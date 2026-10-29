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

### Quizzes from Oak's Open API

`scripts/fetch_quizzes.py` downloads starter and exit quizzes (multiple choice, short answer,
matching and ordering) into `data/oak-quizzes.json`, and the static build adds them to the
matching lessons. It needs an Oak Open API key in `OAK_API_KEY`. By default it fetches every
subject for Years 7–9 plus GCSE Computer Science (OCR) for Years 10–11; pass other programme slugs to fetch more.

```bash
uv run python scripts/fetch_quizzes.py
uv run python scripts/build_static.py
```

### Subjects the ontology lacks (RE, RSHE/PSHE)

The curriculum ontology doesn't cover Religious Education or RSHE/PSHE yet. If their Oak
bulk-download files are in `data/` (`religious-education-secondary.json`,
`rshe-pshe-secondary.json`), the build uses them directly for Years 7–9. Otherwise
`scripts/fetch_subjects.py` builds them from the API: programmes per year, units in
teaching order (with prior knowledge and threads) and lessons (outcome, key learning points,
keywords, misconceptions). It saves `data/oak-subjects.json`, which the static build merges in
alongside the other subjects; their quizzes come from `fetch_quizzes.py` as usual.

```bash
uv run python scripts/fetch_subjects.py    # Years 7–9 of RE and RSHE/PSHE, a few hundred requests
uv run python scripts/fetch_quizzes.py
uv run python scripts/build_static.py
```

### Oak bulk-download files

Files from Oak's [bulk download](https://open-api.thenational.academy/bulk-download)
(e.g. `data/spanish-secondary.json`, `data/computing-secondary.json`) are picked up by the build
automatically. They add teacher tips (shown in the board view's "Teacher notes" panel, toggled with
the button or `T`), content guidance with the supervision level (shown as a warning on the lesson
page), and each lesson's own keyword definitions, which replace the ontology's shared ones. Every
lesson also links to its page on Oak's website.

### Interactive lessons

`static_site/lessons/` holds hand-built, animated versions of single lessons, copied as they are
into `site/lessons/`. A lesson page links to one when its slug is listed in `INTERACTIVE` in
`static_site/index.html`. So far there is one: Year 9 Computing's
[Representing sound with binary data](static_site/lessons/representing-sound-with-binary-data.html),
built from the lesson's video transcript. It runs Oak's starter quiz, eight animated steps (sound
waves, microphones and speakers, sampling, sample rate and bit depth with sounds to compare, sound
to bits, mono/stereo channels, a file-size calculator), each with a quick check, then Oak's exit
quiz. The quizzes are read from `site/data/`, and scores and "done" are shared with the main site.

Questions that need an image are skipped unless the image can be downloaded from
`cloudinary-res.thenational.academy`.

Maths is written in LaTeX (`$$3\over 5$$`); the build converts it to MathML, which browsers
render natively.

**Board view.** Each quiz can be shown on one screen for the whole class ("Show on board" on a
lesson page). Every question stays visible: the page picks the column count and text size that
fit the screen. Reveal answers one at a time with →, ↓ or Space (← or ↑ to step back,
Home/End for none/all), or all at once with "Show all answers".

## Deploying to Netlify

The built site is committed in `site/`, and `netlify.toml` tells Netlify to publish that folder
as-is. There is no build step on Netlify, so it needs no Python, no database download and no
API key.

1. In Netlify: **Add new site → Import an existing project → GitHub**, and pick this repository.
2. Choose the branch to deploy. Netlify reads the publish folder from `netlify.toml`; leave
   the build command empty.
3. Deploy. Every push to that branch redeploys automatically.

To update the content, rebuild locally (or in a Claude session that has the API key) and commit
`site/`:

```bash
uv run python scripts/fetch_quizzes.py     # optional: refresh quizzes from Oak's API
uv run python scripts/build_static.py      # rebuilds site/ (takes a few minutes)
uv run pytest                              # checks site/ is complete and up to date
git add site && git commit -m "Rebuild site"
```

After editing only `static_site/index.html`, `uv run python scripts/build_static.py --page-only`
is enough. The tests fail if `site/index.html` is out of date with its source.

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
  (e.g. "cell" in Biology shows the spreadsheet definition, and "channel" in Computing a netball
  one). Subjects with a bulk-download file in `data/` use each lesson's own definitions instead.
- Roughly a quarter of misconception corrections are written for teachers rather than pupils. Each
  answer links back to its lesson for context.
- KS3 science programmes are stored under the "Biology" subject.

## Licences

Curriculum data © Oak National Academy, under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
htmx (`oak_explorer/static/htmx.min.js`) is © Big Sky Software, under the BSD Zero-Clause licence.
This project is not an official Oak product.
