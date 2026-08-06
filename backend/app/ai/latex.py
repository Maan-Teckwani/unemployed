"""Tailor the user's own LaTeX resume instead of replacing it.

Someone who already has an Overleaf resume does not want ours. So we take their
document verbatim, rewrite the wording inside four sections, and hand the whole
thing back — same preamble, same macros, same layout, same fonts.

The design is defensive because a LaTeX document is code: one unbalanced brace
and it does not compile, and the user finds out in Overleaf rather than here.

* **Only section bodies are touched.** `tailor()` splices rewritten bodies back
  into the original string, so the preamble is byte-identical by construction —
  there is nothing to check because there is nothing that can change it.
* **One LLM call per section**, never one call for the document. Small models
  answer the easy part of a big schema and drop the hard part (the lesson from
  Sprint 4), and a single bad call would otherwise poison the whole file.
* **`validate()` is the safety net, not the prompt.** A rewritten body that
  fails any check is discarded and the original body is kept. A resume that is
  slightly less tailored beats one that will not compile.
"""
import re
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

from app.ai import latex_entries
from app.ai.generate_resume import _invented_numbers, _numbers
from app.ai.kb_groups import Group, describe, group_chunks
from app.ai.latex_entries import Entry, find_entries
from app.ai.llm import fits_context, generate_json
from app.db.models import KBChunk

# Headings vary by template, so match them loosely. Order matters: the first
# keyword found in the heading wins, and "Technical Skills" must not be read as
# an experience section just because some template calls it "Skills & Experience".
#
# Projects goes first because a heading naming both wins for projects. Real
# templates title a projects section "Product Experience & Projects", and read
# as experience it gets the wrong rewrite rules and the wrong candidates. A
# heading naming only one of the two is unaffected either way.
_HEADING_MAP = (
    ("projects", ("project",)),
    ("experience", ("experience", "employment", "internship", "work history")),
    ("certifications", ("certification", "certificate", "licens", "course")),
    ("skills", ("skill", "technolog")),
)

REWRITABLE = tuple(name for name, _ in _HEADING_MAP)

# Sections whose entries are the content: losing one loses a real credential or
# a real keyword. Experience and projects are prose, where rewording is the job.
_LIST_SECTIONS = ("skills", "certifications")

_SECTION_RE = re.compile(r"\\section\*?\s*\{")
_COMMAND_RE = re.compile(r"\\([a-zA-Z]+)")


class Section(NamedTuple):
    """One `\\section{...}` and the span of its body in the original document."""

    name: str  # one of REWRITABLE, or "" when the heading maps to nothing we touch
    heading: str  # as written, e.g. "Work Experience"
    start: int  # index of the first character after the heading
    end: int  # index just past the last character of the body


def find_sections(latex: str) -> list[Section]:
    """Every section in the document, each body running to the next one."""
    sections: list[Section] = []
    document_end = latex.find("\\end{document}")
    if document_end == -1:
        document_end = len(latex)

    starts = [
        (m.start(), m.end() - 1) for m in _SECTION_RE.finditer(latex) if m.start() < document_end
    ]
    for index, (command_start, brace_start) in enumerate(starts):
        brace_end = _matching_brace(latex, brace_start)
        if brace_end is None:
            continue  # malformed \section{ with no closing brace: skip, don't guess
        body_end = starts[index + 1][0] if index + 1 < len(starts) else document_end
        body_end = _trim_trailing_notes(latex, brace_end + 1, body_end)
        heading = _heading_text(latex[brace_start + 1 : brace_end])
        sections.append(
            Section(_canonical(heading), heading, brace_end + 1, max(brace_end + 1, body_end))
        )
    return sections


def tailor(latex: str, chunks: list[KBChunk], requirements: dict) -> tuple[str, list[dict]]:
    """Rewrite what we may, keep what we must. Returns (document, per-section report).

    Sections are worked on at the same time and spliced afterwards, back to
    front so earlier spans keep their indices. They are independent by
    construction: each one reads a span of the original and writes a
    replacement for that span, and nothing crosses between them. Doing them one
    after another meant the user waited for the sum of four model calls to get
    an answer that was ready in the time of the slowest.
    """
    sections = [s for s in find_sections(latex) if s.name in REWRITABLE]
    if not sections:
        return latex, []

    with ThreadPoolExecutor(max_workers=len(sections)) as pool:
        done = list(pool.map(lambda s: _tailor_section(latex, s, chunks, requirements), sections))

    out = latex
    for section, (candidate, entry) in reversed(list(zip(sections, done))):
        if candidate is not None:
            out = out[: section.start] + candidate + out[section.end :]
    return out, [entry for _, entry in done]


def _tailor_section(
    latex: str, section: Section, chunks: list[KBChunk], requirements: dict
) -> tuple[str | None, dict]:
    """One section's replacement text, or None to keep it, plus what happened."""
    original = latex[section.start : section.end]
    entry = {
        "name": section.name,
        "heading": section.heading,
        "rewritten": False,
        "mode": "kept",
    }

    try:
        # Choosing entries is strictly better when it is available: it can put
        # a project on the page that the template never mentioned, which
        # rewording never can. It is only available in sections whose entries
        # repeat and whose headings vary only inside braces, so most sections
        # still take the path below.
        candidate = rebuild_entries(section.name, original, chunks, requirements, entry)
        if candidate is None:
            candidate = rewrite_section(section.name, original, chunks, requirements)
            entry["mode"] = "rewrite"
            if candidate is None:
                # Nothing in here is a sentence we may replace: a heading line,
                # or bullets built out of macros. There is no call to make, so
                # none is made.
                entry["mode"] = "kept"
                entry["reason"] = "this section has no free text to reword"
                return None, entry
        else:
            entry["mode"] = "entries"
        # A tripwire rather than a filter for the entries path: it changes only
        # the contents of brace groups that held no command, so an altered
        # command sequence means this module has a bug, not that a model
        # misbehaved. For the reworded path it is the real check on the words.
        problem = validate(original, candidate, chunks, section.name)
    except Exception as e:  # noqa: BLE001 - one dead section must not lose the rest
        entry["reason"] = f"the model failed: {e}"
        return None, entry

    if problem:
        entry["reason"] = problem
        entry["mode"] = "kept"
        entry.pop("entries", None)
        return None, entry

    entry["rewritten"] = True
    return candidate, entry


_SYSTEM = r"""You improve the wording of individual resume lines for one specific job.

You are given numbered lines from one section of a resume, and the candidate's verified record. You return improved lines. You never see or write LaTeX, markup or formatting of any kind: these are sentences.

WHAT YOU CHANGE
- Rewrite a line so it leads with what was built or achieved, in strong past tense, one sentence.
- Where the record genuinely supports it, use the target job's own words for the same thing: if the line says "REST services" and the job says "RESTful APIs", write "RESTful APIs". This is vocabulary matching, not claim making.
- Put the detail this job asks about first within the line. Same fact, better order.

WHAT YOU MUST NOT CHANGE
- Employers, job titles, institutions, product names, locations, dates and links are facts. Keep them exactly, even if a different one would suit the job better.
- Never state a number, percentage, duration or scale that is not already in the line you are rewriting or in the record below.
- Never claim a technology the record does not show. If the job wants Kubernetes and the candidate has never used it, the line stays as it is.

RETURNING A LINE UNCHANGED
Leave a line out of your answer entirely if it cannot be improved truthfully. That is the expected answer for a certificate, a course title, or a line that is already sharp. Returning two of five lines is fine.

Respond with JSON in exactly this shape:
{"lines":[{"index":0,"text":"Built X using Y, cutting Z"},{"index":3,"text":"..."}]}"""

# What "rewrite" means depends entirely on the section. Told only to improve the
# wording, a model turned "Oracle Cloud Infrastructure 2025 AI Foundations
# Associate" into "Successfully designed and implemented cloud strategies" — a
# certificate rewritten as a claim, which is both false and a lost credential.
_SECTION_RULES = {
    "experience": (
        "This section is bullets about work the candidate did. Rewrite the "
        "sentences. Keep every employer, title and date exactly as written."
    ),
    "projects": (
        "This section is bullets about things the candidate built. Rewrite the "
        "sentences. Keep every project name and technology exactly as written."
    ),
    "skills": (
        "This section is a LIST of skills, not prose. Never turn an entry into a "
        "sentence — a screener reads this as keywords. You may reorder items so "
        "the ones this job asks for come first, and you may relabel a group to "
        "the job's wording. Never drop a skill and never add one."
    ),
    "certifications": (
        "These are the names of real certificates and who issued them. They are "
        "not achievements to describe. Change nothing except, at most, the order "
        "— most relevant to this job first. Returning this section byte-identical "
        "is the expected answer."
    ),
}


def rewrite_section(
    name: str,
    body: str,
    chunks: list[KBChunk],
    requirements: dict,
) -> str | None:
    """Reword this section's sentences, or None if it has none we may touch.

    The model is sent the sentences and nothing else. It used to be sent the
    whole section and asked to return it "character for character, except for
    the human-readable sentences inside it", which is a bad deal three times
    over: a 3b model spends most of its output retyping LaTeX, it is slow in
    proportion to how much it retypes, and the one thing it most often gets
    wrong is the retyping. Measured on a real resume, that shape took nine
    minutes and produced a usable rewrite for one section out of four.

    Now only the sentences move. The LaTeX around them cannot change because
    it is never sent, and `validate` becomes a check on the words rather than
    a wall against the structure.
    """
    holes = latex_entries.find_sentences(body)
    if not holes:
        return None

    required = list(requirements.get("required_skills", []))
    preferred = list(requirements.get("preferred_skills", []))
    responsibilities = list(requirements.get("responsibilities", []))[:6]

    facts = "\n".join(
        f"[{i}] {c.title}"
        + (f" — {c.company}" if c.company else "")
        + f"\n    {c.accomplishment}"
        + (f"\n    Impact: {c.impact}" if c.impact else "")
        + (f"\n    Technologies: {', '.join(c.technologies)}" if c.technologies else "")
        for i, c in enumerate(_fit_facts(chunks), start=1)
    )
    lines = "\n".join(f"[{i}] {body[h.start : h.end]}" for i, h in enumerate(holes))
    prompt = (
        f"THIS SECTION: {_SECTION_RULES.get(name, '')}\n\n"
        "TARGET JOB\n"
        f"Required skills: {', '.join(required) or 'not specified'}\n"
        f"Preferred skills: {', '.join(preferred) or 'not specified'}\n"
        + (f"Responsibilities: {'; '.join(responsibilities)}\n" if responsibilities else "")
        + "\nUse these words only where the accomplishments below already justify them.\n\n"
        f"THE CANDIDATE'S VERIFIED RECORD (the only facts that exist):\n{facts}\n\n"
        f"THE LINES TO IMPROVE:\n{lines}"
    )
    # Sized to the answer. A small model asked for JSON does not stop when it
    # has said everything: given a cap of 1500 it emits 1500, which at the
    # thirteen tokens a second a 3b model manages on a laptop CPU is two
    # minutes of padding per section. One rewritten line is about fifty tokens.
    raw = generate_json(
        _SYSTEM, prompt, timeout=300, max_tokens=min(900, 120 + 70 * len(holes))
    )

    values: dict[latex_entries.Hole, str] = {}
    for item in raw.get("lines") or []:
        if not isinstance(item, dict):
            continue
        index = _as_index(item.get("index"), len(holes))
        text = str(item.get("text") or "").strip()
        # An unchanged line is a valid answer and costs nothing to skip.
        if index is None or not text or text == body[holes[index].start : holes[index].end]:
            continue
        values[holes[index]] = latex_entries.escape(text)

    return latex_entries.fill(body, values) if values else None


def _fit_facts(chunks: list[KBChunk], budget: int = 1800) -> list[KBChunk]:
    """As much of the record as fits a sane prompt, best first.

    The whole knowledge base used to go into every call. It arrives ranked, so
    a cap costs the least relevant accomplishments and buys back the prompt
    time that a local model pays on every one of them: a laptop CPU reads
    about fifty tokens a second, so nine thousand characters of record is a
    minute of waiting before the model writes anything. Rewording needs the
    record only to know which words are already earned, and the accomplishments
    that answer that are the ones this job ranked to the top.
    """
    kept, used = [], 0
    for chunk in chunks:
        used += len(chunk.accomplishment or "") + len(chunk.title or "") + 40
        if used > budget and kept:
            break
        kept.append(chunk)
    return kept


_SELECT_SYSTEM = """You are choosing which of a candidate's real projects belong on their resume for one specific job, and writing the bullets for each.

You are given every project and job the candidate has, numbered, with their real accomplishments under them. You are filling a fixed number of slots on a page that already exists.

CHOOSING
- Read all of them before choosing. The best evidence for this job is often not the first one listed.
- Pick the ones this job actually asks for, strongest first. A project that shows the required skills beats a bigger project that does not.
- Use each project at most once.
- Fill every slot.

WRITING
- Each slot needs EXACTLY the number of bullets it asks for, no more and no fewer.
- Every bullet must come from ONE accomplishment of the project filling that slot, and must carry that accomplishment's id in "source_id".
- Start with a strong past-tense verb. One sentence, at most 30 words.
- Where the accomplishment genuinely supports it, use the job's own words for the same thing: if it says "RESTful APIs" and the accomplishment says "REST services", write "RESTful APIs".
- Never state a number, percentage or scale that is not already in the accomplishment you cite.
- Never claim a technology the accomplishment does not show.

Respond with JSON in exactly this shape:
{"slots":[{"project":2,"bullets":[{"source_id":17,"text":"Built X using Y"},{"source_id":18,"text":"..."}]}]}"""


def rebuild_entries(
    name: str,
    body: str,
    chunks: list[KBChunk],
    requirements: dict,
    report: dict,
) -> str | None:
    r"""Refill this section's entries from the knowledge base, or None to decline.

    This is the part rewording cannot do. A candidate with nine projects and a
    template with three slots should see the three that fit this job, not the
    three that happened to be in the file when they uploaded it.

    Declining is the common answer and is never a failure: the caller falls
    back to rewording, which is what every section did before this existed.
    Everything that could produce a half-filled or self-contradicting section
    declines instead, so there is no state where one slot is a chosen project
    and the next is a leftover from the template.
    """
    # A skills or certifications section is a list of facts, not entries with
    # bullets. `find_entries` would already decline for the templates we have
    # seen, but relying on that would make this correct by accident.
    if name in _LIST_SECTIONS:
        return None

    entries = find_entries(body)
    if entries is None:
        return None

    groups = group_chunks(chunks)
    if len(groups) < len(entries):
        return None  # nothing to choose between: rewording is the honest answer

    roles = _hole_roles(body, entries)
    # Everything that can rule this section out is checked before any model
    # call, not after. Both of these used to be discovered in the loop that
    # renders the answer, which meant a section that could never be filled
    # still paid for the most expensive call in the file to find that out. On a
    # real resume that was two calls and six minutes spent on a decision that
    # needed neither.
    #
    # A slot can only be filled by a project with at least as many
    # accomplishments as it has bullets, because writing four bullets from two
    # facts is how invention starts. And every hole in the heading must have
    # something in the knowledge base to put in it: a template that prints a
    # link next to each project has a hole nothing here can write, and filling
    # the rest would leave one project's link under another project's name.
    needed = max(len(e.bullets) for e in entries)
    smallest = min(len(e.bullets) for e in entries)
    big_enough = [g for g in groups if len(g.chunks) >= smallest]
    usable = [g for g in big_enough if _hole_values(roles, g) is not None]

    if not usable and big_enough:
        report["entries_declined"] = (
            "each entry here shows a link, and the knowledge base does not "
            "store one, so swapping a project in would leave the old project's "
            "link beside the new project's name"
            if "link" in roles
            else "these headings have more fields than the knowledge base can "
            "fill, so a swapped-in project would keep some of the old one's "
            "details"
        )
        return None
    if len(usable) < len(entries):
        report["entries_declined"] = (
            f"fewer than {len(entries)} projects in the knowledge base have "
            "enough accomplishments to fill this section's entries"
        )
        return None

    # A shortlist, not the whole knowledge base. Twenty eight projects in one
    # prompt is both slow and, measurably, too much to hold: asked to fill four
    # slots from that many, a 3b model returned two. They arrive ranked, so the
    # ones that go are the ones least like this job.
    usable = _fit_groups(name, entries, usable[: len(entries) * 3], requirements, needed)

    plan = _select(name, entries, usable, requirements, needed)
    chosen_by = "model"
    if plan is None:
        # The model could not produce a usable plan. Ranking still can, and a
        # section built from the best-matching projects in the candidate's own
        # words beats one built from whichever projects were in the file on the
        # day it was uploaded. Nothing here is generated, so nothing here can
        # be invented.
        plan = _default_plan(entries, usable)
        chosen_by = "ranking"
    if plan is None:
        return None
    report["chosen_by"] = chosen_by

    values: dict[latex_entries.Hole, str] = {}
    chosen: list[dict] = []
    for entry, slot in zip(entries, plan):
        group = usable[slot["project"]]
        lead = _hole_values(roles, group)
        if lead is None:
            return None
        for hole, value in zip(entry.lead, lead):
            values[hole] = latex_entries.escape(value)
        for hole, bullet in zip(entry.bullets, slot["bullets"]):
            values[latex_entries.Hole(hole.start, hole.end)] = latex_entries.escape(
                bullet["text"]
            )
        chosen.append(
            {
                "title": group.title,
                "chunk_ids": [b["source_id"] for b in slot["bullets"]],
                "bullets": [b["text"] for b in slot["bullets"]],
            }
        )

    report["entries"] = chosen
    return latex_entries.fill(body, values)


def _select(
    name: str, entries: list[Entry], groups: list[Group], requirements: dict, detail: int
) -> list[dict] | None:
    """One call: which project fills each slot, and what its bullets say.

    Everything the model returns is checked against the groups it was shown. A
    slot citing an accomplishment from a different project, or returning two
    bullets where the template has three, fails the whole section rather than
    that slot, because a section half rebuilt and half left alone can show the
    same project twice.
    """
    slots = "\n".join(
        f"Slot {i + 1}: {len(entry.bullets)} bullet(s)" for i, entry in enumerate(entries)
    )
    catalogue = "\n\n".join(
        f"PROJECT {i}\n{describe(group, limit=detail)}" for i, group in enumerate(groups)
    )
    prompt = _select_prompt(name, slots, catalogue, requirements)
    # Sized to the answer rather than to what might fit, with room to spare.
    # Too tight is not a smaller answer, it is a truncated one: the JSON stops
    # mid-string and fails to parse.
    wanted = sum(len(e.bullets) for e in entries)
    try:
        raw = generate_json(
            _SELECT_SYSTEM, prompt, timeout=300, max_tokens=min(1500, 250 + 90 * wanted)
        )
    except Exception:  # noqa: BLE001
        # A model that times out, disconnects or returns half a JSON object is
        # the same answer as one that chooses badly: there is no plan. Ranking
        # still has one, and letting this escape would lose the whole section
        # to a fallback that was sitting right there.
        return None

    plan = raw.get("slots")
    if not isinstance(plan, list) or len(plan) != len(entries):
        return None

    used: set[int] = set()
    out: list[dict] = []
    for entry, slot in zip(entries, plan):
        if not isinstance(slot, dict):
            return None
        index = _as_index(slot.get("project"), len(groups))
        if index is None or index in used:
            return None
        used.add(index)

        allowed = {c.id: c for c in groups[index].chunks}
        bullets = slot.get("bullets")
        if not isinstance(bullets, list) or len(bullets) != len(entry.bullets):
            return None

        kept = []
        for item in bullets:
            if not isinstance(item, dict):
                return None
            text = str(item.get("text") or "").strip()
            source = allowed.get(_as_index(item.get("source_id"), None))
            if not text or source is None:
                return None
            # Checked against the one accomplishment it cites, not against the
            # whole knowledge base: a figure that is true of another project is
            # still a false claim about this one.
            if _invented_numbers(text, source):
                return None
            kept.append({"source_id": source.id, "text": text})

        out.append({"project": index, "bullets": kept})
    return out


def _default_plan(entries: list[Entry], groups: list[Group]) -> list[dict] | None:
    """The same choice, made by ranking instead of by a model.

    Each slot takes the best-matching project not already used that has enough
    accomplishments to fill it, and the bullets are those accomplishments as
    the candidate wrote them. Untailored phrasing, but the projects are still
    chosen for this job, and a sentence copied out of the knowledge base cannot
    claim anything the knowledge base does not.

    This is what runs when the local model is too small to answer, which on a
    3b model is often. Without it the feature is only as good as the weakest
    model someone happens to be running.
    """
    remaining = list(range(len(groups)))  # already best first
    plan = []
    for entry in entries:
        want = len(entry.bullets)
        pick = next((i for i in remaining if len(groups[i].chunks) >= want), None)
        if pick is None:
            return None
        remaining.remove(pick)
        plan.append(
            {
                "project": pick,
                "bullets": [
                    {"source_id": c.id, "text": (c.accomplishment or "").strip()}
                    for c in groups[pick].chunks[:want]
                ],
            }
        )
    return plan


def _select_prompt(name: str, slots: str, catalogue: str, requirements: dict) -> str:
    required = list(requirements.get("required_skills", []))
    preferred = list(requirements.get("preferred_skills", []))
    responsibilities = list(requirements.get("responsibilities", []))[:6]
    return (
        f"THIS SECTION: {_SECTION_RULES.get(name, '')}\n\n"
        "TARGET JOB\n"
        f"Required skills: {', '.join(required) or 'not specified'}\n"
        f"Preferred skills: {', '.join(preferred) or 'not specified'}\n"
        + (f"Responsibilities: {'; '.join(responsibilities)}\n" if responsibilities else "")
        + f"\nSLOTS TO FILL (in order, on the page):\n{slots}\n\n"
        f"THE CANDIDATE'S PROJECTS (the only facts that exist):\n{catalogue}"
    )


def _fit_groups(
    name: str, entries: list[Entry], groups: list[Group], requirements: dict, detail: int
) -> list[Group]:
    """Drop the least relevant projects until the prompt fits the context window.

    Ollama truncates the front of an oversized prompt without saying so, which
    reads as the model having ignored the best half of a career. Groups go
    whole rather than losing chunks from each: a project short of its
    accomplishments cannot fill a slot, so trimming that way would starve the
    slots instead of shortening the list.
    """
    kept = list(groups)
    slots = "\n".join(f"Slot {i + 1}: {len(e.bullets)} bullet(s)" for i, e in enumerate(entries))
    while len(kept) > len(entries):
        catalogue = "\n\n".join(
            f"PROJECT {i}\n{describe(g, limit=detail)}" for i, g in enumerate(kept)
        )
        if fits_context(_SELECT_SYSTEM, _select_prompt(name, slots, catalogue, requirements), 2000):
            break
        kept = kept[: max(len(entries), len(kept) // 2)]
    return kept


def _hole_roles(body: str, entries: list[Entry]) -> list[str]:
    """What each heading position holds, voted on across the entries."""
    return [
        latex_entries.hole_role([body[e.lead[i].start : e.lead[i].end] for e in entries])
        for i in range(len(entries[0].lead))
    ]


def _hole_values(roles: list[str], group: Group) -> list[str] | None:
    """The heading for one chosen project, or None if it cannot be written.

    All of it or none of it. A heading with a new project name beside the old
    project's dates is worse than the untouched template, and it is the one
    failure here that compiles cleanly and reads as true.
    """
    values: list[str] = []
    text_holes = 0
    for role in roles:
        if role == "link":
            return None  # nothing in the knowledge base is a URL
        if role == "empty":
            values.append("")  # the author left it blank; leaving it blank is faithful
            continue
        if role == "date":
            value = group.date_range
        elif text_holes == 0:
            value = group.title
        elif text_holes == 1:
            # The second line of a heading is a subtitle: what this was built
            # with, or what it was. Technologies first because they are the
            # part a screener reads, and `context` is whatever the importer
            # had left over.
            value = ", ".join(group.technologies[:4]) or group.context
        else:
            return None  # a third free-text position has nothing to fill it
        if not value:
            return None
        if role != "date":
            text_holes += 1
        values.append(value)
    return values


def _as_index(value, limit: int | None) -> int | None:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    if limit is None:
        return index
    return index if 0 <= index < limit else None


def validate(
    original: str, rewritten: str, chunks: list[KBChunk], section: str = ""
) -> str:
    """Why this rewrite must be thrown away, or "" if it is safe to use.

    Every check answers one of two questions: could this break the document, or
    could it put something on the page the candidate cannot back up? Both were
    learned from watching a real model: it dropped a `\\resumeSubHeadingListEnd`
    (leaving an `itemize` open inside a macro, where a `\\begin`/`\\end` count
    never sees it) and it renamed an employer to one that fits the job better.
    """
    if not rewritten.strip():
        return "the model returned nothing"

    if _brace_depth(rewritten) != 0:
        return "unbalanced braces"

    # Same commands, same count, same order. Anything else is a structural edit,
    # and structure is not the model's to change — only the words between it are.
    if _command_sequence(rewritten) != _command_sequence(original):
        return "the LaTeX structure changed (commands added, dropped or reordered)"

    if _environments(rewritten) != _environments(original):
        return "\\begin/\\end environments do not match the original"

    known_numbers = set(_numbers(original)) | set(_facts_numbers(chunks))
    invented = [n for n in _numbers(rewritten) if n not in known_numbers]
    if invented:
        return "invented numbers: " + ", ".join(sorted(set(invented))[:5])

    unsupported = _unsupported_names(rewritten, _vocabulary(original, chunks))
    if unsupported:
        return "invented names: " + ", ".join(sorted(set(unsupported))[:5])

    # In a list section the entries ARE the facts, so losing one is the failure:
    # "Product Management using Agentic AI -- IIT Patna x Masai" came back as
    # "Successfully designed product management strategies" — nothing invented,
    # every other check satisfied, and the certificate gone.
    #
    # Prose sections are exempt. There, rewording is the whole point, and a
    # rephrased bullet that drops a parenthetical is an editorial call the user
    # reviews — not a lost credential.
    if section in _LIST_SECTIONS:
        dropped = _dropped_names(original, rewritten)
        if dropped:
            return "dropped entries the original listed: " + ", ".join(sorted(dropped)[:5])

    return ""


def _trim_trailing_notes(latex: str, start: int, end: int) -> int:
    r"""Pull the section body back off the blank lines and `% ----- NEXT -----`
    banner that sit between it and the following section.

    Those belong to the next heading, not this body. Sending them to the model
    only gives it something of the author's to lose — and it did lose them.
    """
    lines = latex[start:end].split("\n")
    while lines and (not lines[-1].strip() or lines[-1].lstrip().startswith("%")):
        lines.pop()
    return start + len("\n".join(lines))


def _matching_brace(text: str, open_index: int) -> int | None:
    """Index of the `}` closing the `{` at open_index, honouring nesting."""
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{" and not _escaped(text, i):
            depth += 1
        elif text[i] == "}" and not _escaped(text, i):
            depth -= 1
            if depth == 0:
                return i
    return None


def _escaped(text: str, index: int) -> bool:
    r"""True for a literal `\{`, which is a character rather than a group."""
    backslashes = 0
    while index - 1 - backslashes >= 0 and text[index - 1 - backslashes] == "\\":
        backslashes += 1
    return backslashes % 2 == 1


def _brace_depth(text: str) -> int:
    depth = 0
    for i, char in enumerate(text):
        if char in "{}" and not _escaped(text, i):
            depth += 1 if char == "{" else -1
        if depth < 0:
            return depth  # a `}` before its `{` — broken however it ends up
    return depth


def _environments(text: str) -> dict[str, int]:
    """Counts of `\\begin{x}` minus nothing — `\\end{x}` is counted separately so
    a rewrite that drops one of a pair is caught."""
    counts: dict[str, int] = {}
    for kind, name in re.findall(r"\\(begin|end)\s*\{([^}]*)\}", text):
        key = f"{kind}:{name}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _command_sequence(text: str) -> list[str]:
    return _COMMAND_RE.findall(text)


def _facts_numbers(chunks: list[KBChunk]) -> list[str]:
    return [n for c in chunks for n in _numbers(_chunk_text(c))]


def _vocabulary(original: str, chunks: list[KBChunk]) -> set[str]:
    """Every word the candidate can already point at: this section, plus the KB.

    The job's own skill list is deliberately NOT in here. Letting the model reach
    for a JD keyword the candidate has never used is exactly the keyword-stuffing
    the rest of the product refuses to do.
    """
    blob = original + " " + " ".join(_chunk_text(c) for c in chunks)
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z+#.]*", blob)}


# A name the candidate cannot back up looks like one of two things, and neither
# is ordinary prose: a run of capitalised words ("AWS Partner Ecosystem", "Cloud
# Engineer") or an acronym ("AWS", "GCP"). Single capitalised words are NOT
# checked — "Designed", "Proficient" and "Successfully" are English, and flagging
# them rejected every rewrite while catching nothing.
# No "." inside a word here, or "API. Improved throughput" reads as one phrase
# spanning the full stop between two sentences.
_PROPER_PHRASE = re.compile(r"\b[A-Z][a-zA-Z+#]*(?:\s+[A-Z][a-zA-Z+#]*)+")
_ACRONYM = re.compile(r"\b[A-Z]{2,}(?:[+#]|\b)")


def _unsupported_names(text: str, vocabulary: set[str]) -> list[str]:
    """Employers, products and technologies that appear from nowhere.

    This is the check that catches a model renaming an employer to suit the job —
    the failure a brace count and a number check both sail straight past.
    """
    candidates = _PROPER_PHRASE.findall(text) + _ACRONYM.findall(text)
    unsupported = []
    for candidate in candidates:
        words = [w for w in re.split(r"\s+", candidate) if len(w) >= 3]
        missing = [w for w in words if not _known(w.lower(), vocabulary)]
        # In a phrase, a single unknown word at the front is a sentence starting
        # with a capital in front of a name the candidate does own — "Earned
        # Oracle Cloud Infrastructure". The name is what matters, and it checks
        # out. A lone unknown acronym has no such excuse.
        forgivable = len(words) > 1 and missing == words[:1]
        if missing and not forgivable:
            unsupported.append(candidate.strip())
    return unsupported


def _dropped_names(original: str, rewritten: str) -> set[str]:
    """Names the original stated that the rewrite no longer mentions.

    Only the same proper phrases and acronyms the addition check looks at: an
    employer, an institution, a certificate, a technology.
    """
    source = _without_comments(original)
    present = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z+#]*", rewritten)}
    dropped = set()
    for name in _PROPER_PHRASE.findall(source) + _ACRONYM.findall(source):
        for word in re.split(r"\s+", name):
            if len(word) >= 3 and word.lower() not in present:
                dropped.add(name.strip())
    return dropped


def _without_comments(latex: str) -> str:
    r"""Drop `% ...` lines. Templates label their sections with comment banners
    (`% ----- EXPERIENCE -----`), and a model that reformats naturally drops
    them. Those are notes to the author, not facts about the candidate."""
    return re.sub(r"(?<!\\)%.*", "", latex)


def _known(word: str, vocabulary: set[str]) -> bool:
    """Tolerant match, so "Postgres" in the KB covers "PostgreSQL" on the page."""
    stem = word[:5]
    return any(known == word or known.startswith(stem) or word.startswith(known[:5])
               for known in vocabulary if len(known) >= 3)


def _chunk_text(chunk: KBChunk) -> str:
    r"""Everything about a chunk the page is allowed to say.

    Company, context and dates are in here because entries are now filled from
    the knowledge base, not just reworded. Without them, writing a real
    employer into a real heading reads as an invented name and every rebuilt
    entry is rejected by the check meant to catch the opposite mistake.
    """
    return (
        f"{chunk.title} {chunk.company or ''} {chunk.context or ''} "
        f"{chunk.date_range or ''} {chunk.accomplishment} {chunk.impact or ''} "
        f"{' '.join(chunk.technologies or [])}"
    )


def _heading_text(raw: str) -> str:
    r"""`\textbf{Work Experience}` -> "Work Experience"."""
    text = re.sub(r"\\[a-zA-Z]+\s*", " ", raw)  # drop \textbf, \scshape, ...
    text = re.sub(r"\\(.)", r"\1", text)  # unescape \& so it reads as "Skills & Competencies"
    text = re.sub(r"[{}]", " ", text)
    return re.sub(r"\s+", " ", text).strip() or raw


def _canonical(heading: str) -> str:
    lowered = heading.lower()
    for name, keywords in _HEADING_MAP:
        if any(word in lowered for word in keywords):
            return name
    return ""


