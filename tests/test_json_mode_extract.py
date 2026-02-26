import json
from doc_quality.llm.json_mode import extract_first_json_object

def test_extract_from_fenced_block():
    text = """some text
```json
{ "a": 1, "b": {"c": 2} }
```
tail"""
    s = extract_first_json_object(text)
    obj = json.loads(s)
    assert obj["a"] == 1
    assert obj["b"]["c"] == 2

def test_extract_from_prefix_noise():
    text = "junk prefix... { \"a\": 1, \"b\": 2 } trailing"
    s = extract_first_json_object(text)
    assert json.loads(s) == {"a": 1, "b": 2}

def test_extract_truncated_adds_missing_braces():
    # Missing final closing brace
    text = '{ "a": 1, "b": {"c": 2} '
    s = extract_first_json_object(text)
    obj = json.loads(s)
    assert obj["b"]["c"] == 2
