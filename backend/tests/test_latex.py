"""The LaTeX path has one job: never hand back a document that will not compile.

`tailor` is exercised with a stubbed model rather than a live one — the
interesting cases are the *bad* rewrites, and asking a real model to produce
unbalanced braces on demand is not a test, it is a wish.
"""
import pytest

from app.ai import latex as latex_mod
from app.ai.latex import find_sections, tailor, validate

# A cut-down version of the most common Overleaf resume shape: custom macros in
# the preamble, \section{\textbf{...}} headings, itemize inside each entry.
TEMPLATE = r"""\documentclass[letterpaper,11pt]{article}
\usepackage{titlesec}
\newcommand{\resumeItem}[1]{\item\small{#1}}
\begin{document}
\begin{center}\textbf{\Huge Ada Lovelace}\end{center}

\section{\textbf{Education}}
  \textbf{Analytical University} \hfill 2023 -- 2027

\section{Work Experience}
  \begin{itemize}
    \resumeItem{Built a payments API handling 200 requests per second}
    \resumeItem{Wrote tests}
  \end{itemize}

\section{Personal Projects}
  \begin{itemize}
    \resumeItem{A notes app}
  \end{itemize}

\section{Technical Skills}
  Python, Go

\end{document}
"""


class FakeChunk:
    """Enough of a KBChunk for the checks that read one.

    Company, context and dates are on here because entries are now filled from
    the knowledge base and not only reworded, so those fields reach the page
    and have to count as things the candidate can back up.
    """

    _next_id = 1

    def __init__(
        self,
        title,
        accomplishment,
        impact=None,
        technologies=None,
        type="project",
        company="",
        context="",
        date_range="",
    ):
        self.id = FakeChunk._next_id
        FakeChunk._next_id += 1
        self.title = title
        self.accomplishment = accomplishment
        self.impact = impact
        self.technologies = technologies or []
        self.type = type
        self.company = company
        self.context = context
        self.date_range = date_range


CHUNKS = [
    FakeChunk(
        "Payments API",
        "Built a payments API in Go serving 200 requests per second",
        impact="cut latency to 40ms",
        technologies=["Go", "Postgres"],
    )
]


def test_find_sections_maps_headings_to_what_we_may_rewrite() -> None:
    found = {s.name: s.heading for s in find_sections(TEMPLATE)}
    assert found == {
        "": "Education",  # not ours to touch
        "experience": "Work Experience",
        "projects": "Personal Projects",
        "skills": "Technical Skills",
    }


def test_section_bodies_stop_at_the_next_section() -> None:
    body = {s.name: TEMPLATE[s.start : s.end] for s in find_sections(TEMPLATE)}
    assert "payments API" in body["experience"]
    assert "notes app" not in body["experience"]
    assert "\\end{document}" not in body["skills"]


def test_a_section_stops_before_the_next_one_s_comment_banner() -> None:
    r"""`% ----- PROJECTS -----` introduces the next section. Included in this
    body, the model rewrites it away and the author's file loses the banner."""
    doc = (
        "\\begin{document}\n"
        "\\section{Experience}\n  \\item Built it\n\n"
        "% ---------- PROJECTS ----------\n"
        "\\section{Projects}\n  \\item Shipped it\n"
        "\\end{document}"
    )
    experience = find_sections(doc)[0]
    body = doc[experience.start : experience.end]
    assert "Built it" in body
    assert "%" not in body


def test_headings_survive_wrapping_commands() -> None:
    """\\section{\\textbf{Education}} still reads as "Education"."""
    assert find_sections(TEMPLATE)[0].heading == "Education"


def test_escaped_ampersands_read_as_text() -> None:
    """Real templates write `Skills \\& Competencies`; the badge must not show the escape."""
    doc = r"\begin{document}\section{Skills \& Competencies} Python \end{document}"
    section = find_sections(doc)[0]
    assert (section.heading, section.name) == ("Skills & Competencies", "skills")


@pytest.mark.parametrize(
    ("rewritten", "expected"),
    [
        ("", "the model returned nothing"),
        (r"\resumeItem{Built a payments API", "unbalanced braces"),
        (r"\begin{itemize}\resumeItem{Shipped it}", "structure changed"),
        (r"\begin{itemize}\resumeItem{\textit{Shipped it}}\end{itemize}", "structure changed"),
        (r"\begin{center}\resumeItem{Shipped it}\end{center}", "environments"),
        (r"\begin{itemize}\resumeItem{Served 900 requests per second}\end{itemize}",
         "invented numbers"),
    ],
)
def test_validate_rejects_dangerous_rewrites(rewritten: str, expected: str) -> None:
    original = r"\begin{itemize}\resumeItem{Built a payments API}\end{itemize}"
    assert expected in validate(original, rewritten, CHUNKS)


def test_a_dropped_macro_is_caught_even_though_it_hides_an_environment() -> None:
    r"""The live failure: templates open `itemize` inside `\resumeSubHeadingListStart`,
    so dropping the matching End leaves a document that will not compile while
    every literal \begin/\end still balances."""
    original = r"\resumeSubHeadingListStart\resumeItem{Built it}\resumeSubHeadingListEnd"
    rewritten = r"\resumeSubHeadingListStart\resumeItem{Built the payments API}"
    assert "structure changed" in validate(original, rewritten, CHUNKS)


def test_erasing_a_certificate_is_rejected() -> None:
    """The live failure that every other check waved through: a certification
    line rewritten as an accomplishment, taking the issuer with it."""
    original = r"\item Product Management using Agentic AI -- IIT Patna x Masai"
    rewritten = r"\item Successfully designed product management strategies"
    problem = validate(original, rewritten, CHUNKS, "certifications")
    assert "dropped entries" in problem
    assert "IIT" in problem or "Patna" in problem


def test_a_prose_section_may_drop_a_parenthetical() -> None:
    """Rewording is the point in experience and projects; only list sections are
    frozen. Enforcing it everywhere rejected every rewrite of a real resume."""
    original = r"\item Shipped contract management (Client ID, Contract Code) for the team"
    rewritten = r"\item Shipped a contract management feature for the team"
    assert validate(original, rewritten, CHUNKS, "experience") == ""


def test_a_comment_banner_is_not_a_fact() -> None:
    r"""Templates label sections with `% ----- EXPERIENCE -----`; a model that
    reformats drops the comment, and that is not a lost credential."""
    original = "% ---------- CERTIFICATIONS ----------\n\\item AWS Certified"
    rewritten = r"\item AWS Certified"
    assert validate(original, rewritten, CHUNKS, "certifications") == ""


def test_reordering_a_list_is_allowed() -> None:
    """Skills may be reordered to lead with what the job asks for."""
    original = r"\item Python, SQL, Docker"
    rewritten = r"\item SQL, Python, Docker"
    assert validate(original, rewritten, CHUNKS, "skills") == ""


def test_an_invented_employer_is_rejected() -> None:
    """The other live failure: the model renamed the employer to suit the job."""
    original = r"\resumeSubheading{Software Engineering Intern}{Fintech Startup}"
    rewritten = r"\resumeSubheading{Cloud Engineer}{AWS Partner Ecosystem}"
    assert "invented names" in validate(original, rewritten, CHUNKS)


@pytest.mark.parametrize(
    "rewritten",
    [
        r"\resumeItem{Designed a Go payments API backed by Postgres}",
        # Real rejections seen from the live model: ordinary English words that
        # happen to be capitalised. Flagging these rejected every single section.
        r"\resumeItem{Proficient in building a payments API}",
        r"\resumeItem{Successfully built a payments API}",
        r"\resumeItem{Built a payments API. Improved throughput}",
        # A verb in front of a name the candidate does own. The name checks out,
        # and rejecting this cost a real Certifications section its rewrite.
        r"\resumeItem{Delivered Payments API work}",
    ],
)
def test_ordinary_capitalisation_is_not_an_invention(rewritten: str) -> None:
    """Only proper-noun phrases and acronyms are claims; English is not."""
    original = r"\resumeItem{Built a payments API}"
    assert validate(original, rewritten, CHUNKS) == ""


@pytest.mark.parametrize(
    "rewritten",
    [
        r"\resumeItem{Built a payments API on AWS Lambda}",  # phrase + acronym
        r"\resumeItem{Built a payments API for Acme Financial Group}",
        r"\resumeItem{Built a payments API deployed to GCP}",  # bare acronym
    ],
)
def test_names_the_candidate_cannot_back_up_are_rejected(rewritten: str) -> None:
    original = r"\resumeItem{Built a payments API}"
    assert "invented names" in validate(original, rewritten, CHUNKS)


def test_validate_accepts_a_faithful_rewrite() -> None:
    original = r"\begin{itemize}\resumeItem{Built a payments API}\end{itemize}"
    rewritten = r"\begin{itemize}\resumeItem{Built a Go payments API at 200 rps}\end{itemize}"
    assert validate(original, rewritten, CHUNKS) == ""


def test_numbers_already_in_the_section_are_not_inventions() -> None:
    """Dates and figures the user wrote must survive being repeated back."""
    original = r"\resumeItem{Led a team of 6 from 2024}"
    rewritten = r"\resumeItem{Led 6 engineers from 2024}"
    assert validate(original, rewritten, CHUNKS) == ""


def _tailor_with(monkeypatch, rewrite):
    """Stubs take **kwargs because a failed rewrite is retried with `correction`."""
    monkeypatch.setattr(latex_mod, "rewrite_section", rewrite)
    return tailor(TEMPLATE, CHUNKS, {"required_skills": ["Go"]})


def test_tailor_changes_only_the_sections_it_may(monkeypatch) -> None:
    out, report = _tailor_with(
        monkeypatch,
        lambda name, body, *a, **kw: body.replace("Wrote tests", "Wrote unit tests"),
    )
    preamble = TEMPLATE[: TEMPLATE.index("\\begin{document}")]
    assert out.startswith(preamble), "the preamble must be byte-identical"
    assert "Analytical University" in out, "Education is not ours to rewrite"
    assert "Wrote unit tests" in out
    assert [e["name"] for e in report] == ["experience", "projects", "skills"]
    assert all(e["rewritten"] for e in report)


def test_a_broken_rewrite_keeps_the_original_section(monkeypatch) -> None:
    out, report = _tailor_with(monkeypatch, lambda *a, **kw: r"\resumeItem{oops")
    assert out == TEMPLATE
    assert all(not e["rewritten"] for e in report)
    assert all("brace" in e["reason"] for e in report)


def test_a_rejected_rewrite_is_retried_once_with_the_reason(monkeypatch) -> None:
    """A small model mostly fails by reflowing structure it was told to copy,
    which it can fix when told what it broke."""
    attempts: list[str | None] = []

    def rewrite(name, body, chunks, reqs, correction=None):
        attempts.append(correction)
        # Break it the first time, copy it faithfully on the retry.
        return r"\resumeItem{oops" if correction is None else body

    out, report = _tailor_with(monkeypatch, rewrite)

    assert out == TEMPLATE, "a faithful copy changes nothing"
    assert all(e["rewritten"] for e in report)
    assert attempts.count(None) == 3, "one first attempt per rewritable section"
    assert all("brace" in a for a in attempts if a), "the retry is told what broke"


def test_a_failing_model_call_keeps_the_original_section(monkeypatch) -> None:
    def boom(*a, **kw):
        raise RuntimeError("ollama is down")

    out, report = _tailor_with(monkeypatch, boom)
    assert out == TEMPLATE
    assert report[0]["reason"] == "the model failed: ollama is down"


def test_tailoring_a_document_without_sections_is_a_no_op() -> None:
    plain = "\\documentclass{article}\\begin{document}Hello\\end{document}"
    out, report = tailor(plain, CHUNKS, {})
    assert (out, report) == (plain, [])


# --- choosing entries from the knowledge base --------------------------------
#
# The thing rewording cannot do. A template holds whichever projects were in
# the file on the day it was uploaded; the knowledge base holds everything the
# candidate has ever built, and which of those belongs on the page depends on
# the job.

ENTRY_TEMPLATE = r"""\documentclass{article}
\begin{document}
\section{Projects}
\textbf{Old Project One} | \textit{Legacy}
\begin{itemize}[leftmargin=0.2in]
    \item Did the first thing
    \item Did the second thing
\end{itemize}

\textbf{Old Project Two} | \textit{Legacy}
\begin{itemize}[leftmargin=0.2in]
    \item Did the third thing
    \item Did the fourth thing
\end{itemize}
\end{document}
"""


def _project(title, *accomplishments, tech=("Python",)):
    return [
        FakeChunk(title, text, technologies=list(tech), type="project")
        for text in accomplishments
    ]


# Ranked best-first, which is what retrieve_all hands over, so MarketPulse is
# group 0 and PosturePal group 1. Neither is in the template.
ENTRY_CHUNKS = (
    _project(
        "MarketPulse",
        "Built a market data pipeline",
        "Shipped an alerting service",
        tech=("FastAPI", "AWS"),
    )
    + _project(
        "PosturePal",
        "Owned a desktop product end to end",
        "Shipped the MVP to real users",
        tech=("Electron",),
    )
    + _project("Old Project One", "Did the first thing", "Did the second thing")
)


def _plan(*groups):
    """A model reply choosing these groups, quoting their own accomplishments."""
    by_title: dict[str, list] = {}
    for chunk in ENTRY_CHUNKS:
        by_title.setdefault(chunk.title, []).append(chunk)
    return {
        "slots": [
            {
                "project": index,
                "bullets": [
                    {"source_id": c.id, "text": c.accomplishment}
                    for c in by_title[title][:2]
                ],
            }
            for index, title in groups
        ]
    }


def _tailor_entries(monkeypatch, reply):
    monkeypatch.setattr(latex_mod, "generate_json", lambda *a, **kw: reply)
    # Rewording must never run: if it does, the assertions below are measuring
    # the old path and would pass for the wrong reason.
    monkeypatch.setattr(
        latex_mod, "rewrite_section", lambda *a, **kw: pytest.fail("rewrote instead of choosing")
    )
    return tailor(ENTRY_TEMPLATE, ENTRY_CHUNKS, {"required_skills": ["FastAPI"]})


def test_a_project_the_template_never_mentioned_reaches_the_page(monkeypatch) -> None:
    """The whole point of the sprint, and impossible before it."""
    out, report = _tailor_entries(monkeypatch, _plan((0, "MarketPulse"), (1, "PosturePal")))

    assert "MarketPulse" in out and "PosturePal" in out
    assert "Old Project One" not in out and "Old Project Two" not in out
    assert "Built a market data pipeline" in out
    assert report[0]["mode"] == "entries"
    assert [e["title"] for e in report[0]["entries"]] == ["MarketPulse", "PosturePal"]


def test_choosing_entries_cannot_change_the_structure(monkeypatch) -> None:
    r"""The compile guarantee. Nothing outside a brace group is touched, so the
    `\command` sequence is identical by construction rather than by checking."""
    out, _ = _tailor_entries(monkeypatch, _plan((0, "MarketPulse"), (1, "PosturePal")))
    assert latex_mod._command_sequence(out) == latex_mod._command_sequence(ENTRY_TEMPLATE)
    assert out.count(r"\item") == ENTRY_TEMPLATE.count(r"\item")


def test_the_subtitle_is_filled_too(monkeypatch) -> None:
    """A heading half updated is the failure that compiles and reads as true."""
    out, _ = _tailor_entries(monkeypatch, _plan((0, "MarketPulse"), (1, "PosturePal")))
    assert r"\textit{FastAPI, AWS}" in out
    assert "Legacy" not in out


def test_the_chosen_accomplishments_are_recorded(monkeypatch) -> None:
    """Traceability: the UI proves a bullet by showing the chunk it came from."""
    _, report = _tailor_entries(monkeypatch, _plan((0, "MarketPulse"), (1, "PosturePal")))
    ids = [i for e in report[0]["entries"] for i in e["chunk_ids"]]
    assert ids == [c.id for c in ENTRY_CHUNKS[:4]]


def _refused(monkeypatch, reply):
    """Tailor with a model reply that must not be believed."""
    monkeypatch.setattr(latex_mod, "generate_json", lambda *a, **kw: reply)
    monkeypatch.setattr(latex_mod, "rewrite_section", lambda name, body, *a, **kw: body)
    return tailor(ENTRY_TEMPLATE, ENTRY_CHUNKS, {})


@pytest.mark.parametrize(
    ("reply", "why"),
    [
        ({"slots": []}, "one slot per entry or none"),
        ({"slots": [{"project": 0, "bullets": []}] * 2}, "a slot must fill every bullet"),
        ({"slots": [{"project": 9, "bullets": []}] * 2}, "a project that does not exist"),
        ({}, "no answer at all"),
    ],
)
def test_a_plan_is_all_the_slots_or_none_of_them(monkeypatch, reply, why) -> None:
    """A section half chosen and half left alone can show the same project
    twice, so one bad slot discards the whole plan. What replaces it is the
    ranking, not the template: the projects are still chosen for this job."""
    out, report = _refused(monkeypatch, reply)
    assert out != ENTRY_TEMPLATE, why
    assert report[0]["mode"] == "entries"
    assert report[0]["chosen_by"] == "ranking"
    assert "MarketPulse" in out and "Old Project One" not in out


def test_the_ranked_fallback_quotes_the_knowledge_base_exactly(monkeypatch) -> None:
    """Nothing is generated on this path, so nothing on it can be invented."""
    out, _ = _refused(monkeypatch, {})
    assert "Built a market data pipeline" in out
    assert "Shipped an alerting service" in out


def test_a_bullet_citing_another_project_is_refused(monkeypatch) -> None:
    """Bullets belong to the entry they are printed under. A true sentence
    about a different project is a false one about this heading."""
    reply = {
        "slots": [
            {"project": 0, "bullets": [
                {"source_id": ENTRY_CHUNKS[0].id, "text": "Built a market data pipeline"},
                {"source_id": ENTRY_CHUNKS[2].id, "text": "A borrowed sentence"},
            ]},
            {"project": 1, "bullets": [
                {"source_id": ENTRY_CHUNKS[2].id, "text": "Owned a desktop product end to end"},
                {"source_id": ENTRY_CHUNKS[3].id, "text": "Shipped the MVP to real users"},
            ]},
        ]
    }
    out, report = _refused(monkeypatch, reply)
    assert "A borrowed sentence" not in out
    assert report[0]["chosen_by"] == "ranking"


def test_an_invented_number_in_a_chosen_bullet_is_refused(monkeypatch) -> None:
    """Checked against the one accomplishment the bullet cites, not against the
    whole knowledge base: a figure true of another project is still a false
    claim about this one."""
    reply = _plan((0, "MarketPulse"), (1, "PosturePal"))
    reply["slots"][0]["bullets"][0]["text"] = "Built a pipeline serving 900 requests per second"
    out, report = _refused(monkeypatch, reply)
    assert "900" not in out
    assert report[0]["chosen_by"] == "ranking"


def test_the_same_project_cannot_fill_two_slots(monkeypatch) -> None:
    out, report = _refused(monkeypatch, _plan((0, "MarketPulse"), (0, "MarketPulse")))
    assert report[0]["chosen_by"] == "ranking"
    assert out.count(r"\textbf{MarketPulse}") == 1


def test_too_few_projects_to_choose_from_falls_back(monkeypatch) -> None:
    """Two slots and one project is not a choice. The reason is recorded so the
    user knows to enrich the knowledge base rather than assuming it is broken."""
    monkeypatch.setattr(
        latex_mod, "generate_json", lambda *a, **kw: pytest.fail("asked with nothing to choose")
    )
    monkeypatch.setattr(latex_mod, "rewrite_section", lambda name, body, *a, **kw: body)
    one = _project("MarketPulse", "Built a market data pipeline", "Shipped alerting")
    out, report = tailor(ENTRY_TEMPLATE, one, {})
    assert out == ENTRY_TEMPLATE
    assert report[0]["mode"] == "rewrite"


def test_a_section_that_is_not_entries_still_only_rewords(monkeypatch) -> None:
    """The original template has one bullet list per section and no repeating
    heading, so nothing there is a slot. It must behave exactly as before."""
    monkeypatch.setattr(
        latex_mod, "generate_json", lambda *a, **kw: pytest.fail("treated a list as entries")
    )
    out, report = _tailor_with(monkeypatch, lambda name, body, *a, **kw: body)
    assert out == TEMPLATE
    assert all(e["mode"] == "rewrite" for e in report)
