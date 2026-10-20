import pytest

from truthguard_agent.ingestion import normalize_text


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("a\r\nb\rc", "a\nb\nc"),
        ("a  \nb\t\nc \t ", "a\nb\nc"),
        ("a\n\n\n\nb", "a\n\nb"),
        ("a\n  \n\t\n\nb", "a\n\nb"),
        ("a\n\nb", "a\n\nb"),
        ("  indented  words\nnext line", "  indented  words\nnext line"),
    ],
    ids=["line-endings", "trailing-whitespace", "blank-run", "whitespace-only-lines", "single-blank-kept", "wording-kept"],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_normalize_text_is_idempotent():
    messy = "Title  \r\n\r\n\r\n  Body line one.\t\r\nBody line two.\r\n\r\n\r\n\r\nEnd.  "
    once = normalize_text(messy)
    assert once == "Title\n\n  Body line one.\nBody line two.\n\nEnd."
    assert normalize_text(once) == once
