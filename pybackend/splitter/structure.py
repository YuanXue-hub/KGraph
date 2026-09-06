"""structure 策略：结构优先分块（Markdown 标题 + 中文编号标题切节，超长节滑窗兜底）。"""
import re
from typing import List, Optional, Tuple

from splitter.base import Chunk, SplitStrategy, make_chunk
from splitter.fixed import FixedStrategy
from splitter.recursive import RecursiveStrategy

# 标题识别模式（行长 ≤ 60 且不以句末标点结尾才认定为标题）
_MD_HEADING = re.compile(r"^#{1,6}\s+\S.*$")
_CN_NUM = re.compile(r"^[一二三四五六七八九十百]+\s*[、.．]\s*\S.*$")
_PAREN_NUM = re.compile(r"^[（(][一二三四五六七八九十\d]+[）)]\s*\S.*$")
_ARABIC_NUM = re.compile(r"^(\d+(\.\d+)+\s*\S|\d+\s*[、.．]\s*\S)")

_MAX_TITLE_LEN = 60
_FALLBACK = RecursiveStrategy()
_SLIDING = FixedStrategy()


def is_title(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > _MAX_TITLE_LEN or s[-1] in "。！？；!?;":
        return False
    return bool(_MD_HEADING.match(s) or _CN_NUM.match(s) or _PAREN_NUM.match(s) or _ARABIC_NUM.match(s))


class StructureStrategy(SplitStrategy):
    name = "structure"
    default_size = 2000
    default_overlap = 200

    def split(self, text: str, chunk_size: int, overlap: int,
              separator: Optional[str] = None) -> List[Chunk]:
        if not text or not text.strip():
            return []

        # 1. 按行扫描标题位置（行起始偏移，排他区间末尾）
        sections: List[Tuple[int, int]] = []  # 每节 (start, end) 排他
        found = False
        pos = 0
        first_title = -1
        for line in text.splitlines(keepends=True):
            if is_title(line):
                found = True
                if first_title == -1:
                    first_title = pos
                sections.append((pos, pos))  # 占位：节的起点，end 稍后回填
            pos += len(line)
        if not found:
            # 全文无标题 → 整体降级 recursive
            return _FALLBACK.split(text, chunk_size, overlap, separator)

        # 2. 构造节区间：首标题前的 preamble（若有内容）+ 各标题节
        bounds: List[Tuple[int, int]] = []
        if first_title > 0 and text[:first_title].strip():
            bounds.append((0, first_title))
        starts = [s for s, _ in sections]
        for i, s in enumerate(starts):
            bounds.append((s, starts[i + 1] if i + 1 < len(starts) else len(text)))

        # 3. 每节：≤ size 单块；超长节用 fixed 滑窗兜底（偏移平移回全文坐标系）
        chunks: List[Chunk] = []
        for sec_start, sec_end in bounds:
            if sec_end - sec_start <= chunk_size:
                chunk = make_chunk(len(chunks), text, sec_start, sec_end)
                if chunk:
                    chunks.append(chunk)
                continue
            sub = _SLIDING.split(text[sec_start:sec_end], chunk_size, overlap)
            for c in sub:
                chunks.append(Chunk(
                    index=len(chunks),
                    content=c.content,
                    startOffset=c.startOffset + sec_start,
                    endOffset=c.endOffset + sec_start,
                    charCount=c.charCount,
                ))
        return chunks
