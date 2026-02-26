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

    # Prefer a JSON-looking start: {"
    m2 = re.search(r'\{\s*"', text)
    start = m2.start() if m2 else text.find("{")
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
            elif ch == "\\":  # backslash
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

    # EOF with open braces => likely truncated output. Best-effort close.
    tail = text[start:].strip()
    if depth > 0:
        if in_str:
            tail += '"'
        tail += "}" * depth
        return tail

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
    """Call LLM and force JSON output with schema validation. Returns (obj, raw, error).

    Important: we keep the original prompt context on repair attempts.
    Otherwise the model tends to "fix" by echoing the schema back.
    """
    def _looks_like_schema(obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        # JSON-Schema almost always has these keys.
        if "$schema" in obj and "properties" in obj:
            return True
        # Some models omit $schema but still return schema-like objects.
        if "properties" in obj and "required" in obj and all(isinstance(k, str) for k in obj.keys()):
            # Heuristic: schema has lots of structural keywords
            schema_keys = {"properties", "required", "type", "allOf", "anyOf", "oneOf", "items", "$defs", "definitions"}
            if len(schema_keys.intersection(set(obj.keys()))) >= 3:
                return True
        return False

    last_err: str | None = None
    base_messages = list(messages)
    current = list(base_messages)
    raw = ""
    cur_max_tokens = max_tokens

    for attempt in range(retries + 1):
        resp = client.chat(model=model, messages=current, temperature=temperature, max_tokens=cur_max_tokens, response_format={"type": "json_object"})
        raw = resp.content or ""

        # anti-CJK repair (your MVP trauma lives on)
        if has_cjk(raw):
            current = base_messages + [
                {"role": "system", "content": "Перепиши ответ строго на русском и верни ТОЛЬКО валидный JSON. Без markdown, без пояснений. Ответ начинается с { и заканчивается }."},
                {"role": "user", "content": raw[:4000]},
            ]
            continue

        parsed_obj: Any = None
        try:
            parsed_obj = json.loads(extract_first_json_object(raw))
            validate(instance=parsed_obj, schema=schema)
            return parsed_obj, raw, None
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            last_err = str(e)

            # If output looks truncated, retry with more tokens.
            if ('Unbalanced braces' in last_err) or ('EOF' in last_err) or ('Expecting' in last_err and 'delimiter' in last_err):
                cur_max_tokens = min(int(cur_max_tokens * 1.7), 4096)

            # Try to detect the most common failure mode for generators:
            # the model returns JSON-Schema instead of an instance that should satisfy the schema.
            is_schema_echo = False
            if isinstance(parsed_obj, dict) and _looks_like_schema(parsed_obj):
                is_schema_echo = True
            else:
                # If parsing failed, still detect raw schema-ish output
                raw_head = (raw or '').lstrip()[:800]
                if ('"$schema"' in raw_head) and (('"properties"' in raw_head) or ('"required"' in raw_head)):
                    is_schema_echo = True

            raw_snip = (raw or "")[:2500]

            if is_schema_echo:
                repair_user = (
                    "Ты вернул JSON-Schema (описание формата), а нужен JSON-ОБЪЕКТ ДАННЫХ (test-suite).\n"
                    "НЕ возвращай ключи $schema/properties/required/items/oneOf/anyOf/allOf.\n\n"
                    f"Ошибка валидации: {last_err}\n\n"
                    "Верни объект test-suite минимально валидным. Пример формы (заполни своими значениями):\n"
                    "{\"feature\":{\"id\":\"Feature-0001\",\"title\":\"...\",\"task\":\"...\",},"
                    "\"scenarios\":[{\"id\":\"TC-001\",\"title\":\"...\",\"steps\":[\"...\"],\"expected\":[\"...\"]}],"
                    "\"assumptions\":[],\"scope\":{\"in\":[],\"out\":[]},\"open_questions\":[]}\n\n"
                    "Предыдущий вывод (фрагмент):\n"
                    f"{raw_snip}"
                )
            else:
                repair_user = (
                    "Исправь и верни ТОЛЬКО валидный JSON, который проходит проверку по схеме.\n"
                    "Никаких пояснений и markdown. Ответ начинается с { и заканчивается }.\n\n"
                    f"Ошибка: {last_err}\n\n"
                    "Предыдущий вывод (фрагмент):\n"
                    f"{raw_snip}\n\n"
                    "Схема (для валидации, НЕ возвращай её как ответ):\n"
                    f"{json.dumps(schema, ensure_ascii=False)[:4000]}"
                )
            current = base_messages + [
                {"role": "system", "content": "Верни ТОЛЬКО валидный JSON-ОБЪЕКТ с данными. Не возвращай схему/формат."},
                {"role": "user", "content": repair_user},
            ]

    return None, raw, last_err

