"""Gathering one-accomplishment-per-row back into projects.

The knowledge base stores an accomplishment per row because that is what
retrieval wants. A resume entry is a heading with several bullets under it, so
something has to put the rows back together before anything can choose between
them. These tests are mostly about the ways a real importer gets the fields
wrong, because that is what this has to survive.
"""
from app.ai.kb_groups import describe, group_chunks


class Chunk:
    _next_id = 1

    def __init__(self, title, accomplishment, type="project", company="", context="",
                 date_range="", technologies=None, impact=None):
        self.id = Chunk._next_id
        Chunk._next_id += 1
        self.title = title
        self.accomplishment = accomplishment
        self.type = type
        self.company = company
        self.context = context
        self.date_range = date_range
        self.technologies = technologies or []
        self.impact = impact


def test_accomplishments_sharing_a_project_become_one_entry() -> None:
    chunks = [
        Chunk("MarketPulse", "Built the pipeline", company="Acme"),
        Chunk("MarketPulse", "Shipped alerting", company="Acme"),
        Chunk("PosturePal", "Owned the product"),
    ]
    groups = group_chunks(chunks)
    assert [(g.title, len(g.chunks)) for g in groups] == [
        ("MarketPulse", 2),
        ("PosturePal", 1),
    ]


def test_one_title_over_two_companies_is_two_projects() -> None:
    """The failure this key exists for: an importer filed nine accomplishments
    under one project title, of which six belonged to five other projects. The
    company differed on every one of them."""
    chunks = [
        Chunk("PosturePal", "Built billing", company="PosturePal"),
        Chunk("PosturePal", "Built the data layer", company="PosturePal"),
        Chunk("PosturePal", "Designed a multi-agent system", company="CrewAI"),
    ]
    groups = group_chunks(chunks)
    assert len(groups) == 2
    assert sorted(len(g.chunks) for g in groups) == [1, 2]


def test_a_context_naming_another_project_renames_the_group() -> None:
    """`context` is a description, except when it is exactly another entry's
    title. Then it is the name, and the title beside it is a leftover."""
    chunks = [
        Chunk("Database Health Analyzer", "Scored schema health"),
        Chunk("PosturePal", "Designed the analyzer", company="FastAPI",
              context="Database Health Analyzer"),
    ]
    titles = {g.title for g in group_chunks(chunks)}
    assert titles == {"Database Health Analyzer"}


def test_a_context_that_is_only_a_description_is_left_alone() -> None:
    chunks = [
        Chunk("PosturePal", "Built billing", context="Secure billing subsystem"),
        Chunk("PosturePal", "Shipped the MVP", context="Launch"),
    ]
    assert [g.title for g in group_chunks(chunks)] == ["PosturePal"]


def test_one_labelled_member_renames_the_whole_group() -> None:
    """Its siblings describe the same work in prose and carry no such signal.
    Splitting on which accomplishment the importer happened to label would be
    worse than the naming being wrong."""
    chunks = [
        Chunk("Monte Carlo Portfolio Optimization", "Ran the simulation"),
        Chunk("PosturePal", "Built mean-variance optimisation", company="Python",
              context="Monte Carlo Portfolio Optimization"),
        Chunk("PosturePal", "Tuned the covariance estimator", company="Python",
              context="Statistical modelling work"),
    ]
    groups = group_chunks(chunks)
    mislabelled = next(g for g in groups if len(g.chunks) == 2)
    assert mislabelled.title == "Monte Carlo Portfolio Optimization"
    assert "PosturePal" not in {g.title for g in groups}


def test_a_certificate_is_not_a_project() -> None:
    """A certification is a line in a list. Offering one as a candidate entry
    is how a real credential gets rewritten as a claim."""
    chunks = [
        Chunk("AWS Certified", "Passed the exam", type="certification"),
        Chunk("Python", "Wrote Python", type="skill"),
        Chunk("MarketPulse", "Built the pipeline"),
    ]
    assert [g.title for g in group_chunks(chunks)] == ["MarketPulse"]


def test_relevance_and_depth_both_count() -> None:
    """Chunks arrive ranked against the job. A project with several relevant
    accomplishments outranks one with a single better-placed accomplishment,
    because a three-bullet entry needs three of them."""
    ranked = [
        Chunk("Shallow", "One good thing"),
        Chunk("Deep", "A relevant thing", company="Acme"),
        Chunk("Deep", "Another relevant thing", company="Acme"),
        Chunk("Deep", "A third relevant thing", company="Acme"),
    ]
    assert [g.title for g in group_chunks(ranked)] == ["Deep", "Shallow"]


def test_technologies_are_pooled_without_repeating() -> None:
    chunks = [
        Chunk("MarketPulse", "Built it", company="A", technologies=["Python", "AWS"]),
        Chunk("MarketPulse", "Shipped it", company="A", technologies=["aws", "FastAPI"]),
    ]
    assert group_chunks(chunks)[0].technologies == ("Python", "AWS", "FastAPI")


def test_the_heading_does_not_depend_on_which_bullet_ranked_best() -> None:
    """Members of one group spell the name differently. Taking whichever
    accomplishment ranked highest for this job would make the same project
    appear under two spellings on two resumes for two jobs."""
    def titled(order):
        # Distinct accomplishments, or deduplication leaves one chunk and there
        # is no disagreement left to resolve.
        return group_chunks(
            [Chunk(name, f"did thing {i}", company="X") for i, name in enumerate(order)]
        )[0].title

    assert titled(["Alfred", "ALFRED", "Alfred"]) == "Alfred"
    assert titled(["ALFRED", "Alfred", "Alfred"]) == "Alfred"


def test_describe_cites_ids_the_database_can_answer_for() -> None:
    """Bullets come back citing these numbers, and they are checked against the
    knowledge base rather than against a list this function happened to build."""
    chunk = Chunk("MarketPulse", "Built the pipeline", technologies=["FastAPI"],
                  impact="cut latency in half")
    text = describe(group_chunks([chunk])[0])
    assert f"[{chunk.id}]" in text
    assert "FastAPI" in text
    assert "cut latency in half" in text


def test_an_accomplishment_imported_twice_is_one_bullet() -> None:
    """Importing the same document twice is easy to do and invisible until an
    entry prints three bullets of which two are the same sentence."""
    chunks = [
        Chunk("MarketPulse", "Integrated the Serper API.", company="A"),
        Chunk("MarketPulse", "Integrated the Serper API.", company="A"),
        Chunk("MarketPulse", "Built the pipeline", company="A"),
    ]
    group = group_chunks(chunks)[0]
    assert len(group.chunks) == 2
    assert group.chunks[0].accomplishment == "Integrated the Serper API."


def test_an_empty_knowledge_base_is_no_groups() -> None:
    assert group_chunks([]) == []
