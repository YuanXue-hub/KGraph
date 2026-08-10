import json
import re
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from core.graph_writer import GraphWriter
from core.llm_client import LLMClient
from core.prompt_builder import build_messages
from models.schemas import ExtractionRequest, ExtractionResult

router = APIRouter()


def _extract_json(content: str) -> Dict[str, Any]:
    """从 LLM 返回内容中解析 JSON，兼容 markdown 代码块包裹。"""
    text = content.strip()

    # 去除 ```json ... ``` 整体包裹
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    else:
        # 处理未闭合或行内 ``` 起始的情况
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 回退：提取第一个 {...} 块
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise HTTPException(
        status_code=500,
        detail=f"无法解析 LLM 返回的 JSON: {content[:200]}",
    )


@router.post("/api/extract", response_model=ExtractionResult)
def extract(req: ExtractionRequest, request: Request) -> ExtractionResult:
    llm_client: LLMClient = request.app.state.llm_client
    graph_writer: GraphWriter = request.app.state.graph_writer

    # 1. 根据 ontology 构建 Prompt
    messages = build_messages(req.text, req.ontology, req.mode)

    # 2. 调用 DeepSeek API
    start = time.time()
    try:
        content, tokens = llm_client.chat(messages)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {e}")

    # 3. 解析 LLM 返回的 JSON
    data = _extract_json(content)
    entities: List[Dict[str, Any]] = data.get("entities", []) or []
    relations: List[Dict[str, Any]] = data.get("relations", []) or []

    # 4. 直接写入 Neo4j（节点带 modelId 隔离）
    try:
        write_count = graph_writer.write(entities, relations, req.modelId)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j 写入失败: {e}")

    # 5. 返回结果
    duration = int((time.time() - start) * 1000)

    return ExtractionResult(
        entities=entities,
        relations=relations,
        tokenConsumed=tokens,
        duration=duration,
        writeCount=write_count,
    )
