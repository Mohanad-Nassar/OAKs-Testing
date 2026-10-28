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
