import json
from doc_quality.llm.json_mode import llm_json

def _schema():
    return {
        "type": "object",
        "required": ["feature", "scenarios"],
        "properties": {
            "feature": {"type": "object"},
            "scenarios": {"type": "array"},
        },
        "additionalProperties": True,
    }

def test_llm_json_repairs_schema_echo(DummyClient):
    schema_echo = json.dumps({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["feature", "scenarios"],
        "properties": {"feature": {"type": "object"}, "scenarios": {"type": "array"}}
    })
    good = json.dumps({
        "feature": {"id": "F-1", "title": "T"},
        "scenarios": [{"id":"TC-001","title":"x","steps":["s"],"expected":["e"]}]
    })
    client = DummyClient([schema_echo, good])

    obj, raw, err = llm_json(
        client=client,
        model="x",
        messages=[{"role":"system","content":"x"}],
        schema=_schema(),
        temperature=0.0,
        max_tokens=200,
        retries=2,
    )
    assert err is None
    assert obj and obj["feature"]["id"] == "F-1"

def test_llm_json_salvages_truncated_json(DummyClient):
    # valid object but missing last brace
    truncated = '{ "feature": {"id":"F-2","title":"T"}, "scenarios":[{"id":"TC-001","title":"x","steps":["s"],"expected":["e"]}]'
    client = DummyClient([truncated])

    obj, raw, err = llm_json(
        client=client,
        model="x",
        messages=[{"role":"system","content":"x"}],
        schema=_schema(),
        temperature=0.0,
        max_tokens=200,
        retries=0,
    )
    assert err is None
    assert obj["feature"]["id"] == "F-2"
