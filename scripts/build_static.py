"""Build a static, server-free copy of Oak Explorer into site/.

The page (static_site/index.html) does browsing, search, the mistakes check and
progress tracking in the browser. This script exports the KS3–KS4 data it needs:

    site/index.html
    site/data/index.json      years, programmes, unit list and search index
    site/data/s-<id>.json     unit, lesson and misconception detail, one file per subject
    site/img/                 quiz images

Quizzes come from data/oak-quizzes.json (see scripts/fetch_quizzes.py) when it exists.

The output is a complete static site: publish the site/ folder as-is (Netlify uses
netlify.toml at the repo root).

Usage:
    uv run python scripts/build_static.py              # data and page
    uv run python scripts/build_static.py --page-only  # just refresh site/index.html
"""

import hashlib
import json
import shutil
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from oak_explorer import db  # noqa: E402
from oak_explorer.quiz import convert_quiz, math_segments, to_mathml  # noqa: E402

OUT = ROOT / "site"
QUIZZES = ROOT / "data" / "oak-quizzes.json"
IMAGE_CACHE = ROOT / "data" / "quiz-images"

# static_site/index.html is a page body (the shape claude.ai hosting expects). Static hosts serve
# files as they are, so the build wraps it in a full document with its own charset and base styles.
DOCUMENT = """<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Browse Oak National Academy's Year 7–11 curriculum, take starter and exit quizzes, and show them on the board.">
<style>
:root {{ padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }}
body {{ margin: 0; font-size: 14px; }}
img {{ max-width: 100%; }}
[hidden] {{ display: none !important; }}
</style>
{head}
</head>
<body>
{body}
</body>
</html>
"""


def write_page() -> None:
    page = (ROOT / "static_site" / "index.html").read_text(encoding="utf-8")
    # The page's <title>, font links and <style> come before its first element; they belong in <head>.
    split = page.index('<header class="site">')
    html = DOCUMENT.format(head=page[:split].strip(), body=page[split:].strip())
    (OUT / "index.html").write_text(html, encoding="utf-8")


class ImageStore:
    """Downloads quiz images once into data/quiz-images/ and serves them from site/img/."""

    def __init__(self) -> None:
        self.used: set[str] = set()
        self.failed: set[str] = set()

    def __call__(self, url: str) -> str | None:
        name = hashlib.sha1(url.encode()).hexdigest()[:16] + Path(url).suffix.lower()
        cached = IMAGE_CACHE / name
        if not cached.exists():
            if url in self.failed:
                return None
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "oak-explorer/0.1"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = resp.read()
            except OSError:
                self.failed.add(url)
                return None
            IMAGE_CACHE.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        self.used.add(name)
        return f"img/{name}"


def build() -> None:
    raw_quizzes = json.loads(QUIZZES.read_text(encoding="utf-8")) if QUIZZES.exists() else {}
    images = ImageStore()
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

        chunks: dict[int, dict] = defaultdict(
            lambda: {"units": {}, "lessons": {}, "mistakes": {}, "math": {}}
        )
        units_index, lesson_chunk, lesson_home = {}, {}, {}
        quiz_lessons: set[int] = set()
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
                slug = conn.execute("SELECT slug FROM lesson WHERE id = ?", (lesson_id,)).fetchone()[0]
                quiz = convert_quiz(raw_quizzes[slug], images) if slug in raw_quizzes else None
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
                if quiz and (quiz["starter"] or quiz["exit"]):
                    chunk["lessons"][lesson_id]["quiz"] = quiz
                    for latex in math_segments(quiz):
                        mathml = to_mathml(latex)
                        if mathml:
                            chunk["math"][latex] = mathml
                    quiz_lessons.add(lesson_id)

        for uv_id, meta in units_index.items():
            meta["quizzes"] = sum(lid in quiz_lessons for lid in meta["lessons"])
        for prog in programmes.values():
            prog["quizzes"] = sum(
                units_index[uv]["quizzes"] for slot in prog["units"] for uv in slot["options"]
            )

        search = []
        for lesson_id, chunk_id in lesson_chunk.items():
            lesson = chunks[chunk_id]["lessons"][lesson_id]
            terms = " ".join(k[0] for k in lesson["keywords"])
            search.append([lesson_id, lesson["name"], lesson_home[lesson_id], terms])
        search.sort(key=lambda row: row[1].lower())

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    write_page()
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
    if images.used:
        (OUT / "img").mkdir()
        for name in images.used:
            shutil.copy(IMAGE_CACHE / name, OUT / "img" / name)

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(
        f"Built {OUT}: {len(programmes)} programmes, {len(units_index)} units, "
        f"{len(lesson_chunk)} lessons ({len(quiz_lessons)} with quizzes), "
        f"{len(chunks) + 2 + len(images.used)} files, {total / 1e6:.1f} MB"
    )
    if images.failed:
        print(f"Skipped questions needing {len(images.failed)} images that couldn't be downloaded")


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
    if "--page-only" in sys.argv[1:]:
        write_page()
        print(f"Wrote {OUT / 'index.html'}")
    else:
        build()
