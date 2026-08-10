from typing import Any, Dict, List, Tuple

from openai import OpenAI


class LLMClient:
    """DeepSeek (OpenAI 兼容) LLM 调用封装。读取 config.json 中的 model 配置。"""

    def __init__(self, config: Dict[str, Any]):
        model_cfg = config.get("model", {})
        self.model_name = model_cfg.get("model_name")
        self.client = OpenAI(
            api_key=model_cfg.get("api_key"),
            base_url=model_cfg.get("base_url"),
        )

    def chat(self, messages: List[Dict[str, str]]) -> Tuple[str, int]:
        """调用 LLM，返回 (文本响应, 总 token 数)。"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return content, tokens
