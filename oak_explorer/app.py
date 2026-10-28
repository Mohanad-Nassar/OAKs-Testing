"""Oak Explorer: a pupil-friendly view of Oak's KS3–KS4 curriculum."""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db

HERE = Path(__file__).resolve().parent

app = FastAPI(title="Oak Explorer")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

Scope = Literal["lesson", "unit"]


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def render(request: Request, name: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request, name, context)


def not_found(what: str):
    raise HTTPException(status_code=404, detail=f"{what} not found")


@app.exception_handler(FileNotFoundError)
async def missing_data(request: Request, exc: FileNotFoundError):
    return render(request, "missing_data.html", message=str(exc))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with db.connect() as conn:
        years = db.year_groups(conn)
    return render(request, "home.html", years=years)


@app.get("/year/{year_id}", response_class=HTMLResponse)
def year(request: Request, year_id: int):
    with db.connect() as conn:
        year = db.year_group(conn, year_id) or not_found("Year")
        programmes = db.programmes_for_year(conn, year_id)
    return render(request, "year.html", year=year, programmes=programmes)


@app.get("/programme/{programme_id}", response_class=HTMLResponse)
def programme(request: Request, programme_id: int):
    with db.connect() as conn:
        programme = db.programme(conn, programme_id) or not_found("Programme")
    return render(request, "programme.html", programme=programme)


@app.get("/unit/{unit_id}", response_class=HTMLResponse)
def unit(request: Request, unit_id: int, p: int | None = None):
    with db.connect() as conn:
        unit = db.unit(conn, unit_id) or not_found("Unit")
        programme = db.programme(conn, p) if p else None
    return render(request, "unit.html", unit=unit, programme=programme)


@app.get("/lesson/{lesson_id}", response_class=HTMLResponse)
def lesson(request: Request, lesson_id: int, u: int | None = None, p: int | None = None):
    with db.connect() as conn:
        lesson = db.lesson(conn, lesson_id) or not_found("Lesson")
        unit_ids = [x["id"] for x in lesson["units"]]
        unit_id = u if u in unit_ids else (unit_ids[0] if unit_ids else None)
        unit = db.unit(conn, unit_id) if unit_id else None
        prev_id, next_id = db.neighbours(conn, unit_id, lesson_id) if unit_id else (None, None)
    return render(
        request,
        "lesson.html",
        lesson=lesson,
        unit=unit,
        programme_id=p,
        prev_id=prev_id,
        next_id=next_id,
    )


@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    with db.connect() as conn:
        results = db.search(conn, q)
    template = "_search_results.html" if is_htmx(request) else "search.html"
    return render(request, template, q=q, results=results)


def _cards(conn, scope: Scope, item_id: int) -> tuple[str, list[dict]]:
    if scope == "lesson":
        item = db.lesson(conn, item_id) or not_found("Lesson")
        return item["name"], db.misconceptions_for_lesson(conn, item_id)
    item = db.unit(conn, item_id) or not_found("Unit")
    return item["name"], db.misconceptions_for_unit(conn, item_id)


@app.get("/check/{scope}/{item_id}", response_class=HTMLResponse)
def check(
    request: Request,
    scope: Scope,
    item_id: int,
    i: int = Query(0, ge=0),
    score: int = Query(0, ge=0),
    asked: int = Query(0, ge=0),
):
    with db.connect() as conn:
        title, cards = _cards(conn, scope, item_id)
    context = dict(
        scope=scope,
        item_id=item_id,
        title=title,
        total=len(cards),
        i=i,
        score=score,
        asked=asked,
        card=cards[i] if i < len(cards) else None,
    )
    template = "_check_card.html" if is_htmx(request) else "check.html"
    return render(request, template, **context)


@app.get("/check/{scope}/{item_id}/answer", response_class=HTMLResponse)
def check_answer(
    request: Request,
    scope: Scope,
    item_id: int,
    i: int = Query(..., ge=0),
    score: int = Query(0, ge=0),
    asked: int = Query(0, ge=0),
    choice: Literal["true", "false", "reveal"] = "reveal",
):
    with db.connect() as conn:
        _, cards = _cards(conn, scope, item_id)
    if i >= len(cards):
        not_found("Card")
    # Every misconception is a false belief, so "false" is always right.
    correct = choice == "false" if choice != "reveal" else None
    if correct is not None:
        asked += 1
        score += int(correct)
    return render(
        request,
        "_check_answer.html",
        scope=scope,
        item_id=item_id,
        total=len(cards),
        i=i,
        score=score,
        asked=asked,
        card=cards[i],
        choice=choice,
        correct=correct,
    )
