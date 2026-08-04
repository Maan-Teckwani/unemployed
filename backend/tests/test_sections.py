"""Where each accomplishment ends up, and whether it survives the trip.

This file exists because the complaint that started it was "the resume is not
putting things under proper headings", and nothing tested headings at all. The
generator had nine tests, all about truthfulness, and the PDF renderer had none:
no test in the suite imported app.ai.pdf.

Every case below is a bug that shipped.
"""
from types import SimpleNamespace

import pdfplumber
import pytest

from app.ai import pdf as pdf_mod
from app.ai.generate_resume import _validate_bullets
from app.ai.parse import _normalize, section_of, segments_with_sections
from app.ai.sections import (
    ACHIEVEMENTS,
    CERTIFICATIONS,
    EDUCATION,
    EXPERIENCE,
    ORDER,
    PROJECTS,
    quota_for,
    section_for,
)


# Spelled out, because a digit in a bullet that is not in its source chunk is an
# invented metric and gets rejected before sectioning is reached.
NAMES = [
    "zeroth", "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
    "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
    "nineteenth", "twentieth", "twentyfirst", "twentysecond",
]


def chunk(chunk_id: int, chunk_type: str, title="Thing", company=None, dates=None):
    return SimpleNamespace(
        id=chunk_id,
        type=chunk_type,
        title=title,
        accomplishment="Did the thing",
        impact=None,
        context=None,
        company=company,
        date_range=dates,
        technologies=[],
        skills=[],
    )


# ---- Every chunk type lands under a heading that means something -------------
@pytest.mark.parametrize(
    "chunk_type,expected",
    [
        ("experience", EXPERIENCE),
        ("leadership", EXPERIENCE),
        ("project", PROJECTS),
        ("achievement", ACHIEVEMENTS),
        ("certification", CERTIFICATIONS),
        ("education", EDUCATION),
    ],
)
def test_each_type_has_its_own_section(chunk_type, expected) -> None:
    assert section_for(chunk_type) == expected


def test_skills_are_not_filed_as_projects() -> None:
    # "skill" is a valid chunk type that had no section, so it fell through a
    # bare `return "Projects"` and printed somebody's skills as a project.
    # It has no bullet section at all now: the skills line is computed from the
    # job description, so a skill chunk being routed anywhere was the bug.
    assert "skill" not in {t for t in ("experience", "leadership", "project")}
    assert section_for("skill") == PROJECTS  # last resort, and never reached in practice


def test_certifications_are_not_merged_into_achievements() -> None:
    # These used to share a heading here while latex.py treated certifications
    # as a section of its own, so the same knowledge base produced two different
    # documents depending on which renderer was asked.
    assert section_for("certification") != section_for("achievement")


def test_unknown_type_does_not_claim_a_credential() -> None:
    # Whatever the fallback is, it must not assert an employer, a degree or a
    # certificate the candidate may not have.
    assert section_for("nonsense") not in (EXPERIENCE, EDUCATION, CERTIFICATIONS)


# ---- One section can no longer starve the others ----------------------------
def test_one_section_cannot_consume_the_whole_resume() -> None:
    # The old cap was eight bullets total, applied in arrival order. Twenty
    # Experience bullets returned first meant Projects, Education and
    # Certifications each rendered empty, and an empty section prints no
    # heading, so they vanished from the document entirely.
    by_id = {i: chunk(i, "experience") for i in range(1, 21)}
    by_id[21] = chunk(21, "project")
    by_id[22] = chunk(22, "education")

    # No digits in the text: a number that is not in the source chunk is an
    # invented metric and gets dropped before it can reach a section, which is
    # a different guarantee being tested in test_resume.py.
    raw = [{"source_id": i, "text": f"Did thing number {NAMES[i]}"} for i in range(1, 23)]
    kept, _ = _validate_bullets(raw, by_id)

    sections = {b["section"] for b in kept}
    assert PROJECTS in sections
    assert EDUCATION in sections

    experience = [b for b in kept if b["section"] == EXPERIENCE]
    assert len(experience) == quota_for(EXPERIENCE)


def test_a_section_keeps_its_strongest_bullets() -> None:
    # Bullets arrive strongest first, so a full section must drop the tail.
    by_id = {i: chunk(i, "project") for i in range(1, 10)}
    raw = [{"source_id": i, "text": f"Built the {NAMES[i]} one"} for i in range(1, 10)]
    kept, _ = _validate_bullets(raw, by_id)

    texts = [b["text"] for b in kept]
    assert texts == [f"Built the {NAMES[i]} one" for i in range(1, quota_for(PROJECTS) + 1)]


# ---- Section headings survive extraction ------------------------------------
@pytest.mark.parametrize(
    "line,expected",
    [
        ("EDUCATION", "education"),
        ("Education", "education"),
        ("  WORK EXPERIENCE  ", "experience"),
        ("Technical Skills", "skill"),
        ("CERTIFICATIONS", "certification"),
        ("Positions of Responsibility", "leadership"),
        ("PROJECTS", "project"),
        ("Awards and Honours", "achievement"),
    ],
)
def test_a_heading_line_is_recognised(line, expected) -> None:
    assert section_of(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "My education taught me to ship early and often, which is why",
        "Built a projects dashboard used by the whole team every morning",
        "",
        "   ",
    ],
)
def test_ordinary_prose_is_not_a_heading(line) -> None:
    # A sentence that merely contains the word is not a section break. Reading
    # one as a heading would refile everything after it.
    assert section_of(line) is None


def test_a_split_section_carries_its_heading_forward() -> None:
    # The document is cut into model-sized pieces wherever the text allows, so
    # the second half of a long education list arrives with no heading in it.
    # Left to guess, the model picks the most common thing in a resume, which is
    # jobs, and a degree gets printed as employment.
    filler = "\n".join(f"Line {i} of a fairly long entry about study" for i in range(400))
    text = f"EXPERIENCE\nWorked somewhere\n\nEDUCATION\n{filler}"

    pieces = segments_with_sections(text)
    assert len(pieces) > 1, "this fixture is meant to span several segments"
    assert pieces[-1][1] == "education"


def test_an_unrecognised_type_uses_the_section_it_came_from() -> None:
    # This is the direct mechanical link between bad extraction and wrong
    # headings: `type` is the only thing that picks a heading, and it used to
    # default to "experience" unconditionally.
    assert _normalize({"accomplishment": "x", "type": "???"}, "education")["type"] == "education"
    assert _normalize({"accomplishment": "x"}, "certification")["type"] == "certification"
    # Only a document with no heading at all falls back.
    assert _normalize({"accomplishment": "x", "type": "???"}, None)["type"] == "experience"
    # A type the model got right is never overridden by the section.
    assert _normalize({"accomplishment": "x", "type": "project"}, "education")["type"] == "project"


# ---- The PDF actually prints the headings -----------------------------------
def render(tmp_path, bullets, profile=None):
    resume = {"summary": "", "skills": ["Python"], "bullets": bullets}
    profile = profile or SimpleNamespace(
        name="Test Person", email="t@example.com", phone="", location="", links={}, education=""
    )
    out = pdf_mod.render(profile, resume, tmp_path / "resume.pdf")
    # Read back through pdfplumber, which is what ats.py uses to check the
    # rendered document, so these tests see the same text an ATS would.
    with pdfplumber.open(str(out)) as doc:
        return "\n".join(page.extract_text() or "" for page in doc.pages)


def bullet(section, text, title="Thing", company=None, dates=None):
    return {
        "text": text,
        "source_chunk_ids": [1],
        "section": section,
        "title": title,
        "context": None,
        "company": company,
        "date_range": dates,
    }


def test_every_section_present_gets_its_heading(tmp_path) -> None:
    bullets = [bullet(section, f"Something for {section}") for section in ORDER]
    text = render(tmp_path, bullets)
    for section in ORDER:
        assert section.upper() in text, f"{section} heading is missing from the PDF"


def test_sections_print_in_the_conventional_order(tmp_path) -> None:
    bullets = [bullet(section, f"Something for {section}") for section in reversed(ORDER)]
    text = render(tmp_path, bullets)
    positions = [text.index(section.upper()) for section in ORDER]
    assert positions == sorted(positions)


def test_two_jobs_with_the_same_title_stay_separate(tmp_path) -> None:
    # Grouping by title alone merged these into one heading and then printed one
    # job's dates over both jobs' work.
    bullets = [
        bullet(EXPERIENCE, "Shipped the first thing", "Software Engineer", "Acme", "2023"),
        bullet(EXPERIENCE, "Shipped the second thing", "Software Engineer", "Globex", "2024"),
    ]
    text = render(tmp_path, bullets)
    assert "Acme" in text and "Globex" in text
    assert "2023" in text and "2024" in text


def test_extracted_education_replaces_the_typed_in_field(tmp_path) -> None:
    profile = SimpleNamespace(
        name="Test Person", email="", phone="", location="", links={},
        education="Typed by hand",
    )
    text = render(tmp_path, [bullet(EDUCATION, "BTech in Computer Science")], profile)
    assert "BTech in Computer Science" in text
    assert "Typed by hand" not in text, "the hand-typed field should not be printed twice"


def test_the_typed_in_field_is_still_used_when_nothing_was_extracted(tmp_path) -> None:
    profile = SimpleNamespace(
        name="Test Person", email="", phone="", location="", links={},
        education="BSc, Some University",
    )
    text = render(tmp_path, [bullet(EXPERIENCE, "Did a job")], profile)
    assert EDUCATION.upper() in text
    assert "Some University" in text


# ---- Characters are not silently deleted ------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("José García", "Jose Garcia"),
        ("Björn", "Bjorn"),
        ("₹5,00,000 saved", "INR 5,00,000 saved"),
        ("café — done", "cafe - done"),
        ("90 percent", "90 percent"),
        ("a…b", "a...b"),
    ],
)
def test_accents_and_symbols_survive(raw, expected) -> None:
    # The old code ended in encode("latin-1", "ignore"), which deleted whatever
    # it could not encode. A name came out a letter short and nothing said so.
    assert pdf_mod._safe(raw) == expected


def test_an_accented_name_is_not_shortened(tmp_path) -> None:
    profile = SimpleNamespace(
        name="José Álvarez", email="", phone="", location="", links={}, education=""
    )
    text = render(tmp_path, [bullet(EXPERIENCE, "Did a job")], profile)
    assert "Jose Alvarez" in text


def test_something_unrepresentable_leaves_a_mark() -> None:
    # Better a visible "?" than a sentence that quietly lost a word.
    out = pdf_mod._safe("emoji \U0001f600 here")
    assert "emoji" in out and "here" in out
    assert "?" in out
