import json

from oak_explorer.bulk import is_bulk_file, lesson_extras, load_extras

LESSON = {  # shaped like a lesson in an Oak bulk-download file
    "lessonSlug": "volcanoes-and-people",
    "teacherTips": [{"teacherTip": "Use a  local example ."}],
    "contentGuidance": [
        {
            "contentGuidanceArea": "Upsetting, disturbing and sensitive",
            "supervisionlevel_id": 3,
            "contentGuidanceLabel": "Depiction or discussion of violence or suffering",
            "contentGuidanceDescription": "Depiction or discussion of natural disasters.",
        }
    ],
    "supervisionLevel": "Adult supervision recommended",
}


def test_lesson_extras():
    assert lesson_extras(LESSON) == {
        "tips": ["Use a local example."],
        "guidance": [{
            "label": "Depiction or discussion of violence or suffering",
            "description": "Depiction or discussion of natural disasters.",
        }],
        "supervision": "Adult supervision recommended",
    }
    assert lesson_extras({"teacherTips": [], "contentGuidance": None, "supervisionLevel": None}) == {}


def test_lesson_extras_keep_the_lessons_own_keyword_definitions():
    lesson = {"lessonKeywords": [
        {"keyword": "channel", "description": "a single stream of audio used to reproduce sound"},
        {"keyword": "", "description": "dropped"},
    ]}
    assert lesson_extras(lesson) == {"keywords": [["channel", "a single stream of audio used to reproduce sound"]]}


def test_load_extras_reads_only_bulk_files(tmp_path):
    (tmp_path / "geography-secondary.json").write_text(json.dumps(
        {"sequenceSlug": "geography-secondary", "subjectTitle": "Geography", "sequence": [], "lessons": [LESSON]}
    ))
    (tmp_path / "schema.json").write_text(json.dumps({"title": "schema"}))
    (tmp_path / "oak-quizzes.json").write_text(json.dumps({"sequenceSlug": "not really"}))
    (tmp_path / "other.json").write_text(json.dumps({"something": "else"}))

    assert [p.name for p in sorted(tmp_path.glob("*.json")) if is_bulk_file(p)] == ["geography-secondary.json"]
    assert set(load_extras(tmp_path)) == {"volcanoes-and-people"}


def test_subject_from_bulk_groups_units_by_year_in_order():
    from oak_explorer.bulk import subject_from_bulk

    def unit(slug, year, lessons):
        return {"unitSlug": slug, "unitTitle": slug.title(), "year": year, "description": "", "whyThisWhyNow": "",
                "priorKnowledgeRequirements": ["Know A."], "threads": [{"title": "Beliefs"}],
                "unitLessons": [{"lessonSlug": s, "lessonTitle": s.title(), "lessonOrder": i, "state": st}
                                for i, (s, st) in enumerate(lessons, start=1)]}

    data = {
        "sequenceSlug": "religious-education-secondary",
        "sequence": [
            unit("y11-unit", 11, [("gcse-lesson", "published")]),
            unit("first", 7, [("l2", "published"), ("draft", "new")]),
            unit("second", 7, [("l3", "published")]),
        ],
        "lessons": [{**LESSON, "lessonSlug": "l2", "pupilLessonOutcome": "I can explain belief.",
                     "keyLearningPoints": [{"keyLearningPoint": "Point."}], "lessonKeywords": [],
                     "misconceptionsAndCommonMistakes": [{"misconception": "M", "response": "R"}]}],
    }
    subject = subject_from_bulk(data, "Religious Education", (7, 8, 9))

    assert subject["slug"] == "religious-education"
    (y7,) = subject["programmes"]  # year 11 is outside the range; years 8–9 have no units
    assert y7["slug"] == "religious-education-secondary-year-7"
    assert [u["slug"] for u in y7["units"]] == ["first", "second"]
    first = y7["units"][0]
    assert [lesson["slug"] for lesson in first["lessons"]] == ["l2"]  # unpublished lesson dropped
    assert first["lessons"][0]["summary"]["outcome"] == "I can explain belief."
    assert first["lessons"][0]["summary"]["misconceptions"] == [["M", "R"]]
    assert y7["units"][1]["lessons"][0]["summary"] is None  # lesson missing from the file: title only
    assert first["threads"] == ["Beliefs"]
