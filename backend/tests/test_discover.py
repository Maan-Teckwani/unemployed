"""Finding a company's board by reading its careers page.

Guessing a slug from a name works when the board is named after the company and
fails silently when it is not. Razorpay is on Greenhouse as
"razorpaysoftwareprivatelimited", and for that reason was counted as having no
public board at all. The careers page links to the real one.
"""
import pytest

from app.ingestion import discover


def test_domains_are_guessed_in_and_com() -> None:
    """Half the seed list is Indian and half of those are not on .com. Guessing
    only .com found one company in a hundred and twenty."""
    assert discover.domain_variants("Groww") == ["groww.com", "groww.in"]
    assert "urban-company.in" in discover.domain_variants("Urban Company")


def test_a_name_too_short_to_be_a_domain_is_skipped() -> None:
    assert discover.domain_variants("X") == []


@pytest.mark.parametrize(
    ("html", "platform", "slug"),
    [
        (
            '<a href="https://boards.greenhouse.io/razorpaysoftwareprivatelimited">Jobs</a>',
            "greenhouse",
            "razorpaysoftwareprivatelimited",
        ),
        (
            '<iframe src="https://boards.greenhouse.io/embed/job_board?for=acme"></iframe>',
            "greenhouse",
            "acme",
        ),
        ('<a href="https://job-boards.greenhouse.io/acme">x</a>', "greenhouse", "acme"),
        ('<a href="https://jobs.lever.co/paytm">Careers</a>', "lever", "paytm"),
        ('<a href="https://jobs.ashbyhq.com/atlan/x">Careers</a>', "ashby", "atlan"),
        (
            '<a href="https://careers.smartrecruiters.com/Freshworks">x</a>',
            "smartrecruiters",
            "Freshworks",
        ),
        ('<a href="https://hygraph.recruitee.com/o/x">x</a>', "recruitee", "hygraph"),
    ],
)
def test_the_slug_is_read_out_of_the_link(monkeypatch, html, platform, slug) -> None:
    seen = []

    def probe(p, s):
        seen.append((p, s))
        return [{"id": 1}] if (p, s) == (platform, slug) else None

    monkeypatch.setattr(discover, "probe", probe)
    monkeypatch.setattr(discover, "matched_job_count", lambda p, e, r: 3)

    found = discover._board_in(html, "india")
    assert found == {
        "source": platform,
        "token": slug,
        "total_jobs": 1,
        "matched_jobs": 3,
    }


def test_a_board_with_nothing_for_this_region_is_not_a_match(monkeypatch) -> None:
    """Slugs collide across vendors, so a board that resolves but lists nothing
    you could apply to is a different company with the same name."""
    monkeypatch.setattr(discover, "probe", lambda p, s: [{"id": 1}])
    monkeypatch.setattr(discover, "matched_job_count", lambda p, e, r: 0)
    assert discover._board_in('<a href="https://jobs.lever.co/acme">x</a>', "india") is None


def test_workday_is_resolved_rather_than_probed(monkeypatch) -> None:
    """It has no slug to probe: its API path needs a tenant the URL does not
    carry, so the link goes to the connector's own resolver."""
    monkeypatch.setattr(discover, "probe", lambda p, s: pytest.fail("probed workday"))
    monkeypatch.setattr(
        discover.workday,
        "resolve",
        lambda url, region: {"source": "workday", "token": "t", "total_jobs": 5,
                             "matched_jobs": 5},
    )
    html = '<a href="https://citi.wd5.myworkdayjobs.com/en-US/2/userHome">Careers</a>'
    assert discover._board_in(html, "india")["source"] == "workday"


def test_a_page_naming_no_board_is_not_a_match(monkeypatch) -> None:
    monkeypatch.setattr(discover, "probe", lambda p, s: pytest.fail("probed nothing"))
    assert discover._board_in("<h1>Come work with us</h1>", "india") is None


def test_the_page_is_looked_for_at_the_usual_addresses(monkeypatch) -> None:
    tried = []

    def read(url):
        tried.append(url)
        return None

    monkeypatch.setattr(discover, "_read", read)
    assert discover.find_via_careers_page("Acme", "india") is None
    assert tried[:3] == [
        "https://careers.acme.com",
        "https://acme.com/careers",
        "https://jobs.acme.com",
    ]
    assert "https://careers.acme.in" in tried


def test_the_url_we_landed_on_counts_as_much_as_the_page(monkeypatch) -> None:
    """Plenty of careers domains are a redirect straight onto the board, so the
    final URL is the answer and the body is empty of links."""
    monkeypatch.setattr(
        discover, "_read", lambda url: "https://jobs.lever.co/acme <html></html>"
    )
    monkeypatch.setattr(discover, "probe", lambda p, s: [{"id": 1}])
    monkeypatch.setattr(discover, "matched_job_count", lambda p, e, r: 2)
    found = discover.find_via_careers_page("Acme", "india")
    assert (found["source"], found["token"], found["name"]) == ("lever", "acme", "Acme")


def test_guessing_still_runs_first(monkeypatch) -> None:
    """Reading a careers page costs several requests against someone else's
    site. It is the fallback, not the first move."""
    monkeypatch.setattr(discover, "probe", lambda p, s: [{"id": 1}])
    monkeypatch.setattr(discover, "matched_job_count", lambda p, e, r: 1)
    monkeypatch.setattr(
        discover, "find_via_careers_page", lambda n, r: pytest.fail("read a page too early")
    )
    assert discover.find_company("Atlan", "india")["token"] == "atlan"


def test_progress_is_reported_as_answers_come_back(monkeypatch) -> None:
    """A sweep is minutes long now, and a bar that sits at zero until the end
    looks like a hang."""
    monkeypatch.setattr(discover, "find_company", lambda n, r: None)
    seen = []
    discover.discover(["A", "B", "C"], "india", on_progress=lambda d, t, m: seen.append((d, t)))
    assert seen == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.parametrize(
    ("name", "token", "belongs"),
    [
        # Real finds, including the awkward ones.
        ("Razorpay", "razorpaysoftwareprivatelimited", True),
        ("Meilisearch", "meili", True),
        ("Oyster HR", "oyster", True),
        ("Fractal Analytics", "fractal.wd1/fractal/Careers", True),
        ("BrowserStack", "browserstack.wd3/browserstack/External", True),
        ("Paytm", "paytm", True),
        # The one that made this necessary: jobs.remote.com is Remote's job
        # board product and lists other companies' openings, so the seed name
        # "Remote" came back as the Greenhouse board "alphasense".
        ("Remote", "alphasense", False),
        # The price of the rule. Hotstar's board is "jiostar" after the rename,
        # and a company filed under the wrong name is worse than one missing.
        ("Hotstar", "jiostar.wd102/jiostar/JioStar", False),
    ],
)
def test_a_page_may_link_to_someone_else_s_board(name, token, belongs) -> None:
    assert discover._belongs_to(name, token) is belongs


def test_the_guard_is_only_on_the_page_route(monkeypatch) -> None:
    """The slug probes build the slug from the name, so they cannot pick up a
    board belonging to a different company and do not pay for this check."""
    monkeypatch.setattr(discover, "probe", lambda p, s: [{"id": 1}])
    monkeypatch.setattr(discover, "matched_job_count", lambda p, e, r: 1)
    assert discover.find_company("Atlan", "india")["token"] == "atlan"


def test_a_board_belonging_to_someone_else_is_not_returned(monkeypatch) -> None:
    monkeypatch.setattr(
        discover, "_read", lambda url: 'x <a href="https://boards.greenhouse.io/alphasense">j</a>'
    )
    monkeypatch.setattr(discover, "probe", lambda p, s: [{"id": 1}])
    monkeypatch.setattr(discover, "matched_job_count", lambda p, e, r: 9)
    assert discover.find_via_careers_page("Remote", "india") is None
