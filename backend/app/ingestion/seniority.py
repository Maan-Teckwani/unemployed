"""Is this title plausibly open to a fresher / new grad?

This runs *before* the LLM on purpose. Deciding "Senior Staff Engineer" is not a
fresher role takes a regex and 0ms; asking a local model costs ~25s. Skipping
clearly-senior postings up front removes hours from every enrichment run.

Deliberately conservative: it only rejects titles that are unambiguously senior,
because a wrongly-dropped job is invisible, while a wrongly-kept one just ranks low.
"""
import re

# Ranks nobody enters at, whatever the rest of the title says
# ("Associate Director" is still a director).
_HARD_SENIOR_RE = re.compile(
    r"\b(staff|principal|director|vp|vice\s+president|head|chief|president|"
    r"distinguished|fellow)\b",
    re.IGNORECASE,
)

# Explicit entry-level signals ("Associate Product Manager" is a grad role).
_FRESHER_RE = re.compile(
    r"\b(intern|internship|trainee|apprentice|graduate|new\s+grad|fresher|"
    r"campus|entry[\s-]?level|junior|jr\.?|associate)\b",
    re.IGNORECASE,
)

# Whole-word matches only: "Manager" must not fire on "Managed Services".
# "Intermediate" is GitLab's (and others') word for mid-level — it reads junior
# but is not, so it belongs here.
_SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|lead|leader|manager|mgr|architect|expert|"
    r"intermediate|mid[\s-]?level|experienced)\b",
    re.IGNORECASE,
)

# Level markers: "Engineer II" and up are not entry level ("Engineer I" is).
_LEVEL_RE = re.compile(r"\b(ii|iii|iv|2|3|4|5)\b", re.IGNORECASE)

# "Member of Technical Staff" is not a staff-level rank. It is the ordinary
# individual-contributor title at Pure Storage, VMware, Nutanix and Oracle, and
# new grads are hired into it. Read literally it contains "staff" and every one
# of them was dropped as unambiguously senior: on a real database that was
# twenty four jobs, including "Member of Technical Staff" with nothing else in
# the title at all.
#
# Removed rather than exempted, so the rest of the title still decides. "MTS -
# Systems Architect" is senior because of the architect, and "Member of
# Technical Staff, Senior Backend" because of the senior.
_TECHNICAL_STAFF_RE = re.compile(
    r"\bmember of (the )?technical staff\b|\bmts\b", re.IGNORECASE
)


def is_fresher_friendly(title: str) -> bool:
    """True if a 0-experience candidate could plausibly apply.

    Order matters: hard-senior ranks win over entry-level words, which in turn
    win over softer seniority hints.
    """
    text = _TECHNICAL_STAFF_RE.sub(" ", title or "")
    if _HARD_SENIOR_RE.search(text):
        return False
    if _FRESHER_RE.search(text):
        return True
    if _SENIOR_RE.search(text):
        return False
    return not _LEVEL_RE.search(text)
