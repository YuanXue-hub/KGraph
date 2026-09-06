"""分块策略注册表：策略名 → 策略实例。"""
from splitter.base import Chunk, SplitStrategy
from splitter.fixed import FixedStrategy
from splitter.recursive import RecursiveStrategy
from splitter.sentence import SentenceStrategy
from splitter.structure import StructureStrategy

STRATEGY_REGISTRY = {
    "fixed": FixedStrategy(),
    "sentence": SentenceStrategy(),
    "recursive": RecursiveStrategy(),
    "structure": StructureStrategy(),
}

__all__ = ["Chunk", "SplitStrategy", "STRATEGY_REGISTRY"]
