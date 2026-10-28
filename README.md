# Oak Explorer

A pupil-friendly explorer for the KS3–KS4 (Years 7–11) curriculum, built on Oak National Academy's
open [Oak Curriculum Ontology](https://github.com/oaknational/oak-curriculum-ontology).

Pupils can:

- **Browse** by year → subject → unit → lesson, in teaching order (GCSE exam-board and tier versions included).
- **Search** units and lessons by name or keyword as they type.
- **Read a lesson page** with what they'll be able to do by the end, key learning points, keywords and
  definitions, plus what they need to know before the unit starts.
- **Spot the mistake**: answer true-or-false on common misconceptions for a lesson or a whole unit,
  then see how to get it right.
- **Track progress** by marking lessons as done. This is stored only in the browser (no accounts),
  and units show progress bars.

No AI is involved: everything shown comes straight from Oak's published data.

## Running it

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python scripts/download_data.py   # fetches oak-curriculum.sqlite (~41 MB) into data/
uv run uvicorn oak_explorer.app:app --reload
```

Then open http://127.0.0.1:8000.

To pin a specific Oak release: `uv run python scripts/download_data.py --tag v0.1.3 --force`.
Set `OAK_DB=/path/to/oak-curriculum.sqlite` to use a database somewhere else.

## Static version (no server)

`scripts/build_static.py` exports the Year 7–11 data to JSON files (~12 MB) and copies
`static_site/index.html`, a browser-only version of the app, into `site/`. That folder can be
hosted anywhere static files are served (it's what the hosted demo uses).

```bash
uv run python scripts/build_static.py
cd site && python -m http.server 8000
```

## Tests

```bash
uv run pytest
```

The tests use a small handmade database, so they don't need the download.

## How it works

| Piece | What it does |
|---|---|
| `scripts/download_data.py` | Downloads the SQLite release from GitHub and checks it opens |
| `oak_explorer/db.py` | Read-only SQL queries over the Oak schema |
| `oak_explorer/text.py` | Tidies teacher-facing text for pupils (e.g. turns "Pupils may think that X" into a true/false statement X) |
| `oak_explorer/app.py` | FastAPI routes; HTMX powers live search and the flashcards |
| `oak_explorer/static/progress.js` | Lesson progress in `localStorage` |

htmx is bundled in `static/` so the app works offline.

## Known data quirks (upstream)

The data is an early release (v0.1.x), so expect some rough edges:

- Keywords are de-duplicated by name across subjects, so a definition can come from another subject
  (e.g. "cell" in Biology shows the spreadsheet definition).
- Roughly a quarter of misconception corrections are written for teachers rather than pupils. Each
  answer links back to its lesson for context.
- KS3 science programmes are stored under the "Biology" subject.

## Licences

Curriculum data © Oak National Academy, under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
htmx (`oak_explorer/static/htmx.min.js`) is © Big Sky Software, under the BSD Zero-Clause licence.
This project is not an official Oak product.
