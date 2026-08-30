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
        self._ensure_tables()

    def _ensure_connection(self):
        """确保连接存活，断开时自动重连。"""
        try:
            self.connection.ping(reconnect=True)
        except Exception:
            self._init_client()

    def _ensure_tables(self):
        """确保 chat_session 会话元数据表存在（存放 AI 生成标题等）。

        注意：所有 VARCHAR 列显式使用 utf8mb4_unicode_ci，
        与 chat_history.sessionId/messageType 的排序规则保持一致，
        避免 LEFT JOIN 时出现 "Illegal mix of collations"。
        """
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_session (
                    sessionId VARCHAR(64)  CHARACTER SET utf8mb4
                                           COLLATE utf8mb4_unicode_ci NOT NULL
                                           PRIMARY KEY COMMENT '会话ID',
                    userId    BIGINT       NOT NULL COMMENT '用户ID（隔离用）',
                    title     VARCHAR(64)  CHARACTER SET utf8mb4
                                           COLLATE utf8mb4_unicode_ci NOT NULL
                                           DEFAULT '' COMMENT 'AI 生成或用户指定的会话标题',
                    createdAt DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updatedAt DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                           ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_userId (userId)
                ) ENGINE=InnoDB
                  DEFAULT CHARSET=utf8mb4
                  COLLATE=utf8mb4_unicode_ci
                  COMMENT='会话元数据（AI生成标题等）';
                """
            )
        self.connection.commit()

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

    def get_llm_models(self, enabled_only: bool = True) -> List[Dict]:
        """查询 LLM 模型配置清单（供问答模型选择）。"""
        self._ensure_connection()
        sql = (
            "SELECT id, provider, model_name, display_name, base_url, api_key, "
            "is_reasoner, temperature, enabled, sort_order FROM llm_model"
        )
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY sort_order ASC, id ASC"
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall() or []

    def get_llm_model_by_id(self, model_id: int) -> Optional[Dict]:
        """按 id 查询单个 LLM 模型配置（供问答时动态构造 LLM）。"""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, provider, model_name, display_name, base_url, api_key, "
                "is_reasoner, temperature, enabled FROM llm_model WHERE id = %s",
                (model_id,),
            )
            return cursor.fetchone()

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
        """获取指定用户的历史会话列表（按最近活跃时间倒序）。

        优先返回 chat_session.title（AI 生成或用户指定的会话标题），
        未设置时降级为 chat_history 中该会话的第一条消息作为标题。
        """
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT h.sessionId                AS sessionId,
                       COALESCE(NULLIF(cs.title, ''), MIN(h.message))
                                                        AS title,
                       MIN(h.message)              AS firstMessage,
                       MAX(h.message)              AS lastMessage,
                       LEAST(IFNULL(cs.createdAt, MIN(h.createTime)),
                             MIN(h.createTime))      AS createdAt,
                       GREATEST(IFNULL(cs.updatedAt, MAX(h.createTime)),
                                MAX(h.createTime))    AS updatedAt,
                       COUNT(*)                    AS messageCount
                FROM chat_history h
                LEFT JOIN chat_session cs
                       ON cs.sessionId = h.sessionId AND cs.userId = h.userId
                WHERE h.userId = %s AND h.isDelete = 0
                GROUP BY h.sessionId
                ORDER BY updatedAt DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return cursor.fetchall()

    def upsert_session_title(self, session_id: str, user_id: int, title: str) -> None:
        """写入或更新会话标题。

        调用方需在写入前保证 title 长度合理（建议 ≤ 20 中文字）。
        """
        self._ensure_connection()
        safe_title = (title or "").strip()[:64]
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_session (sessionId, userId, title)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    updatedAt = CURRENT_TIMESTAMP
                """,
                (session_id, user_id, safe_title),
            )
            self.connection.commit()

    def delete_session(self, session_id: str, user_id: int) -> int:
        """逻辑删除会话（isDelete=1）+ 同步清除 chat_session 元数据。

        仅允许删除自己的会话。返回 chat_history 受影响行数。
        """
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            affected = cursor.execute(
                "UPDATE chat_history SET isDelete = 1 "
                "WHERE sessionId = %s AND userId = %s AND isDelete = 0",
                (session_id, user_id),
            )
            cursor.execute(
                "DELETE FROM chat_session WHERE sessionId = %s AND userId = %s",
                (session_id, user_id),
            )
            self.connection.commit()
            return affected
