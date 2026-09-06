"""fixed 策略：固定长度滑窗分块（吸收 text_processor/splitter.py 的句边界回找经验）。"""
from typing import List, Optional

from splitter.base import Chunk, SplitStrategy, make_chunk

# 句末边界标记（分隔符归属前段）
_SENTENCE_ENDINGS = ["。", "！", "？", "!\n", "?\n", ".\n", "\n\n", ". ", "! ", "? "]


class FixedStrategy(SplitStrategy):
    name = "fixed"
    default_size = 1000
    default_overlap = 100

    def split(self, text: str, chunk_size: int, overlap: int,
              separator: Optional[str] = None) -> List[Chunk]:
        if not text or not text.strip():
            return []
        n = len(text)
        if n <= chunk_size:
            chunk = make_chunk(0, text, 0, n)
            return [chunk] if chunk else []

        step = chunk_size - overlap if chunk_size - overlap > 0 else max(1, chunk_size // 2)
        chunks: List[Chunk] = []
        start = 0
        while start < n:
            end = min(start + chunk_size, n)
            if end < n:
                # 窗口内优先回找句末边界截断（命中位置需超过窗长 30%）
                window = text[start:end]
                cut = -1
                for sep in _SENTENCE_ENDINGS:
                    pos = window.rfind(sep)
                    if pos != -1 and pos + len(sep) > chunk_size * 0.3 and pos + len(sep) > cut:
                        cut = pos + len(sep)
                if cut > 0:
                    end = start + cut
            chunk = make_chunk(len(chunks), text, start, end)
            if chunk:
                chunks.append(chunk)
            if end >= n:
                break
            start = max(start + 1, end - overlap)
        return chunks
