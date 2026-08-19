import pymysql
from typing import List, Dict, Optional
from utils.read.read_config import ReadConfig


class MysqlClient:
    """MySQL 客户端（单例）—— 永久存储对话历史。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        config = ReadConfig()
        mysql_config = config.read_config("memory")["mysql"]
        self._db_config = mysql_config
        self.connection = pymysql.connect(
            host=mysql_config["host"],
            port=mysql_config["port"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            database=mysql_config["database"],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )

    def _ensure_connection(self):
        """确保连接存活，断开时自动重连。"""
        try:
            self.connection.ping(reconnect=True)
        except Exception:
            self._init_client()

    def add_message(self, role: str, session_id: str, content: str, user_id: int) -> None:
        """写入一条对话消息到 chat_history 表。"""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_history (message, messageType, sessionId, userId) "
                "VALUES (%s, %s, %s, %s)",
                (content, role, session_id, user_id),
            )
            self.connection.commit()

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, str]]:
        """获取历史消息（按时间正序，用于降级恢复到 Redis）。"""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT message, messageType FROM chat_history "
                "WHERE sessionId = %s AND isDelete = 0 "
                "ORDER BY createTime ASC LIMIT %s",
                (session_id, limit),
            )
            rows = cursor.fetchall()
            # 统一输出格式：{role, content}
            return [
                {"role": row["messageType"], "content": row["message"]}
                for row in rows
            ]

    def get_session_messages(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话的完整消息列表（供前端展示历史对话）。"""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT message, messageType FROM chat_history "
                "WHERE sessionId = %s AND isDelete = 0 "
                "ORDER BY createTime ASC",
                (session_id,),
            )
            rows = cursor.fetchall()
            return [
                {"role": row["messageType"], "content": row["message"]}
                for row in rows
            ]

    def get_sessions(self, user_id: int, limit: int = 50) -> List[Dict]:
        """获取指定用户的历史会话列表（按最近活跃时间倒序）。"""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT sessionId, MIN(message) AS firstMessage, "
                "MAX(message) AS lastMessage, "
                "MIN(createTime) AS createdAt, MAX(createTime) AS updatedAt, "
                "COUNT(*) AS messageCount "
                "FROM chat_history WHERE userId = %s AND isDelete = 0 "
                "GROUP BY sessionId ORDER BY updatedAt DESC LIMIT %s",
                (user_id, limit),
            )
            return cursor.fetchall()

    def delete_session(self, session_id: str, user_id: int) -> int:
        """逻辑删除会话（isDelete=1），仅允许删除自己的会话。返回受影响行数。"""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            affected = cursor.execute(
                "UPDATE chat_history SET isDelete = 1 "
                "WHERE sessionId = %s AND userId = %s AND isDelete = 0",
                (session_id, user_id),
            )
            self.connection.commit()
            return affected
