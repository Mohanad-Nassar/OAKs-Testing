# Working on Oak Explorer

Notes for AI agents (and people) changing this repo. The README explains the code; this file
explains how changes get previewed and published.

## How the site is hosted

- The site is static and **pre-built**: `site/` is committed, and `netlify.toml` tells Netlify to
  publish that folder as-is. Netlify runs no build, so whatever is committed in `site/` is
  exactly what goes online.
- Netlify project: **oak-explorer**. Production deploys from **`main`**.
- Every production deploy costs **15 Netlify credits**. Deploy previews cost **0 credits**.
  So: never push to `main` and never merge a pull request unless the user explicitly asks.
  Batch changes on a branch and let the user merge once.

## Getting a preview link (free)

Netlify builds a **Deploy Preview** for every pull request into `main`, and rebuilds it on every
push to that pull request's branch. The link always has this form:

    https://deploy-preview-<PR number>--oak-explorer.netlify.app

Steps:

1. **Work on a branch, never on `main`.** Check whether a pull request into `main` is already
   open for your branch. If one is, pushing to the branch is all you need to update its preview.
2. **Rebuild `site/` from source.** Don't edit files in `site/` by hand.
   - After editing only `static_site/index.html` or `static_site/lessons/*`:
     `uv run python scripts/build_static.py --page-only`
   - After changing data or build code: `uv run python scripts/build_static.py` (a few minutes;
     it needs `data/oak-curriculum.sqlite` from `scripts/download_data.py`, and quizzes from
     `scripts/fetch_quizzes.py`, which needs `OAK_API_KEY`).
3. **Run `uv run pytest`.** The tests fail if `site/` is incomplete or out of date with its
   source. Fix them before pushing.
4. **Check it yourself before pushing.** The agent container usually can't reach
   `*.netlify.app`, so serve the folder the same way Netlify does and test it in a browser
   (Playwright and Chromium are installed):
   `cd site && python3 -m http.server 8000`, then open `http://127.0.0.1:8000/`.
   Look for JS errors, failed requests (404s) and garbled characters.
5. **Commit, including `site/`, and push the branch.**
6. **If there is no pull request yet, open one** from your branch into `main` (GitHub MCP tools,
   e.g. `create_pull_request`). Say in the description that it's for a preview and that merging
   publishes to production.
7. **Wait for Netlify without polling.** Subscribe to the pull request's activity
   (`subscribe_pr_activity`). Netlify reports back in two ways:
   - a commit status named `netlify/oak-explorer/deploy-preview`, going from "pending" to
     "Deploy Preview ready!" (its `target_url` is the preview link), and
   - a comment by `netlify[bot]` on the pull request, with the link and a QR code for phones.
   A build usually takes under a minute, because there's nothing to build.
8. **Give the user the preview link.** Tell them it's free and that merging the pull request is
   what puts it live.

If a preview fails, read the deploy log linked from the status or bot comment. The usual cause is
a missing or broken file in `site/`.

## Current state

- Working branch: `claude/zealous-cori-bqi2de`
- Open pull request: #1 (`claude/zealous-cori-bqi2de` into `main`)
- Preview: https://deploy-preview-1--oak-explorer.netlify.app

Update this section when a pull request is merged or a new one is opened.

## Working alongside other sessions

- Only one session should push to a branch at a time. Before starting, run `git fetch` and look
  at recent commits. If another session is active on the branch, coordinate through the user or
  use a separate branch (and pull request, which gets its own preview number).
- Pull before pushing. Never force-push a shared branch.

## Other things to know

- The Oak Open API key is read from `OAK_API_KEY`. It's set in the cloud environment's settings,
  not in the repo, and only reaches sessions started after it was saved. Never ask for the key
  in chat or commit it.
- Oak bulk-download files in `data/` (e.g. `computing-secondary.json`) include lesson transcripts,
  teacher tips and content guidance, and need no API key.
- Lesson content is © Oak National Academy under the Open Government Licence v3.0. Keep the
  attribution in the site footer, and don't republish lessons Oak marks as restricted.
