"""分块策略公共契约：Chunk 数据类、策略抽象基类、贪心合并工具。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Chunk:
    """分块结果。偏移量为原文闭区间 [startOffset, endOffset]，content 为 strip 后文本。"""
    index: int
    content: str
    startOffset: int
    endOffset: int
    charCount: int


class SplitStrategy(ABC):
    """分块策略抽象基类。所有策略返回的偏移量必须指向 strip 后内容在原文中的真实位置。"""

    name: str = ""
    default_size: int = 1000
    default_overlap: int = 100

    @abstractmethod
    def split(self, text: str, chunk_size: int, overlap: int,
              separator: Optional[str] = None) -> List[Chunk]:
        """执行分块。separator 仅 recursive 策略消费（自定义一级分隔符），其余策略忽略。"""


def make_chunk(index: int, text: str, start: int, end: int) -> Optional[Chunk]:
    """从 text[start:end]（end 为排他下标）构造 Chunk，strip 后重算闭区间偏移。全空白返回 None。"""
    raw = text[start:end]
    if not raw.strip():
        return None
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw) - len(raw.rstrip())
    content = raw.strip()
    return Chunk(
        index=index,
        content=content,
        startOffset=start + leading,
        endOffset=end - trailing - 1,  # 闭区间终点
        charCount=len(content),
    )


def merge_pieces(text: str, pieces: List[Tuple[int, int]], chunk_size: int, overlap: int) -> List[Chunk]:
    """将原子片段（排他区间）贪心合并为块：组内 span ≤ chunk_size，组间回取 ≤ overlap 的完整片段。

    sentence / recursive 两种策略共用。
    """
    chunks: List[Chunk] = []
    n = len(pieces)
    i = 0
    while i < n:
        # 贪心合并 [i, j)，保证组 span ≤ chunk_size
        j = i + 1
        while j < n and pieces[j][1] - pieces[i][0] <= chunk_size:
            j += 1
        g_start = pieces[i][0]
        # overlap 回取：从 i-1 向前收完整片段，起点距 pieces[i] 起点 ≤ overlap
        if overlap > 0 and i > 0:
            k = i - 1
            while k >= 0 and pieces[i][0] - pieces[k][0] <= overlap:
                k -= 1
            if k + 1 < i:
                g_start = pieces[k + 1][0]
        chunk = make_chunk(len(chunks), text, g_start, pieces[j - 1][1])
        if chunk:
            chunks.append(chunk)
        i = j
    return chunks
