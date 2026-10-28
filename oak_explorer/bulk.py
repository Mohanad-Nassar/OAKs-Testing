"""Read Oak's bulk-download files (https://open-api.thenational.academy/bulk-download).

Each file is one subject sequence (e.g. data/spanish-secondary.json) following Oak's bulk
export schema. The explorer takes the lesson details its other sources lack: teacher tips
and content guidance with the supervision level.
"""

import json
from pathlib import Path

from .text import clean


def is_bulk_file(path: Path) -> bool:
    if path.suffix != ".json" or path.name == "schema.json" or path.name.startswith("oak-"):
        return False
    with path.open(encoding="utf-8") as f:
        return '"sequenceSlug"' in f.read(200)


def lesson_extras(lesson: dict) -> dict:
    """Teacher tips and content guidance for one bulk-file lesson (empty fields left out)."""
    extras: dict = {}
    tips = [clean(t.get("teacherTip")) for t in lesson.get("teacherTips") or []]
    if tips := [t for t in tips if t]:
        extras["tips"] = tips
    guidance = [
        {
            "label": clean(g.get("contentGuidanceLabel")),
            "description": clean(g.get("contentGuidanceDescription")),
        }
        for g in lesson.get("contentGuidance") or []
        if g.get("contentGuidanceLabel")
    ]
    if guidance:
        extras["guidance"] = guidance
    if lesson.get("supervisionLevel"):
        extras["supervision"] = clean(lesson["supervisionLevel"])
    return extras


def load_extras(folder: Path) -> dict[str, dict]:
    """Lesson slug → extras, from every bulk file in a folder."""
    extras: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        if not is_bulk_file(path):
            continue
        for lesson in json.loads(path.read_text(encoding="utf-8"))["lessons"]:
            if found := lesson_extras(lesson):
                extras.setdefault(lesson["lessonSlug"], found)
    return extras


def lesson_summary(lesson: dict) -> dict:
    """Outcome, key learning points, keywords and misconceptions from a lesson record.

    Oak's bulk files and its GET /lessons/{lesson}/summary endpoint use the same field names.
    """
    return {
        "outcome": lesson.get("pupilLessonOutcome") or "",
        "keyLearningPoints": [k["keyLearningPoint"] for k in lesson.get("keyLearningPoints") or []],
        "keywords": [[k["keyword"], k.get("description") or ""] for k in lesson.get("lessonKeywords") or []],
        "misconceptions": [
            [m["misconception"], m.get("response") or ""]
            for m in lesson.get("misconceptionsAndCommonMistakes") or []
        ],
    }


def subject_from_bulk(data: dict, title: str, years) -> dict:
    """A bulk file as a subject in the shape scripts/fetch_subjects.py saves (one programme per year)."""
    lessons = {lesson["lessonSlug"]: lesson for lesson in data["lessons"]}
    programmes = []
    for year in years:
        units = []
        for unit in data["sequence"]:  # already in teaching order
            if unit.get("year") != year:
                continue
            unit_lessons = [
                {"slug": ul["lessonSlug"], "title": ul["lessonTitle"],
                 "summary": lesson_summary(lessons[ul["lessonSlug"]]) if ul["lessonSlug"] in lessons else None}
                for ul in sorted(unit.get("unitLessons") or [], key=lambda x: x.get("lessonOrder") or 0)
                if ul.get("state") == "published"
            ]
            if unit_lessons:
                units.append({
                    "slug": unit["unitSlug"],
                    "title": unit["unitTitle"],
                    "description": unit.get("description") or "",
                    "whyThisWhyNow": unit.get("whyThisWhyNow") or "",
                    "priorKnowledge": unit.get("priorKnowledgeRequirements") or [],
                    "threads": [t["title"] for t in unit.get("threads") or []],
                    "lessons": unit_lessons,
                })
        if units:
            programmes.append({"slug": f"{data['sequenceSlug']}-year-{year}", "year": year, "units": units})
    return {"slug": data["sequenceSlug"].removesuffix("-secondary").removesuffix("-primary"),
            "title": title, "programmes": programmes}
