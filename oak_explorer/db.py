"""Read-only queries over the Oak Curriculum Ontology SQLite release."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .text import belief, clean, programme_title, year_number

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "oak-curriculum.sqlite"
SECONDARY_KEY_STAGES = ("Key Stage 3", "Key Stage 4")

# Joins a lesson to the key stage of every unit it is taught in.
_LESSON_KS_JOIN = """
    JOIN lesson_inclusion li ON li.lesson_id = l.id
    JOIN unit_variant uv ON uv.id = li.unit_variant_id
    JOIN unit u ON u.id = uv.unit_id
    JOIN scheme s ON s.id = u.scheme_id
    JOIN key_stage ks ON ks.id = s.key_stage_id
"""


def db_path() -> Path:
    return Path(os.environ.get("OAK_DB", DEFAULT_DB))


@contextmanager
def connect():
    path = db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `uv run python scripts/download_data.py` first."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _ks_params() -> str:
    return ",".join("?" for _ in SECONDARY_KEY_STAGES)


def year_groups(conn) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT y.id, y.name, ks.name AS key_stage
        FROM year_group y JOIN key_stage ks ON ks.id = y.key_stage_id
        WHERE ks.name IN ({_ks_params()})
        """,
        SECONDARY_KEY_STAGES,
    ).fetchall()
    years = [
        {"id": r["id"], "number": year_number(r["name"]), "key_stage": r["key_stage"]}
        for r in rows
    ]
    return sorted(years, key=lambda y: y["number"] or 0)


def year_group(conn, year_id: int) -> dict | None:
    return next((y for y in year_groups(conn) if y["id"] == year_id), None)


def programmes_for_year(conn, year_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.id, p.name, t.name AS tier, eb.name AS exam_board,
               (SELECT COUNT(*) FROM unit_variant_inclusion uvi
                WHERE uvi.programme_id = p.id) AS unit_count
        FROM programme p
        LEFT JOIN tier t ON t.id = p.tier_id
        LEFT JOIN exam_board eb ON eb.id = p.exam_board_id
        WHERE p.year_group_id = ?
        """,
        (year_id,),
    ).fetchall()
    programmes = [
        {
            "id": r["id"],
            "title": programme_title(r["name"], r["tier"], r["exam_board"]),
            "unit_count": r["unit_count"],
        }
        for r in rows
    ]
    return sorted(programmes, key=lambda p: p["title"])


def programme(conn, programme_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT p.id, p.name, p.year_group_id, t.name AS tier, eb.name AS exam_board,
               y.name AS year_name
        FROM programme p
        JOIN year_group y ON y.id = p.year_group_id
        LEFT JOIN tier t ON t.id = p.tier_id
        LEFT JOIN exam_board eb ON eb.id = p.exam_board_id
        WHERE p.id = ?
        """,
        (programme_id,),
    ).fetchone()
    if row is None:
        return None

    units = []
    inclusions = conn.execute(
        """
        SELECT uvi.sequence_position, uvi.unit_variant_id, uvi.unit_variant_choice_id,
               uvc.name AS choice_name
        FROM unit_variant_inclusion uvi
        LEFT JOIN unit_variant_choice uvc ON uvc.id = uvi.unit_variant_choice_id
        WHERE uvi.programme_id = ?
        ORDER BY uvi.sequence_position
        """,
        (programme_id,),
    ).fetchall()
    for inc in inclusions:
        if inc["unit_variant_id"] is not None:
            units.append({"choice": None, "options": [_unit_summary(conn, inc["unit_variant_id"])]})
        else:
            option_ids = conn.execute(
                "SELECT unit_variant_id FROM unit_variant_choice_option "
                "WHERE unit_variant_choice_id = ?",
                (inc["unit_variant_choice_id"],),
            ).fetchall()
            units.append(
                {
                    "choice": clean(inc["choice_name"]),
                    "options": [_unit_summary(conn, o[0]) for o in option_ids],
                }
            )

    return {
        "id": row["id"],
        "title": programme_title(row["name"], row["tier"], row["exam_board"]),
        "year_id": row["year_group_id"],
        "year": year_number(row["year_name"]),
        "units": units,
    }


def _unit_summary(conn, unit_variant_id: int) -> dict:
    row = conn.execute(
        """
        SELECT uv.id, uv.name,
               (SELECT COUNT(*) FROM lesson_inclusion li
                WHERE li.unit_variant_id = uv.id) AS lesson_count
        FROM unit_variant uv WHERE uv.id = ?
        """,
        (unit_variant_id,),
    ).fetchone()
    lesson_ids = [
        r[0]
        for r in conn.execute(
            "SELECT lesson_id FROM lesson_inclusion WHERE unit_variant_id = ?",
            (unit_variant_id,),
        )
    ]
    return {
        "id": row["id"],
        "name": clean(row["name"]),
        "lesson_count": row["lesson_count"],
        "lesson_ids": lesson_ids,
    }


def unit(conn, unit_variant_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT uv.id, uv.name, u.id AS unit_id, u.description, u.why_this_why_now
        FROM unit_variant uv JOIN unit u ON u.id = uv.unit_id
        WHERE uv.id = ?
        """,
        (unit_variant_id,),
    ).fetchone()
    if row is None:
        return None

    lessons = conn.execute(
        """
        SELECT l.id, l.name, li.sequence_position
        FROM lesson_inclusion li JOIN lesson l ON l.id = li.lesson_id
        WHERE li.unit_variant_id = ?
        ORDER BY li.sequence_position
        """,
        (unit_variant_id,),
    ).fetchall()
    prior = conn.execute(
        "SELECT name FROM prior_knowledge_requirement WHERE unit_id = ? ORDER BY id",
        (row["unit_id"],),
    ).fetchall()
    threads = conn.execute(
        """
        SELECT t.name FROM unit_thread ut JOIN thread t ON t.id = ut.thread_id
        WHERE ut.unit_id = ? ORDER BY t.name
        """,
        (row["unit_id"],),
    ).fetchall()

    return {
        "id": row["id"],
        "name": clean(row["name"]),
        "description": clean(row["description"]),
        "why_this_why_now": clean(row["why_this_why_now"]),
        "lessons": [{"id": r["id"], "name": clean(r["name"])} for r in lessons],
        "prior_knowledge": [clean(r["name"]) for r in prior],
        "threads": [clean(r["name"]) for r in threads],
        "mistake_count": len(misconceptions_for_unit(conn, unit_variant_id)),
    }


def lesson(conn, lesson_id: int) -> dict | None:
    row = conn.execute("SELECT id, name FROM lesson WHERE id = ?", (lesson_id,)).fetchone()
    if row is None:
        return None

    outcome = conn.execute(
        "SELECT name FROM pupil_lesson_outcome WHERE lesson_id = ? LIMIT 1", (lesson_id,)
    ).fetchone()
    points = conn.execute(
        "SELECT name FROM key_learning_point WHERE lesson_id = ? ORDER BY id", (lesson_id,)
    ).fetchall()
    keywords = conn.execute(
        """
        SELECT k.name, k.description FROM lesson_keyword lk
        JOIN keyword k ON k.id = lk.keyword_id
        WHERE lk.lesson_id = ? ORDER BY k.name
        """,
        (lesson_id,),
    ).fetchall()
    units = conn.execute(
        """
        SELECT uv.id, uv.name FROM lesson_inclusion li
        JOIN unit_variant uv ON uv.id = li.unit_variant_id
        WHERE li.lesson_id = ? ORDER BY uv.id
        """,
        (lesson_id,),
    ).fetchall()

    return {
        "id": row["id"],
        "name": clean(row["name"]),
        "outcome": clean(outcome["name"]) if outcome else "",
        "key_points": [clean(r["name"]) for r in points],
        "keywords": [
            {"name": clean(r["name"]), "description": clean(r["description"])}
            for r in keywords
        ],
        "units": [{"id": r["id"], "name": clean(r["name"])} for r in units],
        "mistake_count": len(misconceptions_for_lesson(conn, lesson_id)),
    }


def neighbours(conn, unit_variant_id: int, lesson_id: int) -> tuple[int | None, int | None]:
    """Previous and next lesson ids within a unit variant."""
    ids = [
        r[0]
        for r in conn.execute(
            "SELECT lesson_id FROM lesson_inclusion WHERE unit_variant_id = ? "
            "ORDER BY sequence_position",
            (unit_variant_id,),
        )
    ]
    if lesson_id not in ids:
        return None, None
    i = ids.index(lesson_id)
    return (ids[i - 1] if i > 0 else None, ids[i + 1] if i + 1 < len(ids) else None)


def _misconception_cards(rows) -> list[dict]:
    cards = []
    for r in rows:
        statement = clean(r["statement"])
        cards.append(
            {
                "id": r["id"],
                "belief": belief(statement),
                "statement": statement,
                "correction": clean(r["correction"]),
                "lesson": clean(r["lesson_name"]),
                "lesson_id": r["lesson_id"],
            }
        )
    return cards


def misconceptions_for_lesson(conn, lesson_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT m.id, m.statement, m.correction, l.id AS lesson_id, l.name AS lesson_name
        FROM lesson_misconception lm
        JOIN misconception m ON m.id = lm.misconception_id
        JOIN lesson l ON l.id = lm.lesson_id
        WHERE lm.lesson_id = ? ORDER BY m.id
        """,
        (lesson_id,),
    ).fetchall()
    return _misconception_cards(rows)


def misconceptions_for_unit(conn, unit_variant_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT m.id, m.statement, m.correction, l.id AS lesson_id, l.name AS lesson_name
        FROM lesson_inclusion li
        JOIN lesson l ON l.id = li.lesson_id
        JOIN lesson_misconception lm ON lm.lesson_id = l.id
        JOIN misconception m ON m.id = lm.misconception_id
        WHERE li.unit_variant_id = ?
        ORDER BY li.sequence_position, m.id
        """,
        (unit_variant_id,),
    ).fetchall()
    return _misconception_cards(rows)


def search(conn, query: str, limit: int = 25) -> dict:
    """Find KS3–KS4 units and lessons whose name or keywords match."""
    query = query.strip()
    if len(query) < 2:
        return {"units": [], "lessons": []}
    like = f"%{query}%"

    units = conn.execute(
        f"""
        SELECT uv.id, uv.name, MIN(y.name) AS year_name
        FROM unit_variant uv
        JOIN unit u ON u.id = uv.unit_id
        JOIN scheme s ON s.id = u.scheme_id
        JOIN key_stage ks ON ks.id = s.key_stage_id
        LEFT JOIN unit_variant_inclusion uvi ON uvi.unit_variant_id = uv.id
        LEFT JOIN programme p ON p.id = uvi.programme_id
        LEFT JOIN year_group y ON y.id = p.year_group_id
        WHERE ks.name IN ({_ks_params()}) AND uv.name LIKE ?
        GROUP BY uv.name
        ORDER BY uv.name
        LIMIT ?
        """,
        (*SECONDARY_KEY_STAGES, like, limit),
    ).fetchall()

    lessons = conn.execute(
        f"""
        SELECT l.id, l.name, MIN(uv.name) AS unit_name, MIN(uv.id) AS unit_id,
               MAX(l.name LIKE ?) AS name_match
        FROM lesson l
        {_LESSON_KS_JOIN}
        LEFT JOIN lesson_keyword lk ON lk.lesson_id = l.id
        LEFT JOIN keyword k ON k.id = lk.keyword_id
        WHERE ks.name IN ({_ks_params()}) AND (l.name LIKE ? OR k.name LIKE ?)
        GROUP BY l.id
        ORDER BY name_match DESC, l.name
        LIMIT ?
        """,
        (like, *SECONDARY_KEY_STAGES, like, like, limit),
    ).fetchall()

    return {
        "units": [
            {"id": r["id"], "name": clean(r["name"]), "year": year_number(r["year_name"] or "")}
            for r in units
        ],
        "lessons": [
            {
                "id": r["id"],
                "name": clean(r["name"]),
                "unit": clean(r["unit_name"]),
                "unit_id": r["unit_id"],
            }
            for r in lessons
        ],
    }
