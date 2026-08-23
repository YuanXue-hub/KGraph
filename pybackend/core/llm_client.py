from typing import Any, Dict, List, Tuple

from openai import OpenAI


class LLMClient:
    """DeepSeek (OpenAI 兼容) LLM 调用封装。读取 config.json 中的 model 配置。"""

    def __init__(self, config: Dict[str, Any]):
        model_cfg = config.get("model", {})
        self.model_name = model_cfg.get("model_name")
        timeout = float(model_cfg.get("timeout_sec", 120.0))
        max_retries = int(model_cfg.get("max_retries", 1))
        self.client = OpenAI(
            api_key=model_cfg.get("api_key"),
            base_url=model_cfg.get("base_url"),
            timeout=timeout,
            max_retries=max_retries,
        )

    def chat(self, messages: List[Dict[str, str]], force_json: bool = False) -> Tuple[str, int]:
        """调用 LLM，返回 (文本响应, 总 token 数)。

        force_json=True 时附加 response_format=json_object（DeepSeek 官方 JSON 模式，
        要求 prompt 中必须包含 "json" 字样——抽取 Prompt 均满足）。
        """
        # 针对 deepseek-v4/R1 等推理模型：显式设置 max_tokens，
        # 避免 reasoning_content 吃掉所有 completion budget 导致 content 为空。
        # 同时对推理模型设置 reasoning_effort=low 控制思考长度，进一步提速。
        extra_kwargs: Dict[str, Any] = {}
        model_name_low = (self.model_name or "").lower()
        if any(k in model_name_low for k in ("r1", "reason", "v4")):
            extra_kwargs["reasoning_effort"] = "low"
            extra_kwargs["max_tokens"] = 32768
        else:
            extra_kwargs["max_tokens"] = 16384
        if force_json:
            # 推理模型不支持 response_format，仅普通 chat 模型启用硬约束
            if not any(k in model_name_low for k in ("r1", "reason")):
                extra_kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0,
            **extra_kwargs,
        )
        # DeepSeek R1: response.choices[0].message 可能有 reasoning_content
        # content 才是最终输出，优先取 content；若为空则走 fallback 逻辑
        choice0 = response.choices[0]
        msg = choice0.message
        content = msg.content or ""
        # 极端兜底：如果 content 为空（reasoning 过长截断），从 reasoning 末尾剥离 JSON 尝试恢复
        if not content:
            reasoning = getattr(msg, "reasoning_content", None) or ""
            if reasoning:
                # 从推理末尾找最后一个 ```json 代码块或最外层的 {...}
                import re as _re
                m = _re.search(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", reasoning[-20000:])
                if m:
                    content = m.group(1)
        tokens = response.usage.total_tokens if response.usage else 0
        return content, tokens
