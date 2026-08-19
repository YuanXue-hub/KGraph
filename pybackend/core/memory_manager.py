"""会话记忆管理器 —— Redis（模型历史记忆）+ MySQL（永久存储）双层架构。

流程：
1. get_memory：优先从 Redis 读取历史；Redis 过期或不存在时，从 MySQL 加载并回填 Redis
2. add_memory：同时写入 Redis 和 MySQL，Redis TTL 每天次日 0 点过期
3. clear_memory：清除 Redis 记忆（MySQL 永久存储不清除）
4. delete_memory：同时清除 Redis 记忆和 MySQL 逻辑删除（用于会话删除）
"""

import logging
from typing import List, Dict, Optional

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from utils.db.redis_client import RedisClient
from utils.db.mysql_client import MysqlClient

logger = logging.getLogger(__name__)


class MemoryManager:
    """会话记忆管理器。"""

    def __init__(self):
        self.redis = RedisClient()
        self.mysql = MysqlClient()

    # ── LangChain 消息格式转换 ──

    @staticmethod
    def _to_langchain_messages(history: List[Dict[str, str]]) -> List[BaseMessage]:
        """将 {role, content} 列表转为 LangChain Message 列表。"""
        messages: List[BaseMessage] = []
        for item in history:
            role = item.get("role", "")
            content = item.get("content", "")
            if role in ("user", "human"):
                messages.append(HumanMessage(content=content))
            elif role in ("ai", "assistant"):
                messages.append(AIMessage(content=content))
            elif role in ("system",):
                messages.append(SystemMessage(content=content))
        return messages

    # ── 核心方法 ──

    def get_memory(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史记忆（原始 dict 列表）。

        Redis 优先 → Redis 为空时从 MySQL 加载并回填 Redis。
        """
        # 1. Redis 命中
        if self.redis.has_session(session_id):
            memory = self.redis.get_message(session_id)
            if memory:
                logger.info("Redis 命中会话 %s 记忆: %d 条", session_id, len(memory))
                return memory

        # 2. Redis 未命中 → 从 MySQL 降级加载
        logger.info("Redis 未命中会话 %s，从 MySQL 加载记忆", session_id)
        history = self.mysql.get_history(session_id)
        if history:
            # 回填 Redis（每天 0 点过期，下次直接命中）
            for item in history:
                self.redis.add_message(session_id, item["role"], item["content"])
            logger.info("从 MySQL 加载并回填 Redis: 会话 %s, %d 条", session_id, len(history))
        return history

    def get_langchain_memory(self, session_id: str) -> List[BaseMessage]:
        """获取 LangChain 消息列表（供 Agent 直接使用）。"""
        history = self.get_memory(session_id)
        return self._to_langchain_messages(history)

    def add_memory(self, session_id: str, role: str, content: str, user_id: int) -> None:
        """追加一条消息，同时写入 Redis 和 MySQL。

        Args:
            session_id: 会话 ID
            role: 消息角色（user / ai）
            content: 消息内容
            user_id: 用户 ID（用于 MySQL 永久存储的用户隔离）
        """
        # Redis（模型历史记忆，每天 0 点过期）
        self.redis.add_message(session_id, role, content)
        # MySQL（永久存储）
        self.mysql.add_message(role, session_id, content, user_id)

    def clear_memory(self, session_id: str) -> None:
        """清除 Redis 记忆（MySQL 永久存储保留）。"""
        self.redis.clear_message(session_id)
        logger.info("已清除会话 %s 的 Redis 记忆", session_id)

    def delete_memory(self, session_id: str, user_id: int) -> int:
        """删除会话：同时清除 Redis 记忆 + MySQL 逻辑删除。

        Args:
            session_id: 会话 ID
            user_id: 用户 ID（仅允许删除自己的会话）

        Returns:
            MySQL 受影响行数
        """
        # 1. 清除 Redis 记忆
        self.redis.clear_message(session_id)
        # 2. MySQL 逻辑删除（isDelete=1）
        affected = self.mysql.delete_session(session_id, user_id)
        logger.info("已删除会话 %s（用户 %s），MySQL 受影响 %d 行", session_id, user_id, affected)
        return affected
