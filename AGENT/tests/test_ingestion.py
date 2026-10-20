import hashlib
import re
from datetime import date

import pytest

from truthguard_agent.ingestion import chunk_document, ingest_document, normalize_text
from truthguard_agent.schemas import AuthorityLevel, Document, DocumentIn

SENTENCE_BOUNDARY = re.compile(r"([.!?][\"')\]]*)\s+(\S)")
ABBREVIATION_BEFORE = re.compile(r"(?i)(?<![a-z])(dr|mr|mrs|ms|prof|sec|fig|vs)\.$")


def has_sentence_boundary(text):
    for m in SENTENCE_BOUNDARY.finditer(text):
        if m.group(2).islower() or ABBREVIATION_BEFORE.search(text[: m.start(1) + 1]):
            continue
        return True
    return False


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("a\r\nb\rc", "a\nb\nc"),
        ("a  \nb\t\nc \t ", "a\nb\nc"),
        ("a\n\n\n\nb", "a\n\nb"),
        ("a\n  \n\t\n\nb", "a\n\nb"),
        ("a\n\nb", "a\n\nb"),
        ("  indented  words\nnext line", "  indented  words\nnext line"),
        ("a \nb \n \nc", "a \nb \n \nc"),
        ("", ""),
        ("\n\na\n\n", "\n\na\n\n"),
        ("\n\n\n", "\n\n"),
    ],
    ids=[
        "line-endings",
        "trailing-whitespace",
        "blank-run",
        "whitespace-only-lines",
        "single-blank-kept",
        "wording-kept",
        "unicode-spaces-kept",
        "empty",
        "edge-blank-lines-kept",
        "blank-only-collapsed",
    ],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_normalize_text_is_idempotent():
    messy = "Title  \r\n\r\n\r\n  Body line one.\t\r\nBody line two.\r\n\r\n\r\n\r\nEnd.  "
    once = normalize_text(messy)
    assert once == "Title\n\n  Body line one.\nBody line two.\n\nEnd."
    assert normalize_text(once) == once


def make_doc(content, document_id="d1"):
    return Document(document_id=document_id, title="T", content=content)


def test_one_line_document_is_one_chunk():
    chunks = chunk_document(make_doc("Employees may work remotely."))
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "d1::chunk_000"
    assert chunks[0].document_id == "d1"
    assert chunks[0].index == 0
    assert chunks[0].text == "Employees may work remotely."
    assert (chunks[0].start_offset, chunks[0].end_offset) == (0, 28)


@pytest.mark.parametrize(
    "content, max_chars, expected",
    [
        # two short paragraphs merge; the third does not fit (13 + 2 + 6 > 14)
        ("Alpha.\n\nBeta.\n\nGamma.", 14, [("Alpha.\n\nBeta.", 0, 13), ("Gamma.", 15, 21)]),
        # a paragraph over the limit is split at sentence ends, then short sentences are merged
        ("One two. Three four. Five six.", 20, [("One two. Three four.", 0, 20), ("Five six.", 21, 30)]),
        ("Really? Yes! Fine.", 8, [("Really?", 0, 7), ("Yes!", 8, 12), ("Fine.", 13, 18)]),
        # a single sentence longer than max_chars is kept whole, never cut mid-sentence
        ("Hi. Averyveryverylongsentence.", 10, [("Hi.", 0, 3), ("Averyveryverylongsentence.", 4, 30)]),
        # a single newline stays inside the paragraph
        ("Line one\nline two.\n\nNext.", 100, [("Line one\nline two.\n\nNext.", 0, 25)]),
        # a paragraph is not split at a single newline
        ("Line one\nline two.\n\nNext.", 15, [("Line one\nline two.", 0, 18), ("Next.", 20, 25)]),
        # a dot inside a token (3.14) is not a sentence end
        ("Version 3.14 applies. Next.", 15, [("Version 3.14 applies.", 0, 21), ("Next.", 22, 27)]),
        # a period followed by a lowercase word is not a sentence end
        (
            "Staff may work remotely, e.g. on Fridays. Next.",
            15,
            [("Staff may work remotely, e.g. on Fridays.", 0, 41), ("Next.", 42, 47)],
        ),
        # known abbreviations are not sentence ends, even before a capital letter or a digit
        ("Dr. Lee approved the plan. Next.", 15, [("Dr. Lee approved the plan.", 0, 26), ("Next.", 27, 32)]),
        ("See Fig. 3 for details. Next.", 15, [("See Fig. 3 for details.", 0, 23), ("Next.", 24, 29)]),
        # ! and ? followed by a lowercase word are not sentence ends either
        ("Wait! the door shut. Next.", 10, [("Wait! the door shut.", 0, 20), ("Next.", 21, 26)]),
        # the abbreviation rule only applies to a period
        ("I asked Dr! Then I left.", 15, [("I asked Dr!", 0, 11), ("Then I left.", 12, 24)]),
        # a digit after the period does start a new sentence
        ("It took 3 days. 14 more followed.", 15, [("It took 3 days.", 0, 15), ("14 more followed.", 16, 33)]),
        # "No." as an answer still ends a sentence
        (
            "Is it covered? No. Travel is booked.",
            15,
            [("Is it covered?", 0, 14), ("No.", 15, 18), ("Travel is booked.", 19, 36)],
        ),
        # indentation and non-breaking spaces are excluded from chunk text; a blank-looking paragraph is skipped
        (
            "  Indented.\n\n \n\nTail ",
            11,
            [("Indented.", 2, 11), ("Tail", 16, 20)],
        ),
    ],
    ids=[
        "merge-paragraphs",
        "split-and-merge-sentences",
        "sentence-terminators",
        "long-sentence-whole",
        "single-newline-merged",
        "single-newline-not-split",
        "dot-inside-token",
        "lowercase-after-period",
        "title-abbreviation",
        "abbreviation-before-digit",
        "lowercase-after-bang-or-question",
        "abbreviation-rule-only-for-period",
        "digit-after-period-splits",
        "no-as-answer-still-splits",
        "indent-and-nbsp-trimmed",
    ],
)
def test_chunk_boundaries_and_offsets(content, max_chars, expected):
    chunks = chunk_document(make_doc(content), max_chars=max_chars)
    assert [(c.text, c.start_offset, c.end_offset) for c in chunks] == expected
    assert [c.index for c in chunks] == list(range(len(expected)))


def test_offsets_are_positions_in_normalized_content():
    raw = "Remote work: 3 days.  \r\n\r\n\r\nTravel needs approval."
    chunks = chunk_document(make_doc(raw), max_chars=25)
    assert [(c.text, c.start_offset, c.end_offset) for c in chunks] == [
        ("Remote work: 3 days.", 0, 20),
        ("Travel needs approval.", 22, 44),
    ]
    assert normalize_text(raw)[22:44] == "Travel needs approval."


@pytest.mark.parametrize("abbreviation", ["Dr", "Mr", "Mrs", "Ms", "Prof", "Sec", "Fig", "vs", "DR"])
def test_listed_abbreviations_do_not_end_a_sentence(abbreviation):
    sentence = "Ask %s. Lee today." % abbreviation
    chunks = chunk_document(make_doc(sentence + " Next."), max_chars=15)
    assert [c.text for c in chunks] == [sentence, "Next."]


MESSY = (
    "Remote Work Policy  \r\n\r\n\r\n"
    "Employees may work remotely up to three days a week. Managers must approve each request.\r\n"
    "Exceptions need written sign-off!  \r\n\r\n"
    "Is travel covered? No. Travel is booked through the portal and reimbursed within 30 days.\r\n\r\n\r\n\r\n"
    "Ask Dr. Lee about it, e.g. on Fridays. See Fig. 3 for the timeline. Wait! the door shut.\r\n\r\n"
    "A_single_token_sentence_that_is_much_longer_than_the_small_limits_used_in_this_test_run."
)


@pytest.mark.parametrize("max_chars", [1, 10, 40, 100, 800])
def test_chunks_are_well_formed_for_any_limit(max_chars):
    normalized = normalize_text(MESSY)
    chunks = chunk_document(make_doc(MESSY), max_chars=max_chars)
    assert chunks
    for c in chunks:
        assert normalized[c.start_offset : c.end_offset] == c.text
        assert c.text and c.text == c.text.strip()
        if len(c.text) > max_chars:  # only a lone sentence may exceed the limit
            assert "\n\n" not in c.text and not has_sentence_boundary(c.text)
    for previous, current in zip(chunks, chunks[1:]):
        assert previous.end_offset <= current.start_offset
    # no text is dropped or duplicated
    assert "".join("".join(c.text.split()) for c in chunks) == "".join(normalized.split())
    assert [c.chunk_id for c in chunks] == ["d1::chunk_%03d" % i for i in range(len(chunks))]


def test_chunk_ids_and_offsets_are_identical_on_every_run():
    first = chunk_document(make_doc(MESSY), max_chars=60)
    second = chunk_document(make_doc(MESSY), max_chars=60)
    assert first == second


def test_whitespace_only_document_has_no_chunks():
    assert chunk_document(make_doc("  \r\n\n \t ")) == []


@pytest.mark.parametrize("bad", [0, -5])
def test_max_chars_must_be_positive(bad):
    with pytest.raises(ValueError):
        chunk_document(make_doc("text"), max_chars=bad)


RAW_POLICY = "Remote Work Policy  \r\n\r\nEmployees may work remotely.\r\n\r\nTravel needs approval.  "


def test_ingest_document_stores_the_sha256_of_the_raw_content():
    doc, _ = ingest_document(DocumentIn(document_id="d1", title="T", content=RAW_POLICY))
    assert doc.content_hash == hashlib.sha256(RAW_POLICY.encode("utf-8")).hexdigest()
    assert doc.content == RAW_POLICY


def test_ingest_document_hash_detects_a_changed_file_but_ignores_metadata():
    base = ingest_document(DocumentIn(document_id="d1", title="T", content=RAW_POLICY))[0]
    renamed = ingest_document(DocumentIn(document_id="d2", title="Other", content=RAW_POLICY, version="2"))[0]
    edited = ingest_document(DocumentIn(document_id="d1", title="T", content=RAW_POLICY + "!"))[0]
    assert renamed.content_hash == base.content_hash
    assert edited.content_hash != base.content_hash


def test_ingest_document_recomputes_a_hash_supplied_by_the_caller():
    forged = Document(document_id="d1", title="T", content=RAW_POLICY, content_hash="0" * 64)
    doc, _ = ingest_document(forged)
    assert doc.content_hash == hashlib.sha256(RAW_POLICY.encode("utf-8")).hexdigest()


def test_ingest_document_returns_the_chunks_of_the_normalized_content():
    _, chunks = ingest_document(DocumentIn(document_id="d1", title="T", content=RAW_POLICY), max_chars=30)
    assert [(c.chunk_id, c.text, c.start_offset, c.end_offset) for c in chunks] == [
        ("d1::chunk_000", "Remote Work Policy", 0, 18),
        ("d1::chunk_001", "Employees may work remotely.", 20, 48),
        ("d1::chunk_002", "Travel needs approval.", 50, 72),
    ]


def test_ingest_document_keeps_missing_metadata_unknown():
    doc, _ = ingest_document(DocumentIn(document_id="d1", title="T", content="Text."))
    assert doc.version is None and doc.created_at is None and doc.effective_date is None
    assert doc.supersedes_document_id is None and doc.source is None
    assert doc.authority_level == AuthorityLevel.UNKNOWN


def test_ingest_document_keeps_the_metadata_it_was_given():
    doc, _ = ingest_document(
        DocumentIn(
            document_id="d2",
            title="Amendment",
            content="Text.",
            version="2",
            created_at=date(2026, 10, 1),
            effective_date=date(2026, 10, 15),
            authority_level=AuthorityLevel.OFFICIAL,
            supersedes_document_id="d1",
            source="hr-portal",
        )
    )
    assert (doc.document_id, doc.title, doc.version) == ("d2", "Amendment", "2")
    assert doc.created_at == date(2026, 10, 1) and doc.effective_date == date(2026, 10, 15)
    assert doc.authority_level == AuthorityLevel.OFFICIAL and doc.supersedes_document_id == "d1"
    assert doc.source == "hr-portal"
