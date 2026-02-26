import json
from doc_quality.renderers.registry import get_renderer, list_renderers

def test_renderer_registry_has_expected():
    names = set(list_renderers())
    assert "json" in names
    assert "text" in names
    assert "test_suite_md_v1" in names
    assert "coverage_md_v1" in names

def test_coverage_md_renderer():
    cov = {
        "feature": {"id":"F-1","title":"X"},
        "stats": {"docs_total": 2, "docs_covered": 1, "coverage_pct": 50},
        "uncovered_docs": [{"path":"b.md","title":"B","doc_type":"api"}],
        "by_group": {"api": {"scenarios": 2}},
    }
    r = get_renderer("coverage_md_v1")
    md = r.render(cov, None)  # ctx optional in renderer
    assert "coverage" in md.lower()
    assert "b.md" in md

def test_json_renderer_is_stable_pretty():
    r = get_renderer("json")
    out = r.render({"b":1,"a":2}, None)
    # pretty JSON should start with '{' and have newlines/indent
    assert out.strip().startswith("{")
    assert "\n" in out
