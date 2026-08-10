"""基于深度学习的知识抽取 API 端点。"""
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from core.dl_extractor import extract as dl_extract
from core.graph_writer import GraphWriter
from models.schemas import DlExtractionRequest, DlExtractionResult

router = APIRouter()


@router.post("/api/dl/extract", response_model=DlExtractionResult)
def dl_extract_endpoint(req: DlExtractionRequest, request: Request) -> DlExtractionResult:
    """基于深度学习的知识抽取：BiLSTM-CRF 命名实体识别 + 神经网络关系抽取，写入 Neo4j。"""
    graph_writer: GraphWriter = request.app.state.graph_writer

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="待抽取文本为空")

    start = time.time()

    # 1. 执行深度学习抽取
    try:
        result = dl_extract(req.text, req.dlConfig, req.ontology)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"深度学习抽取失败: {e}")

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

    return DlExtractionResult(
        entities=entities,
        relations=relations,
        metrics=metrics,
        tokenConsumed=0,
        duration=duration,
        writeCount=write_count,
    )
