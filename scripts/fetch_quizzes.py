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
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://open-api.thenational.academy/api/v0"
# Default selection: every subject in Years 7–9, plus GCSE Computer Science (OCR).
DEFAULT_YEARS = (7, 8, 9)
EXTRA_PROGRAMMES = (
    "computing-secondary-year-10-gcse-ocr",
    "computing-secondary-year-11-gcse-ocr",
)
# Quizzes exist for these, but the ontology has no lessons to attach them to.
SKIP_SUBJECTS = {"religious-education", "rshe-pshe"}
DEST = Path(__file__).resolve().parent.parent / "data" / "oak-quizzes.json"


def get(url: str, key: str) -> tuple[object, str | None]:
    """GET a JSON resource; returns the body and the rel="next" URL, if any."""
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {key}", "User-Agent": "oak-explorer/0.1"}
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req) as resp:
                link = resp.headers.get("Link", "")
                match = re.search(r'<([^>]+)>;\s*rel="next"', link)
                if int(resp.headers.get("X-RateLimit-Remaining", "1")) < 5:
                    sys.exit("Oak API rate limit nearly used up; try again in an hour.")
                return json.load(resp), match.group(1) if match else None
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):  # unknown programme, or blocked for copyright
                return [], None
            if exc.code == 429 or exc.code >= 500:
                time.sleep(2**attempt)
                continue
            raise
    raise RuntimeError(f"Giving up on {url}")


def programmes_for_years(years, key: str) -> tuple[list[str], int]:
    """Programme slugs for the given years across all subjects, and the requests used."""
    subjects, _ = get(f"{API}/subjects", key)
    pattern = re.compile(rf"-year-({'|'.join(str(y) for y in years)})$")
    found = []
    for subject in subjects:
        if subject in SKIP_SUBJECTS:
            continue
        programmes, _ = get(f"{API}/subjects/{subject}/programmes", key)
        found += [p for p in programmes if pattern.search(p)]
    return found, len(subjects) + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("programmes", nargs="*",
                        help="Oak API programme slugs (see GET /subjects/{subject}/programmes)")
    parser.add_argument("--years", nargs="+", type=int,
                        help="fetch every subject's programmes for these years")
    args = parser.parse_args()

    key = os.environ.get("OAK_API_KEY")
    if not key:
        print("Set OAK_API_KEY to your Oak Open API key.", file=sys.stderr)
        return 1

    programmes, requests = list(args.programmes), 0
    if args.years or not programmes:
        found, requests = programmes_for_years(args.years or DEFAULT_YEARS, key)
        programmes += found
        if not args.programmes and not args.years:
            programmes += EXTRA_PROGRAMMES

    quizzes: dict[str, dict] = {}
    for programme in programmes:
        url: str | None = f"{API}/programmes/{programme}/questions?limit=300"
        count = 0
        while url:
            lessons, url = get(url, key)
            requests += 1
            for lesson in lessons:
                quizzes[lesson["lessonSlug"]] = {
                    "starter": lesson.get("starterQuiz") or [],
                    "exit": lesson.get("exitQuiz") or [],
                }
                count += 1
        print(f"{programme}: {count} lessons")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(quizzes, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(quizzes):,} lesson quizzes to {DEST} ({requests} requests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
