"""Tidy Oak's teacher-facing text for pupils."""

import re

# "Pupils may think that ...", "Some children believe ...", "Thinking that ..."
_BELIEF = re.compile(
    r"^(?:(?:some\s+)?(?:pupils|children|students)\s+"
    r"(?:(?:may|might|often|will|can|sometimes|commonly|frequently)\s+)*"
    r"(?:think|believe|assume|presume|expect)s?"
    r"|thinking|believing|that)\s+(?:that\s+)?",
    re.IGNORECASE,
)

_YEAR_GROUP = re.compile(r"\s*Year Groups? \d+(?: and \d+)?\s*")


def clean(text: str | None) -> str:
    """Collapse whitespace and fix stray spaces before punctuation."""
    if not text:
        return ""
    text = " ".join(text.split())
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def _sentence(text: str) -> str:
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


def belief(statement: str) -> str | None:
    """Extract the mistaken belief from a misconception, if it is phrased as one.

    Returns None when the statement describes a difficulty rather than a belief
    (e.g. "Pupils struggle to ..."), so it can't be posed as true-or-false.
    """
    statement = clean(statement)
    match = _BELIEF.match(statement)
    if match:
        rest = statement[match.end():]
        return _sentence(rest) if len(rest) > 3 else None
    if re.match(r"^(?:pupils|children|students|some)\b", statement, re.IGNORECASE):
        return None
    return _sentence(statement) if statement else None


def programme_title(name: str, tier: str | None, exam_board: str | None) -> str:
    """'Biology Year Group 10 Foundation AQA' -> 'Biology · Foundation · AQA'."""
    base = _YEAR_GROUP.split(name)[0].strip()
    base = re.sub(r"\bAnd\b", "and", base)
    parts = [base] + [p for p in (tier, exam_board) if p]
    return " · ".join(parts)


def year_number(name: str) -> int | None:
    match = re.search(r"\d+", name)
    return int(match.group()) if match else None
