from doc_quality.test_design.plan import build_split_plan
from doc_quality.test_design.merge import merge_group_fragments
from doc_quality.test_design.coverage import compute_coverage

def _bundle():
    return {
        "feature": {
            "path": "docs/feature.md",
            "title": "Feature X",
            "doc_type": "feature",
            "meta": {"task": "TASK-1", "doc_type": "feature"},
            "text": "## Goal\n...\n",
        },
        "related": [
            {"path":"docs/api1.md","title":"API 1","doc_type":"api","meta":{"task":"TASK-1","doc_type":"api"},"text":"GET /x\n"},
            {"path":"docs/api2.md","title":"API 2","doc_type":"api","meta":{"task":"TASK-1","doc_type":"api"},"text":"GET /y\n"},
            {"path":"docs/algo.md","title":"Algo","doc_type":"algorithm","meta":{"task":"TASK-1","doc_type":"algorithm"},"text":"Rule A\n"},
            {"path":"docs/svc.md","title":"Svc","doc_type":"service","meta":{"task":"TASK-1","doc_type":"service"},"text":"Deps\n"},
        ],
    }

def test_build_split_plan_groups_and_parts():
    feature = {"id":"F-1","title":"Feature X","task":"TASK-1"}
    bundle = _bundle()
    plan = build_split_plan(
        feature=feature,
        bundle=bundle,
        generator_map={"api":"gen_api","algorithm":"gen_algo"},
        default_generator="gen_default",
        doc_types=["feature","api","algorithm","service"],
        max_input_chars=20,  # force chunking
        max_scenarios_per_part=7,
    )
    assert set(plan.groups) == {"feature","api","algorithm","service"}
    # api group should be chunked into multiple parts because max_input_chars is tiny
    api_jobs = [j for j in plan.jobs if j.group == "api"]
    assert len(api_jobs) >= 2
    assert all(j.max_scenarios == 7 for j in plan.jobs)

def test_merge_and_coverage():
    feature = {"id":"F-1","title":"Feature X","task":"TASK-1"}
    source_docs = [
        {"path":"docs/api1.md","title":"API 1","doc_type":"api"},
        {"path":"docs/api2.md","title":"API 2","doc_type":"api"},
    ]
    fragments = [
        {"scenarios":[{"id":"X","title":"t1","steps":["s"],"expected":["e"],"trace":[{"source":"api","ref":"docs/api1.md"}]}]},
        {"scenarios":[{"id":"Y","title":"t1","steps":["s"],"expected":["e"],"trace":[{"source":"api","ref":"docs/api1.md"}]}]},  # duplicate title+steps
        {"scenarios":[{"id":"Z","title":"t2","steps":["s2"],"expected":["e2"],"trace":[{"source":"api","ref":"docs/api2.md"}]}]},
    ]
    suite = merge_group_fragments(group="api", feature=feature, source_docs=source_docs, fragments=fragments)
    assert suite["group"] == "api"
    assert len(suite["scenarios"]) == 2  # dedup
    assert suite["scenarios"][0]["id"].startswith("TC-API-")

    cov = compute_coverage(
        feature=feature,
        bundle_docs=source_docs,
        suites_by_group={"api": suite},
    )
    assert "docs/api1.md" in cov["by_doc"]
    assert cov["by_doc"]["docs/api1.md"]  # covered
