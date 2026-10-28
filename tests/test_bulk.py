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


def test_load_extras_reads_only_bulk_files(tmp_path):
    (tmp_path / "geography-secondary.json").write_text(json.dumps(
        {"sequenceSlug": "geography-secondary", "subjectTitle": "Geography", "sequence": [], "lessons": [LESSON]}
    ))
    (tmp_path / "schema.json").write_text(json.dumps({"title": "schema"}))
    (tmp_path / "oak-quizzes.json").write_text(json.dumps({"sequenceSlug": "not really"}))
    (tmp_path / "other.json").write_text(json.dumps({"something": "else"}))

    assert [p.name for p in sorted(tmp_path.glob("*.json")) if is_bulk_file(p)] == ["geography-secondary.json"]
    assert set(load_extras(tmp_path)) == {"volcanoes-and-people"}
