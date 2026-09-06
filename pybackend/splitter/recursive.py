"""recursive 策略：递归字符分割，分隔符层级逐级降级（对齐 langchain 思路，中文优先标点）。"""
from typing import List, Optional, Tuple

from splitter.base import Chunk, SplitStrategy, merge_pieces


class RecursiveStrategy(SplitStrategy):
    name = "recursive"
    default_size = 1000
    default_overlap = 100

    # 分隔符层级：段落 → 行 → 句 → 分句 → 词（一级可由用户自定义替换）
    SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " "]

    def split(self, text: str, chunk_size: int, overlap: int,
              separator: Optional[str] = None) -> List[Chunk]:
        if not text or not text.strip():
            return []
        seps = list(self.SEPARATORS)
        if separator:
            seps[0] = separator
            seps = [s for i, s in enumerate(seps) if s not in seps[:i]]  # 去重保持顺序

        leaves: List[Tuple[int, int]] = []
        self._recursive(text, 0, len(text), seps, 0, chunk_size, leaves)

        return merge_pieces(text, leaves, chunk_size, overlap)

    def _recursive(self, text: str, s: int, e: int, seps: List[str],
                   level: int, size: int, leaves: List[Tuple[int, int]]) -> None:
        """将 [s, e) 按 seps[level] 起逐级切分为原子片段。"""
        if not text[s:e].strip():
            return
        if e - s <= size:
            leaves.append((s, e))
            return
        if level >= len(seps):
            # 所有层级耗尽，硬切
            p = s
            while p < e:
                leaves.append((p, min(p + size, e)))
                p += size
            return

        sep = seps[level]
        parts: List[Tuple[int, int]] = []
        pos = s
        idx = text.find(sep, s, e)
        while idx != -1:
            parts.append((pos, idx + len(sep)))  # 分隔符归属前段
            pos = idx + len(sep)
            idx = text.find(sep, pos, e)
        parts.append((pos, e))

        if len(parts) == 1:
            # 当前分隔符不存在，同一区间降级到下一级
            self._recursive(text, s, e, seps, level + 1, size, leaves)
            return
        for ps, pe in parts:
            self._recursive(text, ps, pe, seps, level + 1, size, leaves)
