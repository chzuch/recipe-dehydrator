"""LLM provider 策略：DeepSeek / Qwen / Kimi 均为 OpenAI 兼容协议。

新增 provider 只需在这里加一个配置，不触碰上层（CLAUDE.md §8）。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from typing import Any

import httpx

from app.domain.exceptions import LLMError

logger = logging.getLogger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
        "env_base": "DEEPSEEK_BASE_URL",
        "env_model": "DEEPSEEK_MODEL",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "env_key": "QWEN_API_KEY",
        "env_base": "QWEN_BASE_URL",
        "env_model": "QWEN_MODEL",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "env_key": "KIMI_API_KEY",
        "env_base": "KIMI_BASE_URL",
        "env_model": "KIMI_MODEL",
    },
}


class OpenAICompatClient:
    """OpenAI 兼容 /chat/completions 客户端，要求模型返回 JSON 对象。"""

    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_sec: float = 90.0,
    ) -> None:
        if not api_key:
            msg = f"provider「{provider}」未配置 API key，请在 .env 中填写"
            raise LLMError(msg)
        self.provider_name = provider
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_sec

    async def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        url = f"{self._base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            if not isinstance(data, dict):
                msg = f"LLM {self.provider_name} 返回了非对象响应"
                raise LLMError(msg)
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            logger.debug(
                "LLM %s/%s ok: prompt_tokens=%s completion_tokens=%s",
                self.provider_name,
                self.model,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
        except httpx.HTTPStatusError as exc:
            msg = f"LLM {self.provider_name} 返回错误 {exc.response.status_code}: {exc.response.text[:200]}"
            raise LLMError(msg) from exc
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            msg = f"LLM {self.provider_name} 调用失败: {exc}"
            raise LLMError(msg) from exc

        return parse_json_content(content)


def parse_json_content(content: str) -> dict[str, Any]:
    """解析 LLM 返回内容为 dict：先严格 JSON，失败则提取首个 {...}。"""
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(content)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    msg = f"LLM 返回内容无法解析为 JSON: {content[:200]}"
    raise LLMError(msg)


def create_llm_client(provider: str, env: Mapping[str, str | None]) -> OpenAICompatClient:
    """按 provider 名从环境变量装配客户端（组合根调用）。"""
    if provider not in _PROVIDERS:
        msg = f"未知 provider: {provider}（可选: {', '.join(_PROVIDERS)}）"
        raise LLMError(msg)
    cfg = _PROVIDERS[provider]
    return OpenAICompatClient(
        provider=provider,
        api_key=env.get(cfg["env_key"]) or "",
        base_url=env.get(cfg["env_base"]) or cfg["base_url"],
        model=env.get(cfg["env_model"]) or cfg["model"],
    )
