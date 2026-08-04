"""Turn an uploaded career document into proposed KB chunks.

Two clearly separated steps:
1. extract_text  — deterministic: pull raw text out of pdf/docx/txt/md.
2. parse_to_chunks — the LLM's job: structure that text into accomplishment
   chunks. It is instructed to use ONLY what's in the document (no inventing);
   the user reviews and edits everything before it is saved.
"""
import io
import re
from typing import Callable

import pdfplumber
from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ai.llm import generate_json

# How much document text goes into one model call. A long CV is split across
# several calls rather than truncated: cutting at 12k characters silently threw
# away the second half of anyone's career.
_SEGMENT_CHARS = 12000


def extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from a supported document."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return _from_pdf(data)
    if ext == "docx":
        return _from_docx(data)
    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: .{ext} (use pdf, docx, txt, or md)")


def _from_pdf(data: bytes) -> str:
    """Page text, plus any tables the page draws.

    `extract_text` alone reads a table as whatever order its cells happen to sit
    in, which for a two column skills grid is every other word. Pulling the
    tables out separately and writing each row on its own line at least keeps the
    row together, which is the unit that means something.
    """
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [str(c).strip() for c in row if c and str(c).strip()]
                    if cells:
                        parts.append(" | ".join(cells))
    return "\n".join(p for p in parts if p.strip())


def _from_docx(data: bytes) -> str:
    """Everything in the document, in the order it is laid out.

    `Document.paragraphs` skips table cells entirely, and a resume that puts its
    skills, education or contact details in a table is common enough that this
    was the single biggest way text went missing: not truncated, never read.

    Walking the body's own children keeps paragraphs and tables interleaved in
    document order, so a heading still arrives immediately before the table it
    introduces.

    Headers and footers are appended at the end because that is where phone
    numbers and email addresses hide in a lot of templates.
    """
    doc = Document(io.BytesIO(data))
    lines = list(_iter_block_text(doc))

    for section in doc.sections:
        for container in (section.header, section.footer):
            for paragraph in container.paragraphs:
                if paragraph.text.strip():
                    lines.append(paragraph.text.strip())

    return "\n".join(lines)


def _iter_block_text(parent: DocxDocument):
    """Paragraph and table text from one container, in document order."""
    body = parent.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            text = Paragraph(child, parent).text.strip()
            if text:
                yield text
        elif child.tag == qn("w:tbl"):
            for row in Table(child, parent).rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                # Deduplicated because a merged cell reports its text once per
                # column it spans, which would otherwise repeat every entry.
                unique = list(dict.fromkeys(cells))
                if unique:
                    yield " | ".join(unique)


_SYSTEM = """You extract a candidate's career into structured accomplishment chunks for a resume knowledge base.

Rules:
- Use ONLY information present in the document. Never invent facts, metrics, employers, dates, or technologies.
- Create ONE chunk per distinct accomplishment or responsibility (split multi-part bullets).
- Choose `type` from: project, experience, leadership, achievement, skill, certification, education.
- Use `education` for degrees, schools and coursework, one chunk per qualification. Put the degree in `title`, the institution in `company` and the years in `date_range`.
- Fill `technologies` and `skills` only with items actually mentioned; otherwise use [].
- Fill `impact` only if a concrete outcome/metric is stated; otherwise null.
- Keep `accomplishment` concise, truthful, and results-oriented.

Respond as JSON: {"chunks": [{"type","title","context","company","date_range","accomplishment","technologies":[],"skills":[],"impact"}]}"""


# The headings a resume actually uses, and what each one means in our own
# vocabulary.
#
# Ordered most specific first, and "experience" is deliberately last: it is the
# word most likely to turn up inside a combined heading, and a template that
# writes "Skills & Experience" means the skills section.
_SECTION_TYPES: tuple[tuple[str, str], ...] = (
    (r"educations?|academics?|qualifications?|schooling", "education"),
    (r"certifications?|certificates?|licen[cs]es?|courses?|coursework|training", "certification"),
    (r"skills?|technologies|technology|technical|tools|competenc(?:y|ies)", "skill"),
    (r"projects?|portfolio", "project"),
    (r"leadership|volunteering|volunteer|activities|responsibility|extracurricular", "leadership"),
    (r"achievements?|awards?|honou?rs?|accomplishments?|publications?", "achievement"),
    (r"experiences?|employment|internships?|professional|career", "experience"),
)

_SECTION_PATTERNS = tuple(
    (re.compile(rf"(?<![a-z]){words}(?![a-z])", re.IGNORECASE), kind)
    for words, kind in _SECTION_TYPES
)

# A heading is a label, not a sentence. Both bounds are what stop an ordinary
# line that happens to contain "education" from refiling everything after it.
_MAX_HEADING_CHARS = 40
_MAX_HEADING_WORDS = 4


def section_of(line: str) -> str | None:
    """The chunk type this line announces, if it is a section heading at all.

    Extraction flattens a document to plain text, which throws away the font size
    and the bold that made a heading look like one. All that survives is the
    shape of the line: short, standing alone, and naming a section. That shape is
    what this reads, and it is the only thing standing between "EDUCATION" and a
    degree being filed as another job.

    Shape first, keyword second, deliberately. Keyword alone would read "My
    education taught me to ship early" as a section break.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_CHARS:
        return None
    if len(stripped.split()) > _MAX_HEADING_WORDS:
        return None
    for pattern, kind in _SECTION_PATTERNS:
        if pattern.search(stripped):
            return kind
    return None


def segment(text: str) -> list[str]:
    """Split a document into model-sized pieces, breaking at the cleanest seam.

    Where it breaks matters: cutting mid-bullet hands the model half an
    accomplishment and it faithfully records half an accomplishment. So it tries
    paragraph gaps first, then single line breaks, and only chops mid-line when a
    document offers no seam at all.

    Both fallbacks are load-bearing on real files. A Windows text file separates
    paragraphs with CRLF, and PDF text extraction routinely comes back as one
    long run of single newlines — either would otherwise sail past a
    blank-line-only split and reach the model whole.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) <= _SEGMENT_CHARS:
        return [text] if text else []

    return _pack(_pieces(text))


def segments_with_sections(text: str) -> list[tuple[str, str | None]]:
    """Each segment, paired with the section heading that was open when it began.

    A long resume is split into several model calls, and the split lands wherever
    the text allows. A segment starting halfway through the education list used
    to arrive with no clue what it was, so the model guessed, and it guessed the
    most common thing in a resume, which is jobs. Carrying the heading forward is
    what stops the second half of a section being filed as something else.
    """
    pieces = segment(text)
    out: list[tuple[str, str | None]] = []
    current: str | None = None
    for piece in pieces:
        out.append((piece, current))
        for line in piece.split("\n"):
            found = section_of(line)
            if found:
                current = found
    return out


def _pieces(text: str) -> list[str]:
    """Break text into units no larger than one segment, cleanest seam first."""
    units = text.split("\n\n")
    if all(len(u) <= _SEGMENT_CHARS for u in units):
        return units

    units = [line for unit in units for line in unit.split("\n")]
    if all(len(u) <= _SEGMENT_CHARS for u in units):
        return units

    return [
        unit[i : i + _SEGMENT_CHARS]
        for unit in units
        for i in range(0, len(unit), _SEGMENT_CHARS)
    ]


def _pack(units: list[str]) -> list[str]:
    """Greedily fill segments so a long document is as few model calls as possible."""
    segments: list[str] = []
    current = ""
    for unit in units:
        if not unit.strip():
            continue
        if current and len(current) + len(unit) + 2 > _SEGMENT_CHARS:
            segments.append(current)
            current = unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    if current:
        segments.append(current)
    return segments


def parse_to_chunks(
    text: str,
    kind_hint: str | None = None,
    on_segment: Callable[[], None] | None = None,
) -> list[dict]:
    """Structure document text into chunk dicts, one model call per segment.

    No timeout: a 30-page CV on a laptop model is slow, not broken, and the
    caller runs this in the background with a progress bar for exactly that
    reason. `on_segment` fires after each call so that bar can move.
    """
    hint = f"\n\nThis document is the candidate's: {kind_hint}." if kind_hint else ""
    chunks: list[dict] = []
    for piece, section in segments_with_sections(text):
        # Told, not left to be inferred: a piece that begins mid-section has no
        # heading in it to read.
        carried = (
            f"\n\nThis continues the {section} section of the document."
            if section
            else ""
        )
        # A resume can yield many chunks, so this needs far more room than extraction.
        result = generate_json(
            _SYSTEM, f"Document:{hint}{carried}\n\n{piece}", timeout=None, max_tokens=4000
        )
        raw = result.get("chunks", []) if isinstance(result, dict) else []
        chunks.extend(
            _normalize(c, section)
            for c in raw
            if isinstance(c, dict) and c.get("accomplishment")
        )
        if on_segment:
            on_segment()
    return chunks


_VALID_TYPES = {
    "project", "experience", "leadership", "achievement", "skill",
    "certification", "education",
}

# LLMs often emit the *string* "null"/"none"/"n/a" instead of a real null.
_NULLISH = {"", "null", "none", "n/a", "na", "unknown", "not specified"}


def _opt(value, limit: int) -> str | None:
    """Optional text field: strip, drop nullish placeholders, cap length."""
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text.lower() not in _NULLISH else None


def _normalize(c: dict, section: str | None = None) -> dict:
    """Coerce a raw LLM chunk into our exact shape with safe defaults.

    When the model returns a type we do not recognise, the section the text came
    from decides, and only a document with no heading at all falls back to
    "experience". That fallback used to be unconditional, and since `type` is the
    single thing that picks the heading a chunk is printed under, it was the
    mechanism by which a degree ended up in the middle of someone's job history.
    """
    ctype = str(c.get("type", "")).lower().strip()
    if ctype not in _VALID_TYPES:
        ctype = section if section in _VALID_TYPES else "experience"
    return {
        "type": ctype,
        "title": _opt(c.get("title"), 300) or "Untitled",
        "context": _opt(c.get("context"), 300),
        "company": _opt(c.get("company"), 200),
        "date_range": _opt(c.get("date_range"), 100),
        "accomplishment": str(c["accomplishment"]).strip(),
        "technologies": [t for t in (_opt(x, 100) for x in (c.get("technologies") or [])) if t],
        "skills": [s for s in (_opt(x, 100) for x in (c.get("skills") or [])) if s],
        "impact": _opt(c.get("impact"), 500),
    }
