"""Fetch whole subjects from Oak's Open API into data/oak-subjects.json.

For subjects the curriculum ontology doesn't cover yet (RE and RSHE/PSHE), this collects
the same structure the explorer shows for the others: programmes per year, units in
teaching order with prior knowledge and threads, and lessons with their outcome, key
learning points, keywords and misconceptions. Quizzes come from fetch_quizzes.py.

Roughly 1 request per unit plus 1 per lesson (a few hundred for both subjects) against
the 1,000-per-hour limit. Needs OAK_API_KEY.

If you have Oak's bulk-download file for a subject in data/, the build uses that instead and
this script isn't needed for it.

Usage:
    uv run python scripts/fetch_subjects.py
    uv run python scripts/fetch_subjects.py --subjects religious-education --years 7 8 9
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from oak_explorer.bulk import lesson_summary as summary_fields  # noqa: E402
from oak_explorer.oak_api import OakAPI, OakAPIError, Unavailable  # noqa: E402

DEST = ROOT / "data" / "oak-subjects.json"
DEFAULT_SUBJECTS = {"religious-education": "Religious Education", "rshe-pshe": "RSHE (PSHE)"}
DEFAULT_YEARS = (7, 8, 9)


def lesson_summary(api: OakAPI, slug: str) -> dict | None:
    try:
        return summary_fields(api.get_one(f"/lessons/{slug}/summary"))
    except Unavailable:  # e.g. blocked for copyright: keep the title, skip the detail
        return None


def fetch_subject(api: OakAPI, slug: str, title: str, years) -> dict:
    pattern = re.compile(rf"-year-({'|'.join(str(y) for y in years)})$")
    summaries: dict[str, dict | None] = {}
    programmes = []
    for programme in api.get_one(f"/subjects/{slug}/programmes"):
        match = pattern.search(programme)
        if not match:
            continue
        units = []
        for u in sorted(api.get_one(f"/programmes/{programme}/units"), key=lambda u: u["unitOrder"]):
            try:
                unit = api.get_one(f"/units/{u['unitSlug']}/summary")
            except Unavailable:
                continue
            lessons = []
            for lesson in sorted(unit.get("unitLessons") or [], key=lambda x: x.get("lessonOrder") or 0):
                if lesson.get("state") != "published":
                    continue
                if lesson["lessonSlug"] not in summaries:
                    summaries[lesson["lessonSlug"]] = lesson_summary(api, lesson["lessonSlug"])
                lessons.append({"slug": lesson["lessonSlug"], "title": lesson["lessonTitle"],
                                "summary": summaries[lesson["lessonSlug"]]})
            if lessons:
                units.append({
                    "slug": unit["unitSlug"],
                    "title": unit["unitTitle"],
                    "description": unit.get("description") or "",
                    "whyThisWhyNow": unit.get("whyThisWhyNow") or "",
                    "priorKnowledge": unit.get("priorKnowledgeRequirements") or [],
                    "threads": [t["title"] for t in unit.get("threads") or []],
                    "lessons": lessons,
                })
        print(f"{programme}: {len(units)} units, {sum(len(u['lessons']) for u in units)} lessons")
        programmes.append({"slug": programme, "year": int(match.group(1)), "units": units})
    return {"slug": slug, "title": title, "programmes": programmes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subjects", nargs="+", default=list(DEFAULT_SUBJECTS),
                        help="Oak API subject slugs")
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    args = parser.parse_args()

    try:
        api = OakAPI()
        subjects = [
            fetch_subject(api, slug, DEFAULT_SUBJECTS.get(slug, slug.replace("-", " ").title()), args.years)
            for slug in args.subjects
        ]
    except OakAPIError as exc:
        print(exc, file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps({"subjects": subjects}, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(subjects)} subjects to {DEST} ({api.requests} requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
