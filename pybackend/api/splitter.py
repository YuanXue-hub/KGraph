"""语料分块 API 端点（无状态纯函数，不感知 corpusId / 用户 / 数据库）。"""
import time
from typing import Optional

from fastapi import APIRouter, HTTPException

from models.schemas import SplitChunkItem, SplitRequest, SplitResult
from splitter import STRATEGY_REGISTRY

router = APIRouter()

MAX_TEXT_BYTES = 10 * 1024 * 1024  # 10MB
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 8000
MAX_CHUNKS = 2000
MAX_SEPARATOR_LEN = 20


def _restore_escapes(sep: str) -> str:
    """将用户输入的 \\n / \\t 字面量还原为真实字符。"""
    return sep.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")


@router.post("/api/split", response_model=SplitResult)
def split_text(req: SplitRequest) -> SplitResult:
    """按策略对文本分块，返回带闭区间偏移量的块列表。"""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="待分块文本为空")
    if len(req.text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise HTTPException(status_code=413, detail="文本超过 10MB 上限，请先拆分语料")

    strategy = STRATEGY_REGISTRY.get(req.strategy)
    if strategy is None:
        raise HTTPException(status_code=400,
                            detail=f"未知分块策略: {req.strategy}，可选: {list(STRATEGY_REGISTRY)}")

    # 参数钳制（不报错，钳到边界）
    chunk_size = req.chunkSize if req.chunkSize is not None else strategy.default_size
    chunk_size = max(MIN_CHUNK_SIZE, min(MAX_CHUNK_SIZE, chunk_size))
    overlap = req.overlap if req.overlap is not None else strategy.default_overlap
    overlap = max(0, min(overlap, chunk_size // 2))

    separator: Optional[str] = None
    if req.strategy == "recursive" and req.separator is not None and req.separator.strip():
        if len(req.separator) > MAX_SEPARATOR_LEN:
            raise HTTPException(status_code=400, detail=f"分隔符长度超过 {MAX_SEPARATOR_LEN} 字符")
        separator = _restore_escapes(req.separator)

    start = time.time()
    try:
        raw_chunks = strategy.split(req.text, chunk_size, overlap, separator)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分块计算失败: {e}")
    duration = int((time.time() - start) * 1000)

    if len(raw_chunks) > MAX_CHUNKS:
        raise HTTPException(status_code=422,
                            detail=f"分块数量 {len(raw_chunks)} 超过 {MAX_CHUNKS} 上限，请调大块大小后重试")

    items = raw_chunks if not req.previewOnly else raw_chunks[:10]
    chunks = [SplitChunkItem(index=c.index, content=c.content, startOffset=c.startOffset,
                             endOffset=c.endOffset, charCount=c.charCount) for c in items]
    avg = round(sum(c.charCount for c in raw_chunks) / len(raw_chunks)) if raw_chunks else 0

    return SplitResult(
        strategy=req.strategy,
        chunkSize=chunk_size,
        overlap=overlap,
        separator=separator if separator is not None else (req.separator or None),
        totalChunks=len(chunks),
        avgCharCount=avg,
        duration=duration,
        chunks=chunks,
    )
