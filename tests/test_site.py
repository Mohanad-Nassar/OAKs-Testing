"""Checks on the committed static site in site/, which Netlify publishes as-is."""

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

pytestmark = pytest.mark.skipif(not (SITE / "index.html").exists(), reason="site/ not built")


def test_page_is_a_complete_document():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in html.split("</head>")[0]
    assert "[hidden] { display: none !important; }" in html  # the board overlay relies on it
    assert "<title>" in html.split("</head>")[0]


def test_page_matches_its_source(tmp_path, monkeypatch):
    """site/index.html must be rebuilt after editing static_site/index.html."""
    build = runpy.run_path(str(ROOT / "scripts" / "build_static.py"))
    monkeypatch.setitem(build["write_page"].__globals__, "OUT", tmp_path)
    build["write_page"]()
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == (SITE / "index.html").read_text(
        encoding="utf-8"
    ), "run: uv run python scripts/build_static.py --page-only"


def test_every_referenced_data_file_exists_and_parses():
    index = json.loads((SITE / "data" / "index.json").read_text(encoding="utf-8"))
    chunk_ids = {u["chunk"] for u in index["units"].values()}
    chunks = {c: json.loads((SITE / "data" / f"s-{c}.json").read_text(encoding="utf-8")) for c in chunk_ids}

    for uv_id, unit in index["units"].items():
        chunk = chunks[unit["chunk"]]
        assert uv_id in chunk["units"]
        for lesson_id in unit["lessons"]:
            assert str(lesson_id) in chunk["lessons"]

    for lesson_id, chunk_id in index["lessonChunk"].items():
        lesson = chunks[chunk_id]["lessons"][lesson_id]
        for kind in ("starter", "exit"):
            for q in (lesson.get("quiz") or {}).get(kind, []):
                assert q["type"] in {"mc", "short", "match", "order"}
                if "img" in q:
                    assert (SITE / q["img"]).exists()
