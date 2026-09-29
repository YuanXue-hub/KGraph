"""图谱最短路径检索端点（HTTP 薄层）。

核心检索在 core/graph_path.py（无 FastAPI 依赖），
Java 主服务 /explore/path 透传本端点，前端图谱探索页调用后做路径高亮。
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from core.graph_path import DEFAULT_MAX_HOPS, MAX_HOPS_LIMIT, find_shortest_path

router = APIRouter()


@router.get("/api/graph/path")
def graph_path(
    modelId: int = Query(..., gt=0),
    fromId: str = Query(..., min_length=1),
    toId: str = Query(..., min_length=1),
    maxHops: int = Query(DEFAULT_MAX_HOPS, ge=1, le=MAX_HOPS_LIMIT),
):
    """最短路径检索：from → to（无向 BFS，按 modelId 隔离）。"""
    return find_shortest_path(modelId, fromId, toId, maxHops)
