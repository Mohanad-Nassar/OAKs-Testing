"""Build a static, server-free copy of Oak Explorer into site/.

The page (static_site/index.html) does browsing, search, the mistakes check and
progress tracking in the browser. This script exports the KS3–KS4 data it needs:

    site/index.html
    site/data/index.json      years, programmes, unit list and search index
    site/data/s-<id>.json     unit, lesson and misconception detail, one file per subject

Usage:
    uv run python scripts/build_static.py
"""

import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from oak_explorer import db  # noqa: E402

OUT = ROOT / "site"


def build() -> None:
    with db.connect() as conn:
        years = db.year_groups(conn)
        programmes, year_programmes = {}, {}
        unit_ids: list[int] = []
        for year in years:
            year_programmes[year["id"]] = []
            for summary in db.programmes_for_year(conn, year["id"]):
                prog = db.programme(conn, summary["id"])
                year_programmes[year["id"]].append(prog["id"])
                programmes[prog["id"]] = {
                    "title": prog["title"],
                    "year_id": prog["year_id"],
                    "year": prog["year"],
                    "units": [
                        {"choice": slot["choice"], "options": [u["id"] for u in slot["options"]]}
                        for slot in prog["units"]
                    ],
                }
                for slot in prog["units"]:
                    unit_ids.extend(u["id"] for u in slot["options"])

        unit_ids = list(dict.fromkeys(unit_ids))
        unit_year = {}
        for prog in programmes.values():
            for slot in prog["units"]:
                for uv in slot["options"]:
                    unit_year[uv] = min(unit_year.get(uv, 99), prog["year"])

        subject_of = dict(
            conn.execute(
                f"""
                SELECT uv.id, s.subject_id FROM unit_variant uv
                JOIN unit u ON u.id = uv.unit_id JOIN scheme s ON s.id = u.scheme_id
                WHERE uv.id IN ({",".join("?" * len(unit_ids))})
                """,
                unit_ids,
            ).fetchall()
        )

        chunks: dict[int, dict] = defaultdict(lambda: {"units": {}, "lessons": {}, "mistakes": {}})
        units_index, lesson_chunk, lesson_home = {}, {}, {}
        for uv_id in unit_ids:
            chunk_id = subject_of[uv_id]
            chunk = chunks[chunk_id]
            unit = db.unit(conn, uv_id)
            mistakes = db.misconceptions_for_unit(conn, uv_id)
            for m in mistakes:
                chunk["mistakes"][m["id"]] = _mistake(m)
            lesson_ids = [lesson["id"] for lesson in unit["lessons"]]
            chunk["units"][uv_id] = {
                "name": unit["name"],
                "description": unit["description"],
                "why": unit["why_this_why_now"],
                "prior": unit["prior_knowledge"],
                "threads": unit["threads"],
                "lessons": lesson_ids,
                "mistakes": [m["id"] for m in mistakes],
            }
            units_index[uv_id] = {
                "name": unit["name"],
                "chunk": chunk_id,
                "year": unit_year.get(uv_id),
                "lessons": lesson_ids,
            }
            for lesson_id in lesson_ids:
                lesson_chunk.setdefault(lesson_id, chunk_id)
                lesson_home.setdefault(lesson_id, uv_id)
                if lesson_id in chunk["lessons"]:
                    continue
                lesson = db.lesson(conn, lesson_id)
                lesson_mistakes = db.misconceptions_for_lesson(conn, lesson_id)
                for m in lesson_mistakes:
                    chunk["mistakes"][m["id"]] = _mistake(m)
                chunk["lessons"][lesson_id] = {
                    "name": lesson["name"],
                    "outcome": lesson["outcome"],
                    "points": lesson["key_points"],
                    "keywords": [[k["name"], k["description"]] for k in lesson["keywords"]],
                    "mistakes": [m["id"] for m in lesson_mistakes],
                }

        search = []
        for lesson_id, chunk_id in lesson_chunk.items():
            lesson = chunks[chunk_id]["lessons"][lesson_id]
            terms = " ".join(k[0] for k in lesson["keywords"])
            search.append([lesson_id, lesson["name"], lesson_home[lesson_id], terms])
        search.sort(key=lambda row: row[1].lower())

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    shutil.copy(ROOT / "static_site" / "index.html", OUT / "index.html")
    _write(
        OUT / "data" / "index.json",
        {
            "years": years,
            "yearProgrammes": year_programmes,
            "programmes": programmes,
            "units": units_index,
            "lessonChunk": lesson_chunk,
            "search": search,
        },
    )
    for chunk_id, chunk in chunks.items():
        _write(OUT / "data" / f"s-{chunk_id}.json", chunk)

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(
        f"Built {OUT}: {len(programmes)} programmes, {len(units_index)} units, "
        f"{len(lesson_chunk)} lessons, {len(chunks) + 2} files, {total / 1e6:.1f} MB"
    )


def _mistake(m: dict) -> dict:
    return {
        "belief": m["belief"],
        "statement": m["statement"],
        "correction": m["correction"],
        "lesson": m["lesson_id"],
    }


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    build()
