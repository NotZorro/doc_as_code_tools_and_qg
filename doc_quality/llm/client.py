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
        self.timeout_s = float(timeout_s)
        self._client = httpx.Client(timeout=self.timeout_s)

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

    def chat(self, *, model: str, messages: list[dict[str, str]], temperature: float = 0.0, max_tokens: int = 1200, response_format: Any | None = None) -> ChatResponse:
        url = self._endpoint()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        try:
            r = self._client.post(url, headers=headers, json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response_format is not None and e.response is not None and 400 <= e.response.status_code < 500:
                err_txt = ''
                try:
                    err_txt = e.response.text or ''
                except Exception:
                    err_txt = ''
                if 'response_format' in err_txt or 'response format' in err_txt:
                    payload.pop('response_format', None)
                    r = self._client.post(url, headers=headers, json=payload)
                    r.raise_for_status()
                else:
                    raise
            else:
                raise
        raw = r.json()
        content = ""
        try:
            content = raw["choices"][0]["message"]["content"]
        except Exception:
            content = str(raw)
        return ChatResponse(content=content or "", raw=raw)

    def close(self) -> None:
        self._client.close()
