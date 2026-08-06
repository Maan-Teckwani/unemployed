r"""Finding the entries in a section, across the shapes real resumes come in.

Every test here is about the same question: can this section be refilled from
the knowledge base without producing a heading that is half template and half
truth. The answer is allowed to be no, and most of these check that it says no
for the right reason.
"""
import pytest

from app.ai.latex_entries import Hole, escape, fill, find_entries, hole_role

# The shape people write by hand: a bold name, a subtitle, and a list. No
# resume macros anywhere, which is why a parser built around \resumeSubheading
# would never engage on it.
PLAIN_ENTRIES = r"""
\textbf{Database Health Analyzer} | \textit{Technical Product}
\begin{itemize}[leftmargin=0.2in, itemsep=-2pt]
    \item Translated an ambiguous pain point into a scalable product.
    \item Analyzed data to identify root causes and cut audits to minutes.
\end{itemize}

\textbf{PosturePal} | \textit{Founder \& 0-1 Product Owner}
\begin{itemize}[leftmargin=0.2in, itemsep=-2pt]
    \item Owned a consumer product end to end and shipped the MVP.
\end{itemize}
"""

# Jake's Resume, the most forked template on Overleaf. Bullets are a macro with
# one argument, and each entry is closed by a macro rather than an environment.
JAKES = r"""
\resumeSubHeadingListStart
  \resumeSubheading{Software Engineer}{May 2024 -- Aug 2024}{Acme}{Pune, IN}
  \resumeItemListStart
    \resumeItem{Built the payments API}
    \resumeItem{Wrote tests}
  \resumeItemListEnd
  \resumeSubheading{Data Intern}{May 2023 -- Jul 2023}{Globex}{Chennai, IN}
  \resumeItemListStart
    \resumeItem{Shipped a reporting dashboard}
    \resumeItem{Cut query time}
  \resumeItemListEnd
\resumeSubHeadingListEnd
"""

# One job. There is nothing to choose between, and the dates live in bare text
# after \hfill where nothing can write them.
SINGLE = r"""
\textbf{HFactor} | Software Development Intern \hfill May 2026 -- July 2026
\begin{itemize}
    \item Shipped a client-contract management feature.
    \item Owned the backend end to end.
\end{itemize}
"""

# A certifications section: one run of items, no headings, no entries.
FLAT_LIST = r"""
\begin{itemize}
    \item Product Management using Agentic AI -- IIT Patna x Masai
    \item Oracle Cloud Infrastructure 2025 AI Foundations Associate
\end{itemize}
"""


def test_a_handwritten_section_splits_into_its_projects() -> None:
    entries = find_entries(PLAIN_ENTRIES)
    assert entries is not None
    assert len(entries) == 2
    assert [len(e.bullets) for e in entries] == [2, 1], "bullet counts vary and are kept"


def test_the_heading_holes_are_the_name_and_the_subtitle() -> None:
    entries = find_entries(PLAIN_ENTRIES)
    holes = [[PLAIN_ENTRIES[h.start : h.end] for h in e.lead] for e in entries]
    assert holes == [
        ["Database Health Analyzer", "Technical Product"],
        ["PosturePal", r"Founder \& 0-1 Product Owner"],
    ]


def test_an_escaped_ampersand_is_still_writable_text() -> None:
    r"""`\&` is a character, not a command, so a subtitle containing one is a
    hole. Reading it as a command would make every heading with an ampersand in
    it unfillable, and resumes are full of them."""
    entries = find_entries(PLAIN_ENTRIES)
    assert len(entries[1].lead) == 2


def test_the_environment_name_is_not_a_hole() -> None:
    r"""`\begin{itemize}` sits inside the heading span. Writing a project name
    into it produces a document that does not compile."""
    entries = find_entries(PLAIN_ENTRIES)
    written = [PLAIN_ENTRIES[h.start : h.end] for e in entries for h in e.lead]
    assert "itemize" not in written


def test_macro_templates_are_read_the_same_way() -> None:
    """Jake's Resume: a four-argument heading macro and macro bullets."""
    entries = find_entries(JAKES)
    assert entries is not None
    assert len(entries) == 2
    assert [len(e.bullets) for e in entries] == [2, 2]
    assert [JAKES[h.start : h.end] for h in entries[0].lead] == [
        "Software Engineer",
        "May 2024 -- Aug 2024",
        "Acme",
        "Pune, IN",
    ]


def test_the_previous_entry_s_closing_macros_do_not_count_as_a_difference() -> None:
    r"""The second entry's heading span opens with `}\resumeItemListEnd`, which
    the first entry's cannot have. Comparing raw spans rejects every macro
    template on the strength of that alone."""
    assert find_entries(JAKES) is not None


def test_one_entry_is_declined() -> None:
    """Nothing to choose between, and dates outside any hole."""
    assert find_entries(SINGLE) is None


def test_a_flat_list_is_declined() -> None:
    """Certifications: one run of items, no repeating heading."""
    assert find_entries(FLAT_LIST) is None


def test_prose_outside_a_hole_is_declined() -> None:
    r"""If a heading says something the holes do not cover, filling the holes
    leaves that something behind describing a different project."""
    body = r"""
\textbf{Alpha} Senior
\begin{itemize}
    \item Did a thing
\end{itemize}
\textbf{Beta} Junior
\begin{itemize}
    \item Did another thing
\end{itemize}
"""
    assert find_entries(body) is None


def test_headings_that_differ_between_holes_are_declined() -> None:
    """One entry separates its holes with a pipe and the other with a dash, so
    the shape is not actually repeating and neither is what it means."""
    body = r"""
\textbf{Alpha} | \textit{Product}
\begin{itemize}
    \item Did a thing
\end{itemize}
\textbf{Beta} -- \textit{Platform}
\begin{itemize}
    \item Did another thing
\end{itemize}
"""
    assert find_entries(body) is None


def test_hole_role_reads_a_date_column() -> None:
    assert hole_role(["May 2024 -- Aug 2024", "May 2023 -- Jul 2023"]) == "date"
    assert hole_role(["Acme", "Globex"]) == "text"


def test_one_date_looking_subtitle_does_not_make_a_date_column() -> None:
    """A project called "2026 Rewrite" would otherwise be filled with dates."""
    assert hole_role(["2026 Rewrite", "Founder", "Platform work"]) == "text"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Cut costs by 40% & shipped", r"Cut costs by 40\% \& shipped"),
        ("Used C# and .NET_Core", r"Used C\# and .NET\_Core"),
        ("Saved $2M", r"Saved \$2M"),
        # No safe letter-free escape exists for these, and an escape that
        # produced \textbackslash would add a command to the sequence that
        # guards the document.
        ("a\\b ~ c^d", "a/b - cd"),
        ("Set {x} to {y}", r"Set \{x\} to \{y\}"),
    ],
)
def test_escaping_never_adds_a_command(raw: str, expected: str) -> None:
    import re

    assert escape(raw) == expected
    assert not re.search(r"\\[a-zA-Z]", escape(raw))


def test_filling_replaces_only_the_holes() -> None:
    entries = find_entries(PLAIN_ENTRIES)
    values = {entries[0].lead[0]: "MarketPulse"}
    out = fill(PLAIN_ENTRIES, values)
    assert "MarketPulse" in out
    assert "Database Health Analyzer" not in out
    assert r"\begin{itemize}[leftmargin=0.2in, itemsep=-2pt]" in out
    assert out.count(r"\item") == PLAIN_ENTRIES.count(r"\item")


def test_filling_back_to_front_keeps_later_holes_correct() -> None:
    """Two replacements of different lengths in one pass must not shift each
    other's spans, which is the whole reason this splices in reverse."""
    entries = find_entries(PLAIN_ENTRIES)
    out = fill(
        PLAIN_ENTRIES,
        {
            entries[0].lead[0]: "A much longer project name than before",
            entries[1].lead[0]: "Short",
        },
    )
    assert "A much longer project name than before" in out
    assert r"\textbf{Short}" in out


def test_a_hole_is_a_plain_span() -> None:
    """Holes are compared and stored by value, so two references to the same
    span collapse rather than being applied twice."""
    assert Hole(3, 9) == Hole(3, 9)
