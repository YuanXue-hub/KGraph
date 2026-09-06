"""sentence 策略：按句末标点+换行切句，贪心合并至目标长度，组间按完整句回取重叠。"""
import re
from typing import List, Optional, Tuple

from splitter.base import Chunk, SplitStrategy, make_chunk, merge_pieces

# 句末标点 + 换行（零宽断言切分，分隔符保留在前句尾部）
_SENT_SPLIT_RE = re.compile(r"(?<=[。！？!?；;\n])")


class SentenceStrategy(SplitStrategy):
    name = "sentence"
    default_size = 1000
    default_overlap = 100

    def split(self, text: str, chunk_size: int, overlap: int,
              separator: Optional[str] = None) -> List[Chunk]:
        if not text or not text.strip():
            return []

        # 1. 切句（保留分隔符），记录排他区间
        pieces: List[Tuple[int, int]] = []
        pos = 0
        for part in _SENT_SPLIT_RE.split(text):
            if part and part.strip():
                pieces.append((pos, pos + len(part)))
            pos += len(part)
        if not pieces:
            return []

        # 2. 超长单句硬切为 chunk_size 的片段
        sized: List[Tuple[int, int]] = []
        for s, e in pieces:
            if e - s > chunk_size:
                p = s
                while p < e:
                    sized.append((p, min(p + chunk_size, e)))
                    p += chunk_size
            else:
                sized.append((s, e))

        # 3. 贪心合并 + overlap 完整句回取
        return merge_pieces(text, sized, chunk_size, overlap)
