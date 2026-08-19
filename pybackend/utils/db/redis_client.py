import redis
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from utils.read.read_config import ReadConfig


class RedisClient:
    """Redis 客户端（单例）—— 提供模型历史记忆，每天 0 点后过期。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        config = ReadConfig()
        redis_config = config.read_config("memory")["redis"]
        self.client = redis.Redis(
            host=redis_config["host"],
            port=redis_config["port"],
            db=redis_config["db"],
            decode_responses=True,
        )
        self.max_messages = redis_config.get("max_messages", 50)

    @staticmethod
    def _ttl_until_midnight() -> int:
        """计算当前时间到次日 0 点的秒数（TTL，每天 0 点过期）。"""
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return int((tomorrow - now).total_seconds())

    def get_message(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史消息列表。空会话返回空列表 []。"""
        key = f"chat:session:{session_id}"
        data = self.client.lrange(key, 0, -1)
        return [json.loads(msg) for msg in data]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息并刷新 TTL（到次日 0 点）。"""
        key = f"chat:session:{session_id}"
        msg = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        self.client.rpush(key, msg)
        # 保留最近 max_messages 条
        self.client.ltrim(key, -self.max_messages, -1)
        # 刷新过期时间为次日 0 点
        self.client.expire(key, self._ttl_until_midnight())

    def has_session(self, session_id: str) -> bool:
        """判断 Redis 中是否存在该会话的记忆（用于降级判断）。"""
        key = f"chat:session:{session_id}"
        return self.client.exists(key) > 0

    def clear_message(self, session_id: str) -> None:
        """清除会话记忆。"""
        key = f"chat:session:{session_id}"
        self.client.delete(key)
