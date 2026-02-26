from pathlib import Path
from doc_quality.engine import write_report_flat

def test_write_report_flat_creates_file(tmp_path: Path):
    out_dir = tmp_path / "out"
    root = tmp_path / "root"
    root.mkdir()
    fp = root / "a b" / "doc.md"
    fp.parent.mkdir(parents=True)
    fp.write_text("# x", encoding="utf-8")
    report = {"ok": True}

    out = write_report_flat(out_dir=out_dir, fp=fp, report=report, root=root, prefix="qg")
    assert out.exists()
    assert out.name.startswith("qg.")
    assert out.suffix.endswith(".json")
