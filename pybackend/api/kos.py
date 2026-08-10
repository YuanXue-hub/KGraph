"""基于 KOS 的知识抽取 API 端点。"""
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from core.graph_writer import GraphWriter
from core.kos_extractor import extract as kos_extract
from models.schemas import KosExtractionRequest, KosExtractionResult

router = APIRouter()


@router.post("/api/kos/extract", response_model=KosExtractionResult)
def kos_extract_endpoint(req: KosExtractionRequest, request: Request) -> KosExtractionResult:
    """基于 KOS 词表驱动的知识抽取：术语识别 + TF-IDF + 概念归类 + 关系构建，写入 Neo4j。"""
    graph_writer: GraphWriter = request.app.state.graph_writer

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="待抽取文本为空")

    start = time.time()

    # 1. 执行 KOS 抽取
    try:
        result = kos_extract(req.text, req.kosConfig, req.ontology)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KOS 抽取失败: {e}")

    entities: List[Dict[str, Any]] = result.get("entities", [])
    relations: List[Dict[str, Any]] = result.get("relations", [])
    metrics: Dict[str, Any] = result.get("metrics", {})

    # 2. 直接写入 Neo4j（节点带 modelId 隔离）
    try:
        write_count = graph_writer.write(entities, relations, req.modelId)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j 写入失败: {e}")

    # 3. 返回结果
    duration = int((time.time() - start) * 1000)

    return KosExtractionResult(
        entities=entities,
        relations=relations,
        metrics=metrics,
        tokenConsumed=0,
        duration=duration,
        writeCount=write_count,
    )
