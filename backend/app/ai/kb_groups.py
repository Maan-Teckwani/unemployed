"""Turn the knowledge base back into projects and jobs.

`kb_chunks` holds one row per accomplishment, which is the right shape for
retrieval and the wrong shape for a resume. A resume entry is a heading plus
several bullets, so before anything can choose "the three best projects for
this job" the rows have to be gathered back into the things they came from.

Grouping is by title, across types, for a reason worth writing down. The
importer decides `type` per accomplishment rather than per project, so the
three bullets of one project routinely arrive as one `project` row and two
`experience` rows. It also fills `company` from whatever noun sat nearest the
text, which in a real knowledge base means groups keyed on company come out
named "FastAPI" and "Python". Title is the only field the importer gets right
often enough to group on.

Ranking costs nothing extra: `retrieve.retrieve_all` has already ordered every
chunk against this job, so a group's score is read off those positions. A
group scores for being relevant and for having several relevant accomplishments
rather than one, which is what a three-bullet entry needs.
"""
import re
from typing import NamedTuple

from app.db.models import KBChunk

# The types worth putting under a heading with bullets under it. A certification
# or a bare skill is a line in a list, not an entry, and offering one as a
# candidate project is how a Certifications line ends up rewritten as a claim.
ENTRY_TYPES = ("project", "experience", "leadership", "achievement")


class Group(NamedTuple):
    """One project or job, and the accomplishments that belong to it."""

    key: str
    title: str
    company: str
    date_range: str
    context: str
    technologies: tuple[str, ...]
    chunks: tuple[KBChunk, ...]
    score: float


def group_chunks(ranked: list[KBChunk]) -> list[Group]:
    """Gather ranked chunks into entries, best first.

    `ranked` is what `retrieve.retrieve_all` returns: every chunk, ordered
    against this job. Order is the input to the score, so passing an unranked
    list produces groups in arbitrary order rather than an error.
    """
    titles = {_norm(c.title) for c in ranked if c.title}
    buckets: dict[str, list[tuple[int, KBChunk]]] = {}
    for rank, chunk in enumerate(ranked):
        if (chunk.type or "") not in ENTRY_TYPES:
            continue
        key = _key(chunk)
        if key:
            buckets.setdefault(key, []).append((rank, chunk))

    groups = [_build(key, members, titles) for key, members in buckets.items()]
    groups.sort(key=lambda g: g.score, reverse=True)
    return groups


def describe(group: Group, limit: int = 3) -> str:
    """One group as the few lines a model needs to judge it.

    Accomplishments are numbered with their chunk ids rather than a position,
    so what comes back can be checked against the database instead of against
    an index into a list this function happened to build.
    """
    header = group.title
    if group.company:
        header += f" at {group.company}"
    if group.date_range:
        header += f" ({group.date_range})"
    lines = [header]
    if group.technologies:
        lines.append(f"    Technologies: {', '.join(group.technologies)}")
    for chunk in group.chunks[:limit]:
        lines.append(f"    [{chunk.id}] {chunk.accomplishment}")
        if chunk.impact:
            lines.append(f"          Impact: {chunk.impact}")
    return "\n".join(lines)


def _key(chunk: KBChunk) -> str:
    """What makes two accomplishments part of the same thing.

    Title and company together. Company alone is useless here, because the
    importer fills it with a technology often enough that grouping on it
    produces a project called "FastAPI". Used with the title it can only ever
    split a group, never merge two, and splitting is the safe direction: a real
    knowledge base had nine accomplishments filed under one project title, of
    which three were that project and six were five other ones. Company was
    different for every one of those six, so this separates them.

    The cost is that one project written up under two spellings stays as two
    groups, which shows up as a shorter list of candidates rather than as a
    resume claiming one project did another one's work.
    """
    return f"{_norm(chunk.title)}|{_norm(chunk.company)}"


def _build(key: str, members: list[tuple[int, KBChunk]], titles: set[str]) -> Group:
    # Importing the same document twice puts the same accomplishment in twice,
    # and an entry is a place where that becomes visible: three bullets, two of
    # them the same sentence. Deduped here rather than at import because this
    # is where it matters and because the best-ranked copy is the one to keep.
    members = _distinct(members)
    chunks = [chunk for _, chunk in members]
    # A group is worth more for being relevant and worth more again for having
    # several relevant accomplishments, which is what an entry with three
    # bullets needs. Reciprocal rank, so the tenth chunk adds something and
    # cannot outweigh the first.
    score = sum(1.0 / (rank + 1) for rank, _ in members)

    technologies: list[str] = []
    for chunk in chunks:
        for tech in chunk.technologies or []:
            name = str(tech).strip()
            if name and name.lower() not in {t.lower() for t in technologies}:
                technologies.append(name)

    return Group(
        key=key,
        title=_real_title(chunks, titles),
        company=_best(chunks, "company"),
        date_range=_best(chunks, "date_range"),
        context=_best(chunks, "context"),
        technologies=tuple(technologies),
        chunks=tuple(chunks),
        score=score,
    )


def _distinct(members: list[tuple[int, KBChunk]]) -> list[tuple[int, KBChunk]]:
    """One copy of each accomplishment, keeping the best-ranked one."""
    seen: set[str] = set()
    kept = []
    for rank, chunk in members:
        text = _norm(chunk.accomplishment)
        if text and text in seen:
            continue
        seen.add(text)
        kept.append((rank, chunk))
    return kept


def _real_title(chunks: list[KBChunk], titles: set[str]) -> str:
    """What this group is called, preferring a name over a leftover.

    `context` is a description, except when it is exactly the title of another
    entry in the same knowledge base. Then it is a name, and the title beside
    it is a leftover from whichever accomplishment the importer read first. A
    real knowledge base had four accomplishments filed under one project whose
    contexts read "Database Health Analyzer" and "Monte Carlo Portfolio
    Optimization Framework" while their titles all said something else.

    One member is enough to rename the group. Its siblings describe the same
    work in prose and have no such signal, and splitting a group on which of
    its accomplishments the importer happened to label would be worse than the
    naming being wrong.
    """
    for chunk in chunks:
        context = (chunk.context or "").strip()
        if context and _norm(context) in titles and _norm(context) != _norm(chunk.title):
            return context
    return _best(chunks, "title")


def _best(chunks: list[KBChunk], field: str) -> str:
    """The most common non-empty value for a field, longest wins a tie.

    Members disagree: one row calls it "Alfred" and the next "Alfred, an
    autonomous bug-resolution agent". Taking the first would make the heading
    depend on which accomplishment happened to rank highest for this job, so
    the heading would change between two resumes for the same project.
    """
    counts: dict[str, int] = {}
    for chunk in chunks:
        value = (getattr(chunk, field, "") or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return ""
    return max(counts, key=lambda v: (counts[v], len(v)))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#. ]+", " ", (text or "").lower())).strip()
