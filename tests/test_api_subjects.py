import runpy
from pathlib import Path

import pytest

from oak_explorer.api_subjects import ID_BASE, convert_subject, stable_id
from oak_explorer.oak_api import OakAPI, OakAPIError, Unavailable

ROOT = Path(__file__).resolve().parent.parent


def lesson(slug, title, misconceptions=()):
    return {
        "slug": slug,
        "title": title,
        "summary": {
            "outcome": f"I can explain {title.lower()}.",
            "keyLearningPoints": ["Point one.", "Point two."],
            "keywords": [["belief", "something a person holds to be true"]],
            "misconceptions": list(misconceptions),
        },
    }


SUBJECT = {
    "slug": "religious-education",
    "title": "Religious Education",
    "programmes": [
        {
            "slug": "religious-education-secondary-year-7",
            "year": 7,
            "units": [
                {
                    "slug": "what-is-religion",
                    "title": "What is religion?",
                    "description": "An introduction.",
                    "whyThisWhyNow": "It starts the course.",
                    "priorKnowledge": ["Some religions have sacred texts."],
                    "threads": ["Beliefs and practices"],
                    "lessons": [
                        lesson("defining-religion", "Defining religion",
                               [["Pupils may think that all religions believe in one god.",
                                 "Many traditions are not monotheistic."]]),
                        lesson("religion-and-worldviews", "Religion and worldviews"),
                    ],
                }
            ],
        },
        {
            "slug": "religious-education-secondary-year-8",
            "year": 8,
            "units": [
                {
                    "slug": "what-is-religion",  # the same unit reused in another year
                    "title": "What is religion?",
                    "description": "",
                    "whyThisWhyNow": "",
                    "priorKnowledge": [],
                    "threads": [],
                    "lessons": [lesson("defining-religion", "Defining religion")],
                }
            ],
        },
        {"slug": "religious-education-primary-year-3", "year": 3, "units": []},
    ],
}


def test_stable_ids_are_deterministic_and_clear_of_database_ids():
    assert stable_id("lesson", "a") == stable_id("lesson", "a")
    assert stable_id("lesson", "a") != stable_id("unit", "a")
    assert stable_id("lesson", "a") >= ID_BASE


def test_convert_subject_builds_programmes_units_and_lessons():
    records = convert_subject(SUBJECT, {7: 11, 8: 12}, chunk_id=101)

    assert set(records["year_programmes"]) == {11, 12}  # year 3 has no id here, so it's skipped
    pid = records["year_programmes"][11][0]
    programme = records["programmes"][pid]
    assert programme["title"] == "Religious Education" and programme["year"] == 7

    uid = programme["units"][0]["options"][0]
    unit = records["chunk"]["units"][uid]
    assert unit["prior"] == ["Some religions have sacred texts."]
    assert unit["threads"] == ["Beliefs and practices"]
    assert records["units"][uid]["chunk"] == 101
    assert records["units"][uid]["year"] == 7  # earliest year it appears in

    first = records["chunk"]["lessons"][unit["lessons"][0]]
    assert first["outcome"] == "I can explain defining religion."
    assert first["keywords"] == [["belief", "something a person holds to be true"]]
    mistake = records["chunk"]["mistakes"][first["mistakes"][0]]
    assert mistake["belief"] == "All religions believe in one god."
    assert unit["mistakes"] == first["mistakes"]
    assert records["lesson_slugs"][unit["lessons"][0]] == "defining-religion"


def test_lesson_without_summary_keeps_its_title():
    subject = {**SUBJECT, "programmes": [{**SUBJECT["programmes"][0], "units": [{
        **SUBJECT["programmes"][0]["units"][0],
        "lessons": [{"slug": "blocked", "title": "Blocked lesson", "summary": None}],
    }]}]}
    records = convert_subject(subject, {7: 11}, chunk_id=101)
    (only,) = records["chunk"]["lessons"].values()
    assert only == {"name": "Blocked lesson", "outcome": "", "points": [], "keywords": [], "mistakes": []}


def test_lesson_summary_normalises_the_api_shape(monkeypatch):
    fetch = runpy.run_path(str(ROOT / "scripts" / "fetch_subjects.py"))

    class FakeAPI:
        def get_one(self, path):
            if "blocked" in path:
                raise Unavailable(path)
            return {  # trimmed from a real /lessons/{slug}/summary response
                "lessonTitle": "Using the laws together",
                "lessonKeywords": [{"keyword": "Commutative", "description": "Order doesn't matter."}],
                "keyLearningPoints": [{"keyLearningPoint": "Laws can be combined."}],
                "misconceptionsAndCommonMistakes": [{"misconception": "X", "response": "Y"}],
                "pupilLessonOutcome": "I can use the laws",
                "teacherTips": [],
                "contentGuidance": None,
            }

    summary = fetch["lesson_summary"](FakeAPI(), "using-the-laws")
    assert summary == {
        "outcome": "I can use the laws",
        "keyLearningPoints": ["Laws can be combined."],
        "keywords": [["Commutative", "Order doesn't matter."]],
        "misconceptions": [["X", "Y"]],
    }
    assert fetch["lesson_summary"](FakeAPI(), "blocked") is None


def test_client_needs_a_key(monkeypatch):
    monkeypatch.delenv("OAK_API_KEY", raising=False)
    with pytest.raises(OakAPIError):
        OakAPI()
