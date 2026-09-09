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
from utils.db.mysql_client import MysqlClient

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
- 用户问"某实体的 2 跳/多跳相关实体""和 X 有关联的实体还有哪些""X 的关联圈子"（普通关系多跳扩展）
  → 使用 get_entity_neighborhood，只填 start_entity，不填 end_entity（辐射模式），max_hops 按用户说的跳数填、未说则默认 2
- 用户问"A 和 B 之间有什么关联""A 和 B 是怎么联系起来的""A 到 B 的关联路径"（非因果语义的连通性/中间桥接实体）
  → 使用 get_entity_neighborhood，同时填 start_entity 和 end_entity（两点路径模式）
  → 若工具提示未找到路径，可告知用户两者在当前跳数内无关联，不要改用其他工具反复尝试
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
        t_title = time.time()
        try:
            loop = asyncio.get_event_loop()
            text, _toks = await loop.run_in_executor(None, llm.chat, messages)
        except Exception as e:
            logger.warning("标题生成 attempt=%d LLM 调用失败: %s", attempt, e)
            _log_title_call(user_id, 0, t_title, "error")
            # LLM 报错（网络/额度）→ 直接走规则兜底
            return _rule_based_title_fallback(u, a)
        # 每次真实 LLM 调用记 1 条（含重试），与问答/抽取/评估埋点口径一致
        _log_title_call(user_id, _toks, t_title, "success")

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


def _resolve_llm(config: Dict[str, Any], llm_model_id: Optional[int]) -> Dict[str, Any]:
    """解析本次问答使用的 LLM 配置：优先 llm_model 表（按 id），否则回退 config 默认。"""
    if llm_model_id:
        try:
            row = MysqlClient().get_llm_model_by_id(int(llm_model_id))
            if row and row.get("enabled"):
                return {
                    "model_name": row["model_name"],
                    "api_key": row["api_key"],
                    "base_url": row["base_url"],
                    "temperature": float(row.get("temperature") or 0.3),
                }
        except Exception:
            traceback.print_exc()
    # 回退：config.json 默认配置
    return config.get("model", {})


async def _stream_agent_response(config: Dict[str, Any], model_id: int, message: str, session_id: Optional[str] = None, user_id: Optional[int] = None, llm_model_id: Optional[int] = None):
    model_cfg = _resolve_llm(config, llm_model_id)

    llm = ChatOpenAI(
        model=model_cfg.get("model_name", "deepseek-chat"),
        api_key=model_cfg.get("api_key"),
        base_url=model_cfg.get("base_url"),
        temperature=float(model_cfg.get("temperature", 0.3)),
        streaming=True,
        stream_usage=True,
    )
    chat_model_name = model_cfg.get("model_name", "deepseek-chat")

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
        thinking_streamed_len = 0   # 流式阶段实际已推送的思考字数
        answer_streamed_len = 0     # 流式阶段实际已推送的回答字数
        think_state: Optional[str] = None
        think_tag_open = "<think>"
        think_tag_close = "</think>"
        LARGE_DELTA_THRESHOLD = 40
        skipped_large_thinking: Optional[str] = None  # 超过阈值被暂存的思考内容（多段累积）
        skipped_large_answer: Optional[str] = None    # 超过阈值被暂存的回答内容（多段累积）
        # 累积完整 AI 回答文本，用于对话结束后保存到记忆
        full_answer_parts: list = []
        # LLM 用量统计
        chat_total_tokens = 0
        chat_start_time = time.time()

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
                yield _sse_event("tool_call", {
                    "tool": tool_name,
                    "output": cleaned_output,
                    "status": "done",
                })

            # ── LLM 流式输出：ChatModel token 级 与 Chain 级 ──
            # 注意：实测（deepseek-chat / v4-flash）模型节点整段回答作为单个事件到达，
            # 事件 content 是"本次增量"，多事件时各事件内容依次拼接。
            elif (kind == "on_chat_model_stream") or (kind == "on_chain_stream" and name == "model"):
                raw_chunk = data.get("chunk") if "chunk" in data else data
                # 捕获流式 token 用量（stream_usage=True 时最后一个 chunk 携带 usage_metadata）
                try:
                    chunk_usage = getattr(raw_chunk, "usage_metadata", None) or {}
                    if chunk_usage:
                        chat_total_tokens += int(chunk_usage.get("total_tokens", 0) or 0)
                except Exception:
                    pass
                delta_text = _extract_content(raw_chunk)
                if not delta_text:
                    continue

                # ── <think> 标签状态机 ──
                if think_state is None and think_tag_open in delta_text:
                    think_state = "inside"
                if think_state == "inside" and think_tag_close in delta_text:
                    think_state = "closed"

                phase_is_answer = tool_executed  # ✅ 以 tool_executed 而非 tool_calls_made 判定阶段

                think_delta = ""
                answer_delta = ""

                if think_state is not None:
                    # 出现过 <think> 标签：本事件内拆分思考部分与回答部分
                    text = delta_text
                    if think_tag_open in text:
                        _, text = text.split(think_tag_open, 1)
                    if think_tag_close in text:
                        think_part, rest = text.split(think_tag_close, 1)
                    elif think_state == "closed":
                        # 闭合标签在更早事件中，本事件全部是回答
                        think_part, rest = "", text
                    else:
                        think_part, rest = text, ""
                    think_delta = think_part
                    # </think> 之后的内容即正式回答（无论是否调用过工具）
                    if think_state == "closed" and rest:
                        answer_delta = rest
                else:
                    # 普通模式：无 think 标签
                    if phase_is_answer:
                        answer_delta = delta_text
                    else:
                        think_delta = delta_text

                if think_delta:
                    if len(think_delta) > LARGE_DELTA_THRESHOLD:
                        skipped_large_thinking = (skipped_large_thinking or "") + think_delta
                    else:
                        thinking_streamed_len += len(think_delta)
                        yield _sse_event("thinking", {"content": think_delta})
                if answer_delta:
                    if len(answer_delta) > LARGE_DELTA_THRESHOLD:
                        skipped_large_answer = (skipped_large_answer or "") + answer_delta
                    else:
                        answer_streamed_len += len(answer_delta)
                        full_answer_parts.append(answer_delta)
                        yield _sse_event("answer", {"content": answer_delta})

            # ── LLM 调用完成：累积 token 用量 ──
            elif kind == "on_chat_model_end":
                try:
                    output = event.get("data", {}).get("output")
                    usage = getattr(output, "usage_metadata", None) or {}
                    if usage:
                        chat_total_tokens += int(usage.get("total_tokens", 0) or 0)
                except Exception:
                    pass

            # ── Agent 最终完成（仅 LangGraph 根链） ──
            elif kind == "on_chain_end" and name == "LangGraph":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    messages = output.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        full_text = getattr(last_msg, "content", "") or ""
                        has_tool_calls = bool(getattr(last_msg, "tool_calls", None))
                        # 兜底：从最终 AIMessage 的 usage_metadata 取 token 用量
                        try:
                            final_usage = getattr(last_msg, "usage_metadata", None) or {}
                            if final_usage and chat_total_tokens == 0:
                                chat_total_tokens = int(final_usage.get("total_tokens", 0) or 0)
                        except Exception:
                            pass

                        # 诊断日志：排查"无回答就停止"类问题的关键证据
                        logger.info(
                            "agent完成 sid=%s tool_executed=%s has_tool_calls=%s full_len=%d "
                            "思考已推=%d 思考暂存=%d 回答已推=%d 回答暂存=%d",
                            session_id, tool_executed, has_tool_calls, len(full_text or ""),
                            thinking_streamed_len, len(skipped_large_thinking or ""),
                            answer_streamed_len, len(skipped_large_answer or ""),
                        )

                        # 1) 补发流式阶段被暂存的大段内容（实测模型常整段回答作为单事件到达）
                        had_skipped_think = bool(skipped_large_thinking)
                        had_skipped_answer = bool(skipped_large_answer)
                        if skipped_large_thinking:
                            async for ev in _sse_stream_chunks("thinking", skipped_large_thinking, chunk_size=6, sleep_ms=10):
                                yield ev
                            skipped_large_thinking = None
                        if skipped_large_answer:
                            full_answer_parts.append(skipped_large_answer)
                            async for ev in _sse_stream_chunks("answer", skipped_large_answer, chunk_size=4, sleep_ms=5):
                                yield ev
                            skipped_large_answer = None

                        # 2) 兜底：整个流式阶段一个字都没推出去 → 从最终消息解析补发，
                        #    确保任何情况下用户都能看到回答（不再出现"只收到 done"）
                        if (not thinking_streamed_len and not answer_streamed_len
                                and not had_skipped_think and not had_skipped_answer
                                and full_text):
                            if think_tag_open in full_text and think_tag_close in full_text:
                                _, after = full_text.split(think_tag_open, 1)
                                inside, after_close = after.split(think_tag_close, 1)
                                if inside.strip():
                                    async for ev in _sse_stream_chunks("thinking", inside.strip(), chunk_size=6, sleep_ms=10):
                                        yield ev
                                if after_close.strip():
                                    full_answer_parts.append(after_close.strip())
                                    async for ev in _sse_stream_chunks("answer", after_close.strip(), chunk_size=4, sleep_ms=5):
                                        yield ev
                            else:
                                # 直答无标签：推到 thinking 通道（前端在无工具调用且无 content 时
                                # 会把 thinking 迁移到正式回答区展示）
                                async for ev in _sse_stream_chunks("thinking", full_text, chunk_size=6, sleep_ms=10):
                                    yield ev

                        # 3) 记忆兜底：确保回答文本进入记忆（历史对话恢复时 AI 回复不丢失）
                        if not full_answer_parts and full_text and not has_tool_calls:
                            full_answer_parts.append(full_text)

    except Exception as e:
        chat_failed = True
        yield _sse_event("error", {"message": str(e)})
        traceback.print_exc()
    finally:
        # ── 记录 LLM 调用日志（供用量统计）：1 轮问答 1 条（token 跨工具轮次累计） ──
        try:
            chat_duration_ms = int((time.time() - chat_start_time) * 1000)
            MysqlClient().log_request(
                user_id=user_id,
                model_name=chat_model_name,
                total_tokens=chat_total_tokens,
                duration=chat_duration_ms,
                status="error" if chat_failed else "success",
            )
        except Exception:
            pass

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
                                t = await generate_session_title(u, a, user_id=uid or None)
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


@router.get("/api/chat/llm-models")
async def list_llm_models(userId: int = 0):
    """可用的 LLM 模型清单（enabled=1，按 sort_order 排序），不返回 api_key。
    userId>0 时按用户隔离（仅自己的模型）；否则返回全部（兼容旧调用）。"""
    try:
        if userId:
            rows = MysqlClient().get_llm_models_for_user(userId, enabled_only=True)
        else:
            rows = MysqlClient().get_llm_models(enabled_only=True)
        return [
            {
                "id": r["id"],
                "provider": r["provider"],
                "modelName": r["model_name"],
                "displayName": r["display_name"],
                "isReasoner": bool(r.get("is_reasoner")),
            }
            for r in rows
        ]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"加载模型清单失败: {e}")


# 供应商预设（模型管理页下拉用；Ollama 免 key）
_LLM_PROVIDERS = [
    {"key": "ollama", "label": "Ollama", "baseUrl": "http://localhost:11434/v1", "apiKeyRequired": False},
    {"key": "deepseek", "label": "DeepSeek", "baseUrl": "https://api.deepseek.com/v1", "apiKeyRequired": True},
    {"key": "qwen", "label": "Qwen（通义千问）", "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1", "apiKeyRequired": True},
    {"key": "openai", "label": "OpenAI", "baseUrl": "https://api.openai.com/v1", "apiKeyRequired": True},
]


@router.get("/api/chat/llm-providers")
async def list_llm_providers():
    """模型供应商预设清单（唯一权威来源，前端不硬编码）。"""
    return _LLM_PROVIDERS


def _mask_key(key: str) -> str:
    if not key:
        return ""
    return key[:6] + "****" + key[-4:] if len(key) > 12 else "****"


@router.get("/api/chat/llm-models/manage")
async def list_llm_models_manage(userId: int):
    """模型管理列表（用户隔离）：仅自己的模型，key 脱敏。"""
    rows = MysqlClient().get_llm_models_for_user(userId)
    return [
        {
            "id": r["id"],
            "provider": r["provider"],
            "modelName": r["model_name"],
            "displayName": r["display_name"],
            "baseUrl": r["base_url"],
            "apiKeyMasked": _mask_key(r.get("api_key") or ""),
            "hasKey": bool(r.get("api_key")),
            "isReasoner": bool(r.get("is_reasoner")),
            "enabled": bool(r.get("enabled")),
        }
        for r in rows
    ]


def _validate_model_payload(body: Dict, is_create: bool) -> Dict:
    provider = str(body.get("provider") or "").strip()
    valid_providers = {p["key"] for p in _LLM_PROVIDERS}
    if provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"供应商必须在 {sorted(valid_providers)} 内")
    model_name = str(body.get("modelName") or "").strip()
    display_name = str(body.get("displayName") or "").strip() or model_name
    base_url = str(body.get("baseUrl") or "").strip()
    api_key = str(body.get("apiKey") or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    if not base_url:
        raise HTTPException(status_code=400, detail="接口地址不能为空")
    if is_create:
        preset = next(p for p in _LLM_PROVIDERS if p["key"] == provider)
        if preset["apiKeyRequired"] and not api_key:
            raise HTTPException(status_code=400, detail=f"{preset['label']} 需要填写 API Key")
        if not api_key:
            api_key = "ollama-no-key"  # 免 key 占位，避免空 key 报错
    return {
        "provider": provider, "model_name": model_name, "display_name": display_name,
        "base_url": base_url, "api_key": api_key,
        "is_reasoner": bool(body.get("isReasoner")),
        "enabled": 1 if body.get("enabled", True) else 0,
        "sort_order": int(body.get("sortOrder") or 0),
    }


@router.post("/api/chat/llm-models/manage")
async def create_llm_model(body: Dict):
    """新增模型配置（归属当前用户）。"""
    userId = body.get("userId")
    if not userId:
        raise HTTPException(status_code=400, detail="缺少 userId")
    data = _validate_model_payload(body, is_create=True)
    data["user_id"] = int(userId)
    new_id = MysqlClient().create_llm_model(data)
    return {"id": new_id, "message": "模型已添加"}


@router.put("/api/chat/llm-models/manage/{model_id}")
async def update_llm_model(model_id: int, body: Dict):
    """更新模型配置（仅属主可改；apiKey 留空 = 保持不变）。"""
    userId = body.get("userId")
    if not userId:
        raise HTTPException(status_code=400, detail="缺少 userId")
    data = _validate_model_payload(body, is_create=False)
    data["user_id"] = int(userId)
    affected = MysqlClient().update_llm_model(model_id, int(userId), data)
    if not affected:
        raise HTTPException(status_code=403, detail="模型不存在或无权修改")
    return {"message": "模型已更新"}


@router.delete("/api/chat/llm-models/manage/{model_id}")
async def delete_llm_model(model_id: int, userId: int):
    """逻辑删除模型配置（仅属主可删）。"""
    affected = MysqlClient().delete_llm_model(model_id, userId)
    if not affected:
        raise HTTPException(status_code=403, detail="模型不存在或无权删除")
    return {"message": "模型已删除"}



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
        _stream_agent_response(config, req.modelId, req.message, req.sessionId, req.userId, req.llmModelId),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )