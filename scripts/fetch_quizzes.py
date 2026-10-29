"""Fetch starter and exit quizzes from Oak's Open API into data/oak-quizzes.json.

Needs an API key in the OAK_API_KEY environment variable. Uses the bulk
programme endpoint (up to 300 lessons per request), so each programme costs
one or two requests against the 1,000-per-hour limit.

Usage:
    uv run python scripts/fetch_quizzes.py                      # default selection
    uv run python scripts/fetch_quizzes.py --years 7 8 9         # every subject in these years
    uv run python scripts/fetch_quizzes.py maths-secondary-year-7 ...
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from oak_explorer.oak_api import OakAPI, OakAPIError, Unavailable  # noqa: E402

# Default selection: every subject in Years 7–9, plus GCSE Computer Science (OCR).
DEFAULT_YEARS = (7, 8, 9)
EXTRA_PROGRAMMES = (
    "computing-secondary-year-10-gcse-ocr",
    "computing-secondary-year-11-gcse-ocr",
)
DEST = ROOT / "data" / "oak-quizzes.json"


def programmes_for_years(api: OakAPI, years) -> list[str]:
    """Programme slugs for the given years across all subjects."""
    pattern = re.compile(rf"-year-({'|'.join(str(y) for y in years)})$")
    found = []
    for subject in api.get_one("/subjects"):
        found += [p for p in api.get_one(f"/subjects/{subject}/programmes") if pattern.search(p)]
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("programmes", nargs="*",
                        help="Oak API programme slugs (see GET /subjects/{subject}/programmes)")
    parser.add_argument("--years", nargs="+", type=int,
                        help="fetch every subject's programmes for these years")
    args = parser.parse_args()

    try:
        api = OakAPI()
        programmes = list(args.programmes)
        if args.years or not programmes:
            programmes += programmes_for_years(api, args.years or DEFAULT_YEARS)
            if not args.programmes and not args.years:
                programmes += EXTRA_PROGRAMMES

        quizzes: dict[str, dict] = {}
        for programme in programmes:
            try:
                lessons = api.get_all(f"/programmes/{programme}/questions?limit=300")
            except Unavailable:
                lessons = []
            for lesson in lessons:
                quizzes[lesson["lessonSlug"]] = {
                    "starter": lesson.get("starterQuiz") or [],
                    "exit": lesson.get("exitQuiz") or [],
                }
            print(f"{programme}: {len(lessons)} lessons")
    except OakAPIError as exc:
        print(exc, file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(quizzes, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(quizzes):,} lesson quizzes to {DEST} ({api.requests} requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
