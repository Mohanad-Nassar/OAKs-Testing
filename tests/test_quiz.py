from oak_explorer.quiz import convert_question, convert_quiz

IMG = "https://cloudinary-res.thenational.academy/image/upload/x.png"


def no_images(url):
    return None


def local_images(url):
    return "img/x.png"


def test_multiple_choice_marks_correct_answers():
    q = convert_question(
        {
            "question": "Pick the even numbers",
            "questionType": "multiple-choice",
            "answers": [
                {"type": "text", "content": "2", "distractor": False},
                {"type": "text", "content": "3", "distractor": True},
                {"type": "text", "content": "4", "distractor": False},
            ],
        },
        no_images,
    )
    assert q == {
        "q": "Pick the even numbers",
        "type": "mc",
        "options": [{"text": "2"}, {"text": "3"}, {"text": "4"}],
        "correct": [0, 2],
    }


def test_short_answer_drops_blank_alternatives():
    q = convert_question(
        {
            "question": "A {{}} returns a value.",
            "questionType": "short-answer",
            "answers": [{"type": "text", "content": "function "}, {"type": "text", "content": ""}],
        },
        no_images,
    )
    assert q["type"] == "short" and q["accept"] == ["function"]


def test_match_and_order():
    match = convert_question(
        {
            "question": "Match",
            "questionType": "match",
            "answers": [
                {
                    "matchOption": {"type": "text", "content": "list"},
                    "correctChoice": {"type": "text", "content": "many values"},
                }
            ],
        },
        no_images,
    )
    assert match["pairs"] == [["list", "many values"]]

    order = convert_question(
        {
            "question": "Order",
            "questionType": "order",
            "answers": [
                {"order": 2, "type": "text", "content": "second"},
                {"order": 1, "type": "text", "content": "first"},
            ],
        },
        no_images,
    )
    assert order["items"] == ["first", "second"]


def test_image_questions_need_a_local_copy():
    raw = {
        "question": "Which gate is this?",
        "questionType": "multiple-choice",
        "questionImage": {"url": IMG, "width": 10, "height": 10},
        "answers": [{"type": "text", "content": "AND", "distractor": False}],
    }
    assert convert_question(raw, no_images) is None
    assert convert_question(raw, local_images)["img"] == "img/x.png"


def test_convert_quiz_skips_unusable_questions():
    quiz = convert_quiz(
        {
            "starter": [{"question": "?", "questionType": "unknown", "answers": []}],
            "exit": [
                {
                    "question": "Name it",
                    "questionType": "short-answer",
                    "answers": [{"type": "text", "content": "bit"}],
                }
            ],
        },
        no_images,
    )
    assert quiz["starter"] == [] and len(quiz["exit"]) == 1
