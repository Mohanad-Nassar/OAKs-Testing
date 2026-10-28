"""Turn subjects fetched from Oak's Open API (scripts/fetch_subjects.py) into explorer records.

The ontology's subjects use its database ids. Subjects from the API get ids derived from
their slugs instead, so links, bookmarks and saved progress survive rebuilds. They sit in
a range well above the database's ids.
"""

import hashlib

from .text import belief, clean

ID_BASE = 10_000_000


def stable_id(kind: str, slug: str) -> int:
    digest = hashlib.sha1(f"{kind}:{slug}".encode()).hexdigest()
    return ID_BASE + int(digest[:12], 16) % 900_000_000


def convert_subject(subject: dict, year_ids: dict[int, int], chunk_id: int) -> dict:
    """Records for one subject, in the shapes build_static.py writes.

    Returns {"programmes", "year_programmes", "units", "chunk", "lesson_slugs"}; units and
    lessons repeated across programmes are stored once.
    """
    programmes, year_programmes, units = {}, {}, {}
    chunk: dict = {"units": {}, "lessons": {}, "mistakes": {}, "math": {}}
    lesson_slugs: dict[int, str] = {}

    for prog in subject["programmes"]:
        year_id = year_ids.get(prog["year"])
        if year_id is None:
            continue
        pid = stable_id("programme", prog["slug"])
        unit_ids = []
        for unit in prog["units"]:
            uid = stable_id("unit", unit["slug"])
            unit_ids.append(uid)
            lesson_ids = [stable_id("lesson", lesson["slug"]) for lesson in unit["lessons"]]
            unit_mistakes = []
            for lesson, lid in zip(unit["lessons"], lesson_ids):
                if lid not in chunk["lessons"]:
                    chunk["lessons"][lid] = _lesson(lesson, lid, chunk["mistakes"])
                    lesson_slugs[lid] = lesson["slug"]
                unit_mistakes += chunk["lessons"][lid]["mistakes"]
            if uid in chunk["units"]:  # the same unit reused in another year
                units[uid]["year"] = min(units[uid]["year"], prog["year"])
                continue
            chunk["units"][uid] = {
                "name": clean(unit["title"]),
                "description": clean(unit["description"]),
                "why": clean(unit["whyThisWhyNow"]),
                "prior": [clean(p) for p in unit["priorKnowledge"]],
                "threads": [clean(t) for t in unit["threads"]],
                "lessons": lesson_ids,
                "mistakes": unit_mistakes,
            }
            units[uid] = {
                "name": clean(unit["title"]),
                "chunk": chunk_id,
                "year": prog["year"],
                "lessons": lesson_ids,
            }
        programmes[pid] = {
            "title": subject["title"],
            "year_id": year_id,
            "year": prog["year"],
            "units": [{"choice": None, "options": [uid]} for uid in unit_ids],
        }
        year_programmes.setdefault(year_id, []).append(pid)

    return {
        "programmes": programmes,
        "year_programmes": year_programmes,
        "units": units,
        "chunk": chunk,
        "lesson_slugs": lesson_slugs,
    }


def _lesson(lesson: dict, lesson_id: int, mistakes: dict) -> dict:
    summary = lesson.get("summary") or {}
    mistake_ids = []
    for k, (statement, correction) in enumerate(summary.get("misconceptions", [])):
        mid = stable_id("misconception", f"{lesson['slug']}:{k}")
        statement = clean(statement)
        mistakes[mid] = {
            "belief": belief(statement),
            "statement": statement,
            "correction": clean(correction),
            "lesson": lesson_id,
        }
        mistake_ids.append(mid)
    return {
        "name": clean(lesson["title"]),
        "outcome": clean(summary.get("outcome")),
        "points": [clean(p) for p in summary.get("keyLearningPoints", [])],
        "keywords": [[clean(k), clean(d)] for k, d in summary.get("keywords", [])],
        "mistakes": mistake_ids,
    }
