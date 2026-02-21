import ast
from pathlib import Path

import pytest


def _write_min_policy(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a minimal policy (templates/validators/config) that makes `run --no-llm` succeed."""
    templates_dir = tmp_path / "templates"
    validators_dir = tmp_path / "validators"
    templates_dir.mkdir()
    validators_dir.mkdir()

    # Minimal template: no required meta, no required sections.
    (templates_dir / "test.yml").write_text(
        """\
id: test
doc_type: test
meta:
  required: []
sections: []
""",
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yml"
    config_path.write_text("llm:\n  enabled: false\n", encoding="utf-8")

    return templates_dir, validators_dir, config_path


def test_cli_main_has_no_local_import_of_iter_md_files():
    """Regression guard: importing iter_md_files *inside* main() makes it a local variable and breaks `run`."""
    src = Path(__file__).resolve().parents[1] / "doc_quality" / "cli.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))

    main_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            main_fn = node
            break
    assert main_fn is not None, "cli.main() must exist"

    bad = []
    for node in ast.walk(main_fn):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in {"iter_md_files", "read_paths_file"}:
                    bad.append((node.module, alias.name, node.lineno))

    assert not bad, f"Do not import these inside main() (breaks scope): {bad}"


def test_cli_run_does_not_crash_with_unboundlocal(tmp_path: Path, capsys):
    from doc_quality.cli import main

    templates_dir, validators_dir, config_path = _write_min_policy(tmp_path)

    # Create a markdown file that matches the template.
    md = tmp_path / "doc.md"
    md.write_text(
        """\
---
doc_type: test
---

# Title

Body
""",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"

    # main() always sys.exit(...)
    with pytest.raises(SystemExit) as e:
        main(
            [
                "run",
                "--paths",
                str(md),
                "--templates-dir",
                str(templates_dir),
                "--validators-dir",
                str(validators_dir),
                "--config",
                str(config_path),
                "--out-dir",
                str(out_dir),
                "--no-llm",
            ]
        )

    assert e.value.code == 0

    # Also ensure we actually wrote reports (so the command didn't early-exit)
    assert (out_dir / "summary.json").exists()


def test_cli_tools_with_missing_dir_exits_zero(tmp_path: Path):
    from doc_quality.cli import main

    missing = tmp_path / "no_such_tools"

    with pytest.raises(SystemExit) as e:
        main(["tools", "--tools-dir", str(missing)])

    assert e.value.code == 0
