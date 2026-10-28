"""Download the Oak Curriculum Ontology SQLite release into data/.

Usage:
    python scripts/download_data.py            # latest release
    python scripts/download_data.py --tag v0.1.3
"""

import argparse
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = "oaknational/oak-curriculum-ontology"
ASSET = "oak-curriculum.sqlite"
DEST = Path(__file__).resolve().parent.parent / "data" / ASSET


def release_url(tag: str | None) -> str:
    if tag:
        return f"https://github.com/{REPO}/releases/download/{tag}/{ASSET}"
    return f"https://github.com/{REPO}/releases/latest/download/{ASSET}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="release tag to download (default: latest)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing file")
    args = parser.parse_args()

    if DEST.exists() and not args.force:
        print(f"{DEST} already exists; pass --force to re-download.")
        return 0

    url = release_url(args.tag)
    print(f"Downloading {url}")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=DEST.parent, suffix=".part", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        with urllib.request.urlopen(url) as resp:
            shutil.copyfileobj(resp, tmp)

    try:
        with sqlite3.connect(tmp_path) as conn:
            lessons = conn.execute("SELECT COUNT(*) FROM lesson").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        tmp_path.unlink(missing_ok=True)
        print(f"Downloaded file is not a valid Oak database: {exc}", file=sys.stderr)
        return 1

    tmp_path.replace(DEST)
    print(f"Saved {DEST} ({lessons:,} lessons)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
