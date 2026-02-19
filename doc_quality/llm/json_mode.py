from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import validate, ValidationError

from ..util import has_cjk
from .client import OpenAICompatClient


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_first_json_object(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Empty model output.")

    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()

    start = text.find("{")
    if start == -1:
        raise ValueError("No '{' found.")

    in_str = False
    esc = False
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1].strip()

    raise ValueError("Unbalanced braces.")


def llm_json(
    *,
    client: OpenAICompatClient,
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    temperature: float,
    max_tokens: int,
    retries: int = 2,
) -> tuple[dict[str, Any] | None, str, str | None]:
    """Call LLM and force JSON output with schema validation. Returns (obj, raw, error)."""
    last_err: str | None = None
    current = list(messages)
    raw = ""

    for attempt in range(retries + 1):
        resp = client.chat(model=model, messages=current, temperature=temperature, max_tokens=max_tokens)
        raw = resp.content or ""

        # anti-CJK repair (your MVP trauma lives on)
        if has_cjk(raw):
            current = [
                {"role": "system", "content": "Перепиши ответ строго на русском и верни ТОЛЬКО валидный JSON. Без markdown, без пояснений. Ответ начинается с { и заканчивается }."},
                {"role": "user", "content": raw},
            ]
            continue

        try:
            obj = json.loads(extract_first_json_object(raw))
            validate(instance=obj, schema=schema)
            return obj, raw, None
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            last_err = str(e)
            current = [
                {"role": "system", "content": "Исправь и верни ТОЛЬКО валидный JSON. Никаких пояснений и markdown. Ответ начинается с { и заканчивается }."},
                {"role": "user", "content": f"Ошибка: {last_err}\nСхема:\n{json.dumps(schema, ensure_ascii=False)}\n\nПредыдущий вывод:\n{raw}"},
            ]

    return None, raw, last_err
