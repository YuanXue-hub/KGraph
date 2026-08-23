"""智能问答 Agent 接口 —— 流式 SSE 输出思考 / 工具调用 / 正式回答。

LangGraph v1 事件体系：
- on_chain_stream + name="model"  → LLM 流式 token（Command 对象携带 AIMessage）
- on_tool_start / on_tool_end       → 工具调用生命周期
- on_chain_end + name="LangGraph"   → Agent 最终完成
"""

import asyncio
import json
import logging
import time
import random
import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from core.agent_tools import ALL_TOOLS
from core.llm_client import LLMClient
from core.memory_manager import MemoryManager
from models.schemas import ChatAgentRequest
from utils.read.read_config import ReadConfig

logger = logging.getLogger(__name__)
TITLE_MAX_CHARS = 20   # AI 生成标题严格上限（中文字符数）
TITLE_RETRY_MAX = 2    # 超长时最多重试次数（不含首次）
TITLE_WAIT_MAX_MS = 10000  # done 之后最多等多少毫秒补发 title 事件（不阻塞用户，标题晚到晚推）

router = APIRouter()
memory_manager = MemoryManager()

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
- 用户问某个名称的多条记录（同名实体有哪些类型/版本）→ 使用 get_entities_by_name，limit 按问题需要的条数自行决定
- 用户问某个实体的关系 → 使用 get_entity_relations
- 用户问"某事件导致了什么""引发了什么连锁反应""有哪些后续因果影响"（单个事件向外辐射）
  → 【前置步骤】先调用 search_entities 搜索该事件名称，从返回结果中筛选 type 以"事件"开头的事件实体的 canonicalName 作为 start_entity
  → 再调用 get_causal_chain，只填 start_entity，不填 end_entity（辐射模式）
  → 若未找到 type 以"事件"开头的事件实体，直接告知用户"未找到对应的事件实体，请确认事件名称是否正确或检查图谱中是否已抽取该事件"
- 用户问"A 和 B 之间有什么因果关系""A 是怎么传导/影响到 B 的""从 A 到 B 的因果路径"
  → 【前置步骤】先分别调用 search_entities 搜索 A 和 B 的名称，从返回结果中筛选 type 以"事件"开头的事件实体的 canonicalName 分别作为 start_entity 和 end_entity
  → 再调用 get_causal_chain，同时填 start_entity 和 end_entity（两点路径模式）
  → 若 A 或 B 中任意一个未找到 type 以"事件"开头的事件实体，告知用户"未找到[A/B]对应的事件实体，请确认事件名称是否正确或检查图谱中是否已抽取该事件"，并列出当前搜索到的相关静态实体供参考
- 用户明确提到"因果链""因果路径""多跳因果""连锁反应""传导链路"
  → 【前置步骤】先调用 search_entities 确认事件实体存在（type 以"事件"开头），再调用 get_causal_chain
  → 优先使用 get_causal_chain

如果用户的问题与图谱无关，可以直接用自己的知识回答。"""


# ========== 会话标题生成（AI 直接产出 ≤20 字，不截断，不合格重试+规则兜底） ==========

_TITLE_LLM_CLIENT: Optional["LLMClient"] = None  # 懒加载单例

def _get_title_llm() -> "LLMClient":
    """懒加载标题生成用的 LLM 客户端（和对话共用同一个模型配置即可）。"""
    global _TITLE_LLM_CLIENT
    if _TITLE_LLM_CLIENT is None:
        model_cfg = ReadConfig().read_config("model")
        # LLMClient 外层需要 {"model": {...}} 结构（与 main.py 中一致），
        # 这里把 read_config("model") 返回的 model 段包进外层 "model" key
        _TITLE_LLM_CLIENT = LLMClient({"model": model_cfg} if model_cfg else {})
    return _TITLE_LLM_CLIENT


def _count_title_chars(text: str) -> int:
    """统计标题的「显示用字数」：中文/全角 1，其他 0.5，向上取整。

    用来校验 AI 输出是否天然在 20 字限制内（不做 substring，仅用于判断是否需要重试/兜底）。
    """
    if not text:
        return 0
    n = 0.0
    for ch in text:
        cp = ord(ch)
        if (
            '\u4e00' <= ch <= '\u9fff'        # CJK 基本汉字
            or '\u3000' <= ch <= '\u303f'      # CJK 标点
            or '\uff00' <= ch <= '\uffef'      # 全角字符
            or '\u3400' <= ch <= '\u4dbf'      # CJK 扩展 A
            or cp >= 0x20000                   # CJK 扩展 B+（非常用字）
        ):
            n += 1.0
        elif ch.isspace():
            continue
        else:
            n += 0.5
    return int(n) if n == int(n) else int(n) + 1


def _normalize_title_output(raw: str) -> str:
    """对 AI 输出做规范化（去前缀/引号/空白/换行），但不截断字数。"""
    if not raw:
        return ""
    t = raw.strip()
    # 去掉前后成对的引号/书名号/括号，不影响语义
    for lq, rq in [('《', '》'), ('「', '」'), ('"', '"'), ('“', '”'), ('(', ')'), ('（', '）'), ('<', '>')]:
        if len(t) >= 2 and t.startswith(lq) and t.endswith(rq):
            t = t[1:-1].strip()
    # 只取第一行
    if '\n' in t:
        t = t.split('\n', 1)[0].strip()
    # 去掉常见前缀 "标题："/ "话题：" 之类
    for prefix in ('标题：', '标题:', '话题：', '话题:', '摘要：', '摘要:', '主题：', '主题:'):
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
            break
    # 去掉末尾无意义的省略/句号重复
    while t and t[-1] in '。.!！？?~…·':
        if len(t) <= 2:
            break
        t = t[:-1]
    return t.strip()


def _rule_based_title_fallback(user_question: str, ai_answer: str) -> str:
    """当 AI 连续重试仍无法输出合规标题时的规则兜底（不用 AI 任何内容，避免 substring 截断 AI 输出）。

    策略：直接取用户提问原文前 15 个 CJK 字符 + 超过则加"…"。
    兜底标题也保证 ≤ 20 字（15 + 省略号 1 = 16）。
    """
    src = (user_question or "").strip()
    if not src:
        src = (ai_answer or "").strip()
    if not src:
        return "新的对话"
    collected = []
    width = 0
    for ch in src:
        cp = ord(ch)
        is_wide = (
            '\u4e00' <= ch <= '\u9fff'
            or '\u3000' <= ch <= '\u303f'
            or '\uff00' <= ch <= '\uffef'
            or '\u3400' <= ch <= '\u4dbf'
            or cp >= 0x20000
        )
        w = 1 if is_wide else 0.5
        if width + w > 15:
            collected.append('…')
            break
        collected.append(ch)
        width += w
    title = ''.join(collected).strip()
    return title or "新的对话"


# ========== 短路优化：短且信息量充足的问题直接作标题（省一次 LLM 调用，秒出） ==========

# 纯寒暄/无信息量词（命中则必须走 AI 生成，不能直接当标题）
_TITLE_GREETING_SET = {
    "你好", "您好", "在吗", "在么", "谢谢", "多谢", "辛苦了", "再见", "拜拜",
    "好的", "好滴", "嗯嗯", "测试", "test", "hi", "hello", "thanks", "thankyou", "ok",
}

def _is_pure_greeting(q: str) -> bool:
    """判断是否纯寒暄：去掉标点和语气助词后，剩余内容仍在寒暄黑名单中（或为空）。"""
    core = q.lower()
    for ch in " \t,，。.!！?？~～:：;；、\"'“”‘’()（）[]【】":
        core = core.replace(ch, "")
    if not core:
        return True
    if core in _TITLE_GREETING_SET:
        return True
    # 再剥一层语气助词（如「你好呀」「谢谢啦」→「你好」「谢谢」）
    stripped = core
    for ch in "呀啊呢吧哟哇啦嘛哦噢嘿哈":
        stripped = stripped.replace(ch, "")
    return stripped in _TITLE_GREETING_SET


def _short_circuit_title(user_question: str) -> Optional[str]:
    """短路判定：问题本身短且有信息量 → 规范化后直接作为标题，不调 LLM。

    任一条件不满足返回 None，继续走 AI 生成：
      ① 宽度字数 4 ~ 18（太短无信息量；上限留 2 字余量，保证规范化后仍 ≤20）
      ② 非纯寒暄/语气词（你好/在吗/谢谢/测试 等）
      ③ 至少含 2 个汉字（纯英文/数字/符号不走短路，交给 AI 提炼）
    """
    q = (user_question or "").strip()
    if not q:
        return None
    n = _count_title_chars(q)
    if n < 4 or n > TITLE_MAX_CHARS - 2:
        return None
    if _is_pure_greeting(q):
        return None
    if sum(1 for ch in q if '\u4e00' <= ch <= '\u9fff') < 2:
        return None
    title = _normalize_title_output(q)
    if 0 < _count_title_chars(title) <= TITLE_MAX_CHARS:
        return title
    return None


async def generate_session_title(user_question: str, ai_answer: str) -> str:
    """为会话第一轮生成 ≤20 字中文标题。

    核心原则（需求强调）：AI 必须直接输出在字数限制内，绝不在本地对 AI 输出做 substring 截断。
    - Prompt 强约束：「只输出一行标题 / ≤20 中文字 / 不加任何前缀解释」
    - 生成后 _count_title_chars 校验：超过 → 用"明确指出上一次字数"的强约束 Prompt 再请求（最多 TITLE_RETRY_MAX 次）
    - 连续重试仍不合规 → 走 _rule_based_title_fallback（完全不用 AI 输出）
    """
    u = (user_question or "").strip()[:400]
    a = (ai_answer or "").strip()[:500]
    if not u and not a:
        return "新的对话"

    # ── 短路优化：问题本身短且有信息量 → 不调 LLM 直接用问题作标题 ──
    short = _short_circuit_title(u)
    if short:
        return short

    user_prompt_block = (
        f"请把以下「用户提问 + AI 回答」压缩为一句不超过 {TITLE_MAX_CHARS} 个中文字的会话标题。\n"
        "严格遵守（否则判定失败）：\n"
        f"1. 只输出标题这一行文字，不要任何解释、引号、前缀（如 标题：/ 话题：）、后缀、换行、省略号\n"
        f"2. 标题长度必须 ≤ {TITLE_MAX_CHARS} 个中文字（含标点），超过则自动压缩再输出\n"
        "3. 保留核心关键词（图谱名称、提问意图、领域），不要空泛如「对话记录」「智能问答」\n"
        "4. 纯中文标题，不要英文或代码\n\n"
        f"【用户提问】\n{u}\n\n"
        f"【AI 回答摘要（前 500 字）】\n{a}\n\n"
        "【标题】\n"
    )

    llm = _get_title_llm()
    messages = [
        {"role": "system", "content": "你是会话标题助手。只为用户输出一句不超过20字的中文会话标题，其他什么都不写。"},
        {"role": "user", "content": user_prompt_block},
    ]

    attempt = 0
    total_attempts = TITLE_RETRY_MAX + 1  # 首次 + N 次重试
    last_generated_text = ""

    while attempt < total_attempts:
        attempt += 1
        try:
            loop = asyncio.get_event_loop()
            text, _toks = await loop.run_in_executor(None, llm.chat, messages)
        except Exception as e:
            logger.warning("标题生成 attempt=%d LLM 调用失败: %s", attempt, e)
            # LLM 报错（网络/额度）→ 直接走规则兜底
            return _rule_based_title_fallback(u, a)

        last_generated_text = text
        title = _normalize_title_output(text)
        n = _count_title_chars(title)
        if 0 < n <= TITLE_MAX_CHARS:
            # ✅ 成功：AI 天然产出在限制内，直接返回
            return title[:TITLE_MAX_CHARS * 2]  # 只防极端超长，不是业务截断

        # ❌ 超长/空：下一轮重试用更严格的 Prompt，明确告诉模型"上次多少字、必须 ≤20"
        logger.info("标题生成 attempt=%d 不符合长度 n=%s title=%r", attempt, n, title[:40])
        hint = f"上一次生成的标题为 {n} 字（超过上限 {TITLE_MAX_CHARS} 字），已判定失败。" if n > TITLE_MAX_CHARS else "上一次输出为空或无法识别。"
        messages = [
            {"role": "system", "content": "你是会话标题助手。只输出一行标题文本，且严格≤20中文字。绝不写多余内容。"},
            {"role": "user", "content": (
                f"{hint}请重新生成。严格遵守：\n"
                f"1. 只输出标题，不加引号不加前缀不解释不换行\n"
                f"2. 长度 ≤ {TITLE_MAX_CHARS} 字（{TITLE_MAX_CHARS} 个汉字或标点），如果内容长请主动压缩合并关键词\n"
                f"3. 如果超出，视为失败。\n\n"
                f"【用户提问】\n{u}\n"
                f"\n【之前的错误标题（参考）】{last_generated_text}\n\n【标题】\n"
            )},
        ]

    # 全部重试失败 → 规则兜底（完全不使用 AI 产出内容，避免 substring 截断）
    logger.warning(
        "标题生成重试 %d 次仍未合规，走规则兜底。last_text=%r",
        total_attempts, last_generated_text[:100],
    )
    return _rule_based_title_fallback(u, a)


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


async def _stream_agent_response(config: Dict[str, Any], model_id: int, message: str, session_id: Optional[str] = None, user_id: Optional[int] = None):
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

    # ── 加载历史记忆并保存用户消息 ──
    history_messages = []
    if session_id:
        try:
            history_messages = memory_manager.get_langchain_memory(session_id)
            memory_manager.add_memory(session_id, "user", message, user_id or 0)
        except Exception as e:
            traceback.print_exc()
            # 记忆加载失败不阻断对话，降级为无记忆模式

    # 拼接：历史记忆 + 当前用户消息
    agent_messages = history_messages + [HumanMessage(content=user_message)]

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
        # 累积完整 AI 回答文本，用于对话结束后保存到记忆
        full_answer_parts: list = []

        async for event in agent.astream_events(
            {"messages": agent_messages},
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
                            full_answer_parts.append(delta)
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
                            full_answer_parts.append(delta)
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

                        # 无工具调用的直答场景：流式阶段已将全部内容作为 thinking 推送（前端已展示），
                        # 此处不重复推送 SSE，仅将完整回答存入记忆，保证历史对话恢复时 AI 回复不丢失
                        if not tool_executed and not has_tool_calls and full_text and not full_answer_parts:
                            full_answer_parts.append(full_text)
                        else:
                            # 有工具调用：优先使用"暂存的大段累积内容"（流式事件但 delta 过大被跳过的）
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
                                # 确保最终回答文本被累积（用于保存到记忆）
                                full_answer_parts.append(pending_answer)
                                async for ev in _sse_stream_chunks("answer", pending_answer, chunk_size=4, sleep_ms=5):
                                    yield ev

    except Exception as e:
        yield _sse_event("error", {"message": str(e)})
        traceback.print_exc()
    finally:
        # ── 保存 AI 回答到记忆 ──
        title_task: Optional[asyncio.Task] = None
        if session_id:
            answer_text = "".join(full_answer_parts).strip()
            if answer_text:
                try:
                    memory_manager.add_memory(session_id, "ai", answer_text, user_id or 0)
                except Exception:
                    traceback.print_exc()

            # ── 第一轮 user+ai 完成后：异步生成会话标题（不阻塞主流程） ──
            try:
                done_flag = memory_manager.redis.get_session_meta(session_id, "title_done") or ""
                if done_flag != "1":
                    mem = memory_manager.get_memory(session_id)
                    # 刚好 2 条 = 1 user + 1 ai → 第一轮完成
                    if len(mem) == 2:
                        user_msg = next(
                            (m["content"] for m in mem if m.get("role") in ("user", "human")),
                            message,
                        )
                        ai_msg = next(
                            (m["content"] for m in mem if m.get("role") in ("ai", "assistant")),
                            answer_text,
                        )

                        async def _do_title_and_save(
                            sid=session_id, uid=user_id or 0, u=user_msg, a=ai_msg
                        ):
                            try:
                                t = await generate_session_title(u, a)
                            except Exception as exc:
                                logger.exception("后台生成会话标题异常：%s", exc)
                                t = ""
                            if not t:
                                t = _rule_based_title_fallback(u, a)
                            try:
                                memory_manager.mysql.upsert_session_title(sid, uid, t)
                            except Exception:
                                logger.exception("会话标题写入 MySQL 失败 sid=%s", sid)
                            try:
                                memory_manager.redis.set_session_meta(sid, "title", t)
                                memory_manager.redis.set_session_meta(sid, "title_done", "1")
                            except Exception:
                                logger.exception("会话标题写入 Redis 失败 sid=%s", sid)
                            return t

                        title_task = asyncio.create_task(_do_title_and_save())
            except Exception:
                traceback.print_exc()
                title_task = None

    # ── 先发 done（DeepSeek 式：回答一结束就恢复输入框，绝不让用户等标题生成）──
    yield _sse_event("done", {})

    # ── done 之后继续持有连接等后台标题：生成完就补发 title 事件（最多 TITLE_WAIT_MAX_MS）。
    #    超时或客户端提前断开都没关系——标题任务本身会继续跑完并写入 MySQL+Redis，下次进页面可见。
    #    title 事件带 sessionId，前端按会话精准匹配（用户此时可能已切换/新建了别的会话）。──
    if title_task is not None:
        title_sid = str(session_id or "")
        try:
            await asyncio.wait_for(asyncio.shield(title_task), timeout=TITLE_WAIT_MAX_MS / 1000.0)
        except (asyncio.TimeoutError, Exception):
            pass
        if title_task.done() and not title_task.cancelled():
            try:
                res = title_task.result()
                if isinstance(res, str) and res:
                    yield _sse_event("title", {"title": res, "sessionId": title_sid})
            except Exception:
                logger.exception("获取会话标题结果失败")


@router.post("/api/chat/session/create")
async def create_chat_session():
    """创建新会话，返回 session_id（字符串）。

    生成规则：时间戳（毫秒）+ 随机数，确保唯一。
    对话发生时消息才会写入 chat_history 表，创建会话本身不写入。
    """
    session_id = str(int(time.time() * 1000) * 1000 + random.randint(0, 999))
    return {"sessionId": session_id}


@router.get("/api/chat/session/list")
async def list_chat_sessions(userId: int):
    """获取指定用户的历史会话列表（从 MySQL 永久存储中查询，用户间隔离）。"""
    sessions = memory_manager.mysql.get_sessions(userId)
    # datetime 序列化为字符串，便于前端展示
    for s in sessions:
        for key in ("createdAt", "updatedAt"):
            if s.get(key) is not None:
                s[key] = s[key].strftime("%Y-%m-%d %H:%M:%S")
    return {"sessions": sessions}


@router.get("/api/chat/session/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话的完整消息列表（供前端切换页面后恢复历史对话）。"""
    messages = memory_manager.mysql.get_session_messages(session_id)
    return {"messages": messages}


@router.delete("/api/chat/session/{session_id}")
async def delete_chat_session(session_id: str, userId: int):
    """删除会话：清除 Redis 记忆 + MySQL 逻辑删除（isDelete=1）。

    仅允许删除自己的会话（按 userId 过滤）。
    """
    affected = memory_manager.delete_memory(session_id, userId)
    return {"message": f"会话 {session_id} 已删除", "affected": affected}


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
        _stream_agent_response(config, req.modelId, req.message, req.sessionId, req.userId),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )