"""Convert Oak Open API quiz questions into the compact shape the explorer page uses.

Output question shapes (all have "type" and "q", the question text, and may have "img"):

    {"type": "mc", "options": [{"text": ...} | {"img": ...}], "correct": [0, 2]}
    {"type": "short", "accept": ["function", "a function"]}
    {"type": "match", "pairs": [["list", "a collection of values"], ...]}
    {"type": "order", "items": ["first", "second", ...]}
"""

import re
from collections.abc import Callable

from latex2mathml.converter import convert

# Resolves an Oak image URL to a local path, or None if it isn't available.
ImageResolver = Callable[[str], str | None]


class MissingImage(Exception):
    pass


def _image(content: dict, resolve: ImageResolver) -> str:
    path = resolve(content["url"])
    if path is None:
        raise MissingImage(content["url"])
    return path


def _option(answer: dict, resolve: ImageResolver) -> dict:
    if answer.get("type") == "image":
        return {"img": _image(answer["content"], resolve)}
    return {"text": answer["content"]}


def _text(item: dict) -> str:
    if item.get("type") != "text":
        raise MissingImage("non-text item")
    return item["content"]


def convert_question(raw: dict, resolve: ImageResolver) -> dict | None:
    """Convert one API question; returns None if it can't be shown (e.g. a missing image)."""
    try:
        out: dict = {"q": raw["question"]}
        if raw.get("questionImage"):
            out["img"] = _image(raw["questionImage"], resolve)
        answers = raw.get("answers") or []
        kind = raw["questionType"]
        if kind == "multiple-choice":
            out["type"] = "mc"
            out["options"] = [_option(a, resolve) for a in answers]
            out["correct"] = [i for i, a in enumerate(answers) if not a.get("distractor")]
            if not out["correct"]:
                return None
        elif kind == "short-answer":
            out["type"] = "short"
            out["accept"] = [a["content"].strip() for a in answers if a.get("content", "").strip()]
            if not out["accept"]:
                return None
        elif kind == "match":
            out["type"] = "match"
            out["pairs"] = [[_text(a["matchOption"]), _text(a["correctChoice"])] for a in answers]
        elif kind == "order":
            out["type"] = "order"
            out["items"] = [_text(a) for a in sorted(answers, key=lambda a: a["order"])]
        else:
            return None
        return out
    except (MissingImage, KeyError, TypeError):
        return None


def convert_quiz(raw: dict, resolve: ImageResolver) -> dict:
    """{"starter": [...], "exit": [...]} from the API → the same keys, converted."""
    return {
        name: [q for q in (convert_question(x, resolve) for x in raw.get(name, [])) if q]
        for name in ("starter", "exit")
    }


MATH = re.compile(r"\$\$(.+?)\$\$", re.S)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def math_segments(quiz: dict) -> set[str]:
    """Every $$LaTeX$$ segment used in a converted quiz."""
    return {m for text in _strings(quiz) for m in MATH.findall(text)}


def to_mathml(latex: str) -> str | None:
    """MathML for a LaTeX segment, which browsers render natively; None if it can't be converted."""
    try:
        return convert(latex)
    except Exception:  # latex2mathml raises a variety of parser errors
        return None
