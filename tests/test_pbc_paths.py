from pathlib import Path
from doc_quality.pbc import resolve_pbc_paths

def test_resolve_pbc_new_layout(tmp_path: Path):
    policy = tmp_path / ".docq"
    (policy / "pbc" / "test_design" / "generators").mkdir(parents=True)
    (policy / "pbc" / "test_design" / "config.yml").write_text("llm: {enabled: false}\n", encoding="utf-8")

    paths = resolve_pbc_paths(policy_root=policy, pbc="test_design")
    assert paths.policy_root == policy.resolve()
    assert paths.pbc == "test_design"
    assert paths.generators_dir == (policy / "pbc" / "test_design" / "generators").resolve()
    assert paths.config_path == (policy / "pbc" / "test_design" / "config.yml").resolve()

def test_resolve_pbc_legacy_layout(tmp_path: Path):
    policy = tmp_path / ".docq"
    (policy / "generators").mkdir(parents=True)
    (policy / "config.yml").write_text("llm: {enabled: false}\n", encoding="utf-8")

    paths = resolve_pbc_paths(policy_root=policy, pbc="anything")
    assert paths.generators_dir == (policy / "generators").resolve()
    assert paths.config_path == (policy / "config.yml").resolve()

def test_resolve_pbc_explicit_overrides(tmp_path: Path):
    policy = tmp_path / ".docq"
    legacy_g = policy / "generators"
    legacy_g.mkdir(parents=True)
    custom_g = tmp_path / "custom_g"
    custom_g.mkdir()

    paths = resolve_pbc_paths(policy_root=policy, pbc="x", generators_dir=custom_g)
    assert paths.generators_dir == custom_g.resolve()
