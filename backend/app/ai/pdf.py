"""Render a resume to an ATS-safe PDF.

Everything here is a deliberate parseability choice, not a style choice:

* **Single column.** Multi-column layouts are the number one cause of garbled ATS
  parsing — extractors read in text order and interleave the columns.
* **Real text, no images, no tables, no text boxes.** A resume rendered as
  graphics parses as nothing at all.
* **Standard section headings** ("Experience", "Projects", "Skills", "Education")
  because parsers look for exactly these words to segment the document.
* **Core font (Helvetica).** No embedded/exotic fonts to mangle extraction.

The layout is fixed and code-owned — the LLM writes words, never markup, so a bad
generation can never produce an unparseable document.
"""
import unicodedata
from pathlib import Path

from fpdf import FPDF

from app.ai.sections import EDUCATION, ORDER

PAGE_MARGIN = 14
LINE = 4.6


class _Resume(FPDF):
    def header(self) -> None:  # no running header: it confuses parsers
        pass

    def footer(self) -> None:
        pass


def render(profile, resume: dict, out_path: Path) -> Path:
    """Write the resume PDF and return its path."""
    pdf = _Resume(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=PAGE_MARGIN)
    pdf.set_margins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    pdf.add_page()

    _header(pdf, profile)
    if resume.get("summary"):
        _section(pdf, "Summary")
        _body(pdf, resume["summary"])
    if resume.get("skills"):
        _section(pdf, "Skills")
        _body(pdf, ", ".join(resume["skills"]))

    bullets = resume.get("bullets", [])
    for section in ORDER:
        items = [b for b in bullets if b.get("section") == section]
        if items:
            _section(pdf, section)
            _bullets(pdf, items)

    # The typed-in field, only when nothing was extracted for it. Education used
    # to come from here alone, which meant a resume that listed a degree still
    # printed no Education heading unless the same degree had also been typed
    # into the profile by hand, and ats.py then warned about the missing section
    # forever.
    if getattr(profile, "education", "") and not any(
        b.get("section") == EDUCATION for b in bullets
    ):
        _section(pdf, EDUCATION)
        _body(pdf, profile.education)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def _header(pdf: FPDF, profile) -> None:
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 7, _safe(profile.name or "Your Name"), new_x="LMARGIN", new_y="NEXT")

    contact = " | ".join(
        p for p in [profile.email, profile.phone, profile.location] if p
    )
    links = " | ".join(str(v) for v in (profile.links or {}).values() if v)
    pdf.set_font("Helvetica", "", 9)
    for line in (contact, links):
        if line:
            pdf.cell(0, LINE, _safe(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)


def _section(pdf: FPDF, title: str) -> None:
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 5.5, _safe(title.upper()), new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.line(PAGE_MARGIN, y, pdf.w - PAGE_MARGIN, y)
    pdf.ln(1)


def _body(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 9.5)
    # multi_cell leaves the cursor at the RIGHT edge by default, which makes the
    # next full-width call fail with "not enough horizontal space".
    pdf.multi_cell(0, LINE, _safe(text), new_x="LMARGIN", new_y="NEXT")


def _bullets(pdf: FPDF, items: list[dict]) -> None:
    """Group bullets under their role/project heading.

    Bullets arrive ordered by relevance, so the same project can appear more than
    once; grouping first keeps each heading on the page exactly once.

    Grouped by title AND employer AND dates, not by title alone. Two spells as
    "Software Engineer" at different companies collapsed into one heading under a
    title-only key, and because the company and dates were then read off
    whichever bullet happened to sort first, the merged entry printed one job's
    dates over both jobs' work.
    """
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for item in items:
        key = (
            (item.get("title") or "").strip(),
            (item.get("company") or "").strip(),
            (item.get("date_range") or "").strip(),
        )
        grouped.setdefault(key, []).append(item)

    for (title, company, dates), group in grouped.items():
        # An untitled chunk used to print an empty bold line with an orphaned
        # indent under it. Falling through to the employer, then to nothing,
        # keeps the bullets attached to whatever context there is.
        label = title or company
        meta = " | ".join(
            p for p in ([company] if company and company != label else []) + [dates] if p
        )
        if label:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5, _safe(label), new_x="LMARGIN", new_y="NEXT")
        if meta:
            pdf.set_font("Helvetica", "I", 9)
            pdf.cell(0, LINE, _safe(meta), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9.5)
        for item in group:
            # "- " not a bullet glyph: plain ASCII always survives extraction.
            pdf.multi_cell(
                0, LINE, _safe(f"- {item['text']}"), new_x="LMARGIN", new_y="NEXT"
            )
        pdf.ln(0.5)


# The punctuation a word processor substitutes while you type, which is most of
# what actually turns up outside latin-1, plus the currency symbols that matter
# to anyone writing an impact figure.
_REPLACEMENTS = {
    "–": "-", "—": "-", "‒": "-", "−": "-",
    "‘": "'", "’": "'", "‚": ",", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "•": "-", "‣": "-", "●": "-", "·": "-",
    "…": "...", " ": " ", " ": " ", " ": " ",
    "→": "->", "≤": "<=", "≥": ">=",
    "₹": "INR ", "€": "EUR ", "£": "GBP ", "¥": "JPY ",
    "™": "(TM)", "®": "(R)", "′": "'", "″": '"',
}


def _safe(text: str) -> str:
    """Make text printable by a core PDF font without deleting any of it.

    Core fonts are latin-1, and this used to end in
    `encode("latin-1", "ignore")`, which silently dropped whatever it could not
    encode. A name spelled with an accent came out a letter short, a rupee figure
    lost its currency, and nothing anywhere said so. On a resume that is the
    worst failure mode available: the document is still valid, it is just quietly
    wrong about the candidate's name.

    Three passes, most preserving first. Substitute the punctuation a word
    processor invents. Then decompose accented letters and drop only the marks,
    so an accented "Jose" stays "Jose" rather than losing a letter. Only then
    replace what is genuinely unrepresentable with "?", which at least shows that
    something was there.
    """
    text = text or ""
    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)

    # NFKD splits an accented letter into a base letter plus a combining mark,
    # so removing only the marks keeps the letters.
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return stripped.encode("latin-1", "replace").decode("latin-1")
