import pytest

from oak_explorer.text import belief, clean, programme_title


@pytest.mark.parametrize(
    "statement, expected",
    [
        ("Pupils may think that the Sun orbits the Earth", "The Sun orbits the Earth."),
        ("Some children often believe heavy things fall faster.", "Heavy things fall faster."),
        ("That addition always makes numbers bigger", "Addition always makes numbers bigger."),
        ("Thinking that plants get food from soil", "Plants get food from soil."),
        ("All metals are magnetic.", "All metals are magnetic."),
        ("Pupils struggle to line up the digits", None),
    ],
)
def test_belief(statement, expected):
    assert belief(statement) == expected


def test_clean_collapses_whitespace_and_stray_spaces():
    assert clean("This is\n  the  answer .") == "This is the answer."
    assert clean(None) == ""


def test_programme_title():
    assert programme_title("Biology Year Group 10 Higher AQA", "Higher", "AQA") == "Biology · Higher · AQA"
    assert programme_title("Art And Design Year Group 7", None, None) == "Art and Design"
