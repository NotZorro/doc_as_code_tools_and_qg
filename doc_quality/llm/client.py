from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urljoin

import httpx


@dataclass(frozen=True)
class ChatResponse:
    content: str
    raw: dict[str, Any]


class OpenAICompatClient:
    """Very small client for OpenAI-compatible /v1/chat/completions APIs."""

    def __init__(self, base_url: str, api_key: str, timeout_s: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(timeout=timeout_s)

    def _endpoint(self) -> str:
        # Accept base_url variants:
        # - https://host/v1
        # - https://host/v1/
        # - https://host
        # We'll always post to .../chat/completions
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/v1"):
            return self.base_url + "/chat/completions"
        return self.base_url + "/v1/chat/completions"

    def chat(self, *, model: str, messages: list[dict[str, str]], temperature: float = 0.0, max_tokens: int = 1200) -> ChatResponse:
        url = self._endpoint()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = self._client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        raw = r.json()
        # OpenAI-like response
        content = ""
        try:
            content = raw["choices"][0]["message"]["content"]
        except Exception:
            content = str(raw)
        return ChatResponse(content=content or "", raw=raw)

    def close(self) -> None:
        self._client.close()
