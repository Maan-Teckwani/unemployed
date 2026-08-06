r"""Find the repeating entries inside one section of someone's LaTeX resume.

`latex.py` can reword the sentences in a section but cannot change which
projects are in it, because the document is the only place those projects
exist. This module is what makes the knowledge base usable there: it works out
where one project ends and the next begins, and which spans of text are the
project's name, its subtitle and its bullets.

The output is deliberately not a tree. It is a list of **holes**: character
spans of the body whose contents may be replaced. Everything outside a hole is
never touched, so the rendered section is byte-identical to the template apart
from the words, and the `\command` sequence `latex.validate` checks cannot
change. That is the whole safety argument, and it is structural rather than a
promise about a model's output.

Two entry shapes cover almost every resume in the wild, and one mechanism reads
both, because both are "a lead, then a run of bullets":

    \textbf{PosturePal} | \textit{Founder}          <- lead
    \begin{itemize}
        \item Owned a consumer product end to end   <- bullets
        \item Shipped to 500+ organic users
    \end{itemize}

    \resumeSubheading{Engineer}{2024}{Acme}{Pune}    <- lead
    \resumeItemListStart
      \resumeItem{Built the payments API}            <- bullets
    \resumeItemListEnd

`find_entries` returns None whenever it cannot be sure, and every such case
leaves the caller doing exactly what it did before this module existed. A
section we decline to understand is a section that keeps its own words, which
is a much better failure than a confident one.
"""
import re
from typing import NamedTuple

_COMMAND = re.compile(r"\\[a-zA-Z]+")
_ITEM = re.compile(r"\\item\b")
_ENV = re.compile(r"\\(?:begin|end)\s*\{")
# A year, a month, or the word every resume uses for "still there". Enough to
# tell a date hole from a name hole, and nothing more is needed.
_DATE = re.compile(
    r"\b(?:19|20)\d{2}\b|\bpresent\b|\bcurrent\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
    re.IGNORECASE,
)

# Characters TeX reads as syntax, and the escape that makes each one literal.
# Only escapes whose second character is not a letter are safe here: `\&` is
# invisible to the `\\([a-zA-Z]+)` scan that guards the command sequence, and
# `\textbackslash` would read as a brand new command. So the three that have no
# safe escape are replaced with plain characters instead of escaped.
_ESCAPES = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
}
_REPLACEMENTS = {"\\": "/", "^": "", "~": "-"}


class Hole(NamedTuple):
    """A span of the body whose contents may be replaced."""

    start: int
    end: int


class Bullet(NamedTuple):
    r"""One bullet: where its command starts, where its text lives, where it ends.

    Three positions rather than two because the gap between bullets is what
    separates one entry from the next, and both edges of that gap need a name.
    Using the text start would put every `\item` inside a gap and make every
    bullet look like a new entry; using the text end would put the closing brace
    of `\resumeItem{...}` there and do the same to every macro template.
    """

    command: int
    start: int
    end: int
    after: int


class Entry(NamedTuple):
    """One project or one job: the holes in its heading, and its bullets."""

    lead: tuple[Hole, ...]
    bullets: tuple[Bullet, ...]


def find_entries(body: str) -> list[Entry] | None:
    """The entries in this section body, or None if it is not that shape.

    None is the common answer and not a failure. A section with one entry has
    nothing to choose between; a section whose entries differ in ways this
    cannot express is one where filling the holes would produce a heading that
    is half template and half knowledge base.
    """
    bullets = _find_bullets(body)
    if len(bullets) < 2:
        return None

    runs = _split_runs(body, bullets)
    # One run is a plain list, not repeating entries: a Certifications section,
    # or a single job. There is no slot to choose between, so there is nothing
    # here worth the risk of rewriting a heading.
    if len(runs) < 2:
        return None

    entries: list[Entry] = []
    cursor = 0
    for run in runs:
        lead = _lead_holes(body, cursor, run[0].command)
        if lead is None:
            return None
        entries.append(Entry(lead=lead, bullets=tuple(run)))
        cursor = run[-1].after

    # Every heading must have the same number of holes, or "hole 2" means a
    # different thing in different entries and there is nothing to vote on. No
    # holes at all means the heading is not writable, so there is no way to say
    # which project an entry is about.
    if len({len(e.lead) for e in entries}) != 1 or not entries[0].lead:
        return None

    # The safety property, and the reason this is trustworthy: outside their
    # holes the headings must be the same text. If they are not, the heading
    # carries a fact that lives somewhere we cannot write to, and filling the
    # holes would leave that fact behind describing a different project. Your
    # own template puts the dates of a job in bare text after \hfill, which is
    # exactly this case, and exactly why Experience declines and Projects does
    # not.
    #
    # Compared from the first hole onwards, because everything before it is the
    # previous entry's closing braces and list macros, which only the first
    # entry lacks. That prefix is checked separately for words instead: it is
    # allowed to be structure, and it is not allowed to be prose, or a heading
    # reading "Senior \textbf{Name}" could keep "Senior" while the name changes
    # underneath it.
    skeletons = set()
    for start, entry in _with_lead_starts(body, entries):
        if _has_words(body[start : entry.lead[0].start]):
            return None
        skeletons.add(_skeleton(body, entry))
    if len(skeletons) != 1:
        return None

    return entries


def hole_role(values: list[str]) -> str:
    """What one hole position holds, judged from what the template put there.

    Voting across the entries rather than trusting one, because a single
    project subtitle reading "2026 Product Work" would otherwise turn the whole
    position into a date column.
    """
    dates = sum(1 for v in values if _DATE.search(v))
    return "date" if dates * 2 > len(values) else "text"


def escape(text: str) -> str:
    r"""Make arbitrary prose safe to drop into LaTeX without adding a command.

    The command sequence is the compile guarantee, so an escape that produces
    `\textbackslash` would break the very check it is supposed to survive. The
    three characters with no letter-free escape are replaced rather than
    escaped: a stray backslash or tilde in a knowledge base entry is a typo,
    and losing it costs nothing next to losing the document.
    """
    out = []
    for char in text:
        if char in _REPLACEMENTS:
            out.append(_REPLACEMENTS[char])
        else:
            out.append(_ESCAPES.get(char, char))
    return "".join(out)


def fill(body: str, values: dict[Hole, str]) -> str:
    """Replace hole contents, back to front so earlier spans keep their indices.

    The same splice `latex.tailor` uses on whole sections, one level down.
    Nothing outside a hole moves, which is what makes the result byte-identical
    to the template apart from the words.
    """
    out = body
    for hole in sorted(values, key=lambda h: h.start, reverse=True):
        out = out[: hole.start] + values[hole] + out[hole.end :]
    return out


def _find_bullets(body: str) -> list[Bullet]:
    r"""Every bullet in the body, whichever of the two shapes it uses.

    `\item` wins when present because it is unambiguous. Otherwise the bullet
    is whichever single-argument command repeats most, which is `\resumeItem`
    or `\cvitem` in the templates that have one.
    """
    items = list(_ITEM.finditer(body))
    if len(items) >= 2:
        return _item_bullets(body, items)
    return _macro_bullets(body)


def _item_bullets(body: str, items: list[re.Match]) -> list[Bullet]:
    r"""`\item Some text`, running to the next \item or the end of the list."""
    bullets = []
    for index, match in enumerate(items):
        limit = items[index + 1].start() if index + 1 < len(items) else len(body)
        env = _ENV.search(body, match.end(), limit)
        if env:
            limit = env.start()
        start = _skip_space(body, match.end(), limit)
        end = _rstrip(body, start, limit)
        if end > start:
            # Nothing closes an `\item`, so its text is also its end.
            bullets.append(Bullet(command=match.start(), start=start, end=end, after=end))
    return bullets


def _macro_bullets(body: str) -> list[Bullet]:
    r"""`\resumeItem{Some text}`: the repeated one-argument command."""
    counts: dict[str, list[Bullet]] = {}
    for match in _COMMAND.finditer(body):
        name = match.group()[1:]
        group = _first_group(body, match.end())
        if group is None:
            continue
        counts.setdefault(name, []).append(
            Bullet(command=match.start(), start=group[0], end=group[1], after=group[1] + 1)
        )
    if not counts:
        return []
    name = max(counts, key=lambda k: len(counts[k]))
    return counts[name] if len(counts[name]) >= 2 else []


def _split_runs(body: str, bullets: list[Bullet]) -> list[list[Bullet]]:
    """Group bullets into entries: a run continues while the gap is only space.

    Anything else between two bullets, a closing environment or a new heading
    macro, means the second one belongs to the next project.
    """
    runs = [[bullets[0]]]
    for previous, bullet in zip(bullets, bullets[1:]):
        if body[previous.after : bullet.command].strip():
            runs.append([bullet])
        else:
            runs[-1].append(bullet)
    return runs


def _lead_holes(body: str, start: int, end: int) -> tuple[Hole, ...] | None:
    r"""The fillable brace groups in one entry's heading.

    Fillable means the contents hold no `\command`, so replacing them cannot
    change the command sequence. A group holding commands is not a dead end:
    `\textbf{Gitlytics} $|$ \emph{Python}` has nothing writable at the top
    level and two writable groups one level down, so this recurses.
    """
    holes: list[Hole] = []
    for group_start, content_start, content_end in _groups(body, start, end):
        # `\begin{itemize}` and `\end{itemize}`: the brace holds the name of an
        # environment, not a fact about anyone, and writing to it produces a
        # document that does not compile.
        if _ENV.search(body, max(start, group_start - 12), group_start + 1):
            continue
        if _COMMAND.search(body, content_start, content_end):
            nested = _lead_holes(body, content_start, content_end)
            if nested is None:
                return None
            holes.extend(nested)
        else:
            holes.append(Hole(content_start, content_end))
    return tuple(holes)


def _groups(body: str, start: int, end: int) -> list[tuple[int, int, int]]:
    """Top-level `{...}` groups in a span, as (brace, content start, content end)."""
    found = []
    i = start
    while i < end:
        if body[i] == "{" and not _escaped(body, i):
            close = _matching(body, i, end)
            if close is None:
                break
            found.append((i, i + 1, close))
            i = close + 1
        else:
            i += 1
    return found


def _with_lead_starts(body: str, entries: list[Entry]) -> list[tuple[int, Entry]]:
    """Each entry paired with where its heading begins."""
    starts = [0]
    for entry in entries[:-1]:
        starts.append(entry.bullets[-1].after)
    return list(zip(starts, entries))


def _skeleton(body: str, entry: Entry) -> str:
    r"""One heading from its first hole on, with the hole contents blanked.

    Whitespace is collapsed because it differs between the first entry and the
    rest for no reason beyond how the file was typed, and because rendering
    uses each entry's own text rather than this, so nothing here reaches the
    page.
    """
    text = _blank(body, entry.lead[0].start, entry.bullets[0].command, entry.lead)
    return re.sub(r"\s+", " ", text).strip()


def _has_words(text: str) -> bool:
    r"""True if this span says anything, once the LaTeX is taken out of it.

    `\resumeItemListEnd`, a stray closing brace and `\begin{itemize}[...]` are
    structure. "Senior" is a fact about a person, and a fact sitting outside
    every hole is one this module cannot replace.
    """
    bare = _ENV.sub("", re.sub(r"\\(?:begin|end)\s*\{[^}]*\}", "", text))
    bare = _COMMAND.sub("", bare)
    return bool(re.search(r"[A-Za-z]", bare))


def _blank(body: str, start: int, end: int, holes: tuple[Hole, ...]) -> str:
    out = []
    cursor = start
    for hole in holes:
        out.append(body[cursor : hole.start])
        cursor = hole.end
    out.append(body[cursor:end])
    return "".join(out)


def _first_group(body: str, start: int) -> tuple[int, int] | None:
    r"""The `{...}` immediately after a command, across spaces but not blank lines.

    A blank line ends a paragraph in TeX, so a group after one is never an
    argument. Without that rule `\vspace{-2pt}` followed by a `{\small ...}`
    block reads as a two-argument command.
    """
    i = start
    newlines = 0
    while i < len(body) and body[i].isspace():
        newlines += body[i] == "\n"
        if newlines > 1:
            return None
        i += 1
    if i >= len(body) or body[i] != "{" or _escaped(body, i):
        return None
    close = _matching(body, i, len(body))
    return None if close is None else (i + 1, close)


def _matching(body: str, open_index: int, limit: int) -> int | None:
    depth = 0
    for i in range(open_index, min(limit, len(body))):
        if body[i] == "{" and not _escaped(body, i):
            depth += 1
        elif body[i] == "}" and not _escaped(body, i):
            depth -= 1
            if depth == 0:
                return i
    return None


def _escaped(body: str, index: int) -> bool:
    backslashes = 0
    while index - 1 - backslashes >= 0 and body[index - 1 - backslashes] == "\\":
        backslashes += 1
    return backslashes % 2 == 1


def _skip_space(body: str, start: int, limit: int) -> int:
    while start < limit and body[start].isspace():
        start += 1
    return start


def _rstrip(body: str, start: int, limit: int) -> int:
    while limit > start and body[limit - 1].isspace():
        limit -= 1
    return limit
