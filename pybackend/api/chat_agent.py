"""智能问答 Agent 接口 —— 流式 SSE 输出思考 / 工具调用 / 正式回答。

LangGraph v1 事件体系：
- on_chain_stream + name="model"  → LLM 流式 token（Command 对象携带 AIMessage）
- on_tool_start / on_tool_end       → 工具调用生命周期
- on_chain_end + name="LangGraph"   → Agent 最终完成
"""

import asyncio
import json
import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from core.agent_tools import ALL_TOOLS
from models.schemas import ChatAgentRequest

router = APIRouter()

SYSTEM_PROMPT = """你是一个知识图谱智能问答助手，可以查询知识图谱中的实体、关系和属性信息。

回答规则：
1. 优先使用工具查询图谱数据，基于真实数据回答问题
2. 如果工具返回空结果，如实告知用户未找到相关信息
3. 回答时列出具体的实体名称、类型和关系
4. 回答简洁清晰，使用中文，避免冗余

工具使用策略（重要，必须严格遵守）：
- 一次问答最多调用 3 次工具，达到 3 次后必须给出最终回答
- 工具调用完成后，基于已有结果直接回答，不要继续调用工具"补充"或"验证"信息
- 严禁用"让我继续搜索/查找/发现更多"等理由反复调用工具
- 一次工具调用返回的结果足够回答问题时，立即给出最终回答

工具选择指南：
- 用户问"某类型有哪些实体"（如"人物有哪些""地点有什么"）→ 使用 get_entities_by_type
- 用户搜索特定名称的实体 → 使用 search_entities
- 用户问图谱整体情况 → 使用 get_graph_stats 或 list_entity_types
- 用户问某个实体的详细信息 → 使用 get_entity_detail
- 用户问某个实体的关系 → 使用 get_entity_relations

如果用户的问题与图谱无关，可以直接用自己的知识回答。"""


def _sse_event(event_type: str, data: Dict[str, Any]) -> str:
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def _sse_stream_chunks(event_type: str, text: str, chunk_size: int = 4, sleep_ms: int = 6):
    """将一段文本按 chunk_size 拆成小片段，逐段 yield SSE 事件，以模拟真正的流式输出。"""
    if not text:
        return
    total = len(text)
    i = 0
    while i < total:
        piece = text[i:i + chunk_size]
        yield _sse_event(event_type, {"content": piece})
        i += chunk_size
        if i < total and sleep_ms > 0:
            await asyncio.sleep(sleep_ms / 1000.0)


def _extract_content(chunk: Any) -> str:
    """从 LangGraph astream_events 的各种 chunk 中提取 LLM 文本增量内容。

    兼容多种事件格式：
    - on_chain_stream: chunk 是 Command([...])
    - on_chat_model_stream: chunk 是 AIMessageChunk 或 dict
    """
    # 1. AIMessageChunk / AIMessage / BaseMessage 对象
    if hasattr(chunk, "content"):
        c = chunk.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            # multimodal content, 提取 text 段
            parts = []
            for item in c:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)

    # 2. dict 结构 { "content": "..." }
    if isinstance(chunk, dict):
        c = chunk.get("content", "")
        if isinstance(c, str):
            return c
        # 如果 data.messages → 提取第一个 message 的 content
        msgs = chunk.get("messages", [])
        if msgs:
            return _extract_content(msgs[-1])
        # 如果 chunk 字段
        if "chunk" in chunk:
            return _extract_content(chunk["chunk"])
        return ""

    # 3. list： Command(update={"messages": [...]})
    if isinstance(chunk, list):
        for item in chunk:
            if hasattr(item, "update"):
                msgs = item.update.get("messages", []) if isinstance(item.update, dict) else []
                for msg in msgs:
                    txt = _extract_content(msg)
                    if txt:
                        return txt
            else:
                txt = _extract_content(item)
                if txt:
                    return txt
    return ""


async def _stream_agent_response(config: Dict[str, Any], model_id: int, message: str):
    model_cfg = config.get("model", {})

    llm = ChatOpenAI(
        model=model_cfg.get("model_name", "deepseek-chat"),
        api_key=model_cfg.get("api_key"),
        base_url=model_cfg.get("base_url"),
        temperature=0.3,
        streaming=True,
    )

    agent = create_agent(
        model=llm,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )

    user_message = f"[modelId={model_id}] {message}"

    try:
        tool_calls_made = False
        tool_executed = False  # 关键：是否已经有至少一个工具执行完成（on_tool_end 已触发）→ 进入正式回答阶段
        running_tools: Dict[str, str] = {}  # run_id → tool_name
        thinking_sent_len = 0
        answer_sent_len = 0
        think_state: Optional[str] = None
        think_tag_open = "<think>"
        think_tag_close = "</think>"
        LARGE_DELTA_THRESHOLD = 40
        skipped_large_thinking: Optional[str] = None
        skipped_large_answer: Optional[str] = None

        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=user_message)]},
            config={"recursion_limit": 50},
            version="v2",
        ):
            kind = event.get("event")
            name = event.get("name", "")
            data = event.get("data", {})

            # ── 工具调用开始 ──
            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                run_id = event.get("run_id", "")
                tool_input = event.get("data", {}).get("input", {})
                if isinstance(tool_input, dict) and "model_id" not in tool_input:
                    tool_input["model_id"] = model_id
                running_tools[run_id] = tool_name
                tool_calls_made = True
                yield _sse_event("tool_call", {
                    "tool": tool_name,
                    "input": json.dumps(tool_input, ensure_ascii=False),
                    "status": "running",
                })

            # ── 工具调用完成 ──
            elif kind == "on_tool_end":
                run_id = event.get("run_id", "")
                tool_name = running_tools.pop(run_id, event.get("name", ""))
                raw_output = event.get("data", {}).get("output", "")
                if hasattr(raw_output, "content"):
                    extracted: Any = raw_output.content
                    cleaned_output = extracted if isinstance(extracted, str) else json.dumps(extracted, ensure_ascii=False)
                elif isinstance(raw_output, str) and raw_output.startswith("content='"):
                    try:
                        first_quote = raw_output.index("content='") + len("content='")
                        end_quote = raw_output.index("'", first_quote)
                        cleaned_output = raw_output[first_quote:end_quote]
                    except ValueError:
                        cleaned_output = str(raw_output)
                else:
                    cleaned_output = str(raw_output) if raw_output else ""
                # 关键：有工具真正完成 → 此后的 LLM 输出是正式回答
                tool_executed = True
                answer_sent_len = 0
                yield _sse_event("tool_call", {
                    "tool": tool_name,
                    "output": cleaned_output,
                    "status": "done",
                })

            # ── LLM 流式输出：ChatModel token 级 与 Chain 级 ──
            elif (kind == "on_chat_model_stream") or (kind == "on_chain_stream" and name == "model"):
                raw_chunk = data.get("chunk") if "chunk" in data else data
                full_content = _extract_content(raw_chunk)
                if not full_content:
                    continue

                # ── 解析 <think> 标签 ──
                if think_state is None and think_tag_open in full_content:
                    think_state = "inside"
                if think_state == "inside" and think_tag_close in full_content:
                    think_state = "closed"

                phase_is_answer = tool_executed  # ✅ 以 tool_executed 而非 tool_calls_made 判定阶段

                # 1) 若出现 <think> 标签
                if think_state is not None:
                    text = full_content
                    if think_tag_open in text:
                        _, after_open = text.split(think_tag_open, 1)
                    else:
                        after_open = text
                    if think_tag_close in after_open:
                        think_part, rest = after_open.split(think_tag_close, 1)
                    else:
                        think_part, rest = after_open, ""
                    answer_part = rest if think_state == "closed" else ""

                    if len(think_part) > thinking_sent_len:
                        delta = think_part[thinking_sent_len:]
                        if len(delta) > LARGE_DELTA_THRESHOLD:
                            skipped_large_thinking = delta
                        elif delta:
                            yield _sse_event("thinking", {"content": delta})
                        thinking_sent_len = len(think_part)

                    if phase_is_answer and len(answer_part) > answer_sent_len:
                        delta = answer_part[answer_sent_len:]
                        if len(delta) > LARGE_DELTA_THRESHOLD:
                            skipped_large_answer = delta
                        elif delta:
                            yield _sse_event("answer", {"content": delta})
                        answer_sent_len = len(answer_part)
                    continue

                # 2) 普通模式
                if phase_is_answer:
                    if len(full_content) > answer_sent_len:
                        delta = full_content[answer_sent_len:]
                        if len(delta) > LARGE_DELTA_THRESHOLD:
                            skipped_large_answer = delta
                        elif delta:
                            yield _sse_event("answer", {"content": delta})
                        answer_sent_len = len(full_content)
                else:
                    if len(full_content) > thinking_sent_len:
                        delta = full_content[thinking_sent_len:]
                        if len(delta) > LARGE_DELTA_THRESHOLD:
                            skipped_large_thinking = delta
                        elif delta:
                            yield _sse_event("thinking", {"content": delta})
                        thinking_sent_len = len(full_content)

            # ── Agent 最终完成（仅 LangGraph 根链） ──
            elif kind == "on_chain_end" and name == "LangGraph":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    messages = output.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        full_text = getattr(last_msg, "content", "") or ""
                        has_tool_calls = bool(getattr(last_msg, "tool_calls", None))

                        # 优先使用"暂存的大段累积内容"（来自流式事件但delta过大的）
                        pending_think: Optional[str] = None
                        pending_answer: Optional[str] = None

                        if skipped_large_thinking:
                            pending_think = skipped_large_thinking
                        if skipped_large_answer:
                            pending_answer = skipped_large_answer

                        # 没有暂存 → 从最终 last_msg 解析
                        if pending_think is None and pending_answer is None and not has_tool_calls and full_text:
                            if think_tag_open in full_text and think_tag_close in full_text:
                                _, after = full_text.split(think_tag_open, 1)
                                _inside, after_close = after.split(think_tag_close, 1)
                                pending_think = _inside.strip() or None
                                pending_answer = after_close.strip() or None
                            else:
                                pending_answer = full_text or None

                        # 对暂存 / 解析到的内容进行分段流式推送
                        if pending_think:
                            async for ev in _sse_stream_chunks("thinking", pending_think, chunk_size=6, sleep_ms=10):
                                yield ev
                        if pending_answer:
                            async for ev in _sse_stream_chunks("answer", pending_answer, chunk_size=4, sleep_ms=5):
                                yield ev

    except Exception as e:
        yield _sse_event("error", {"message": str(e)})
        traceback.print_exc()

    yield _sse_event("done", {})


@router.post("/api/chat/agent/stream")
async def chat_agent_stream(req: ChatAgentRequest, request: Request):
    """流式对话 Agent 接口（SSE）。

    事件类型：
    - thinking: LLM 思考过程（工具调用前，token 级流式输出）
    - tool_call: 工具调用（running 开始，done 完成含结果）
    - answer: 正式回答（工具调用后，token 级流式输出）
    - done: 流结束
    - error: 错误信息
    """
    config: Dict[str, Any] = request.app.state.config
    if not config:
        raise HTTPException(status_code=500, detail="配置未加载")

    return StreamingResponse(
        _stream_agent_response(config, req.modelId, req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )