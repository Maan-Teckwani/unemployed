# Plan: shipping this as an open-source project

**Status:** planned — not yet built.
**Goal:** any student can clone the repo, run one command, and be looking at
ranked jobs within an hour — on their own machine, with their own local LLM, with
no API keys and no data leaving their laptop.

---

## Why this is worth doing

The product currently assumes *this* laptop: a Windows path in every command, a
pre-seeded database, a company list tuned to one person's target roles, and a
setup that took a week of sprints to converge. None of that is a code problem —
it's a **distribution** problem, and it's the whole distance between "my project"
and "a thing 500 students use".

The honest framing for a reader: every student doing an off-campus job hunt is
doing this work manually — trawling boards, guessing fit, rewriting resumes,
hunting for referrals. The software already exists. It just isn't installable.

---

## The hard problems (and how each is solved)

### 1. Setup must survive a first-time user

Today a new user needs Docker *and* Python *and* Node, must run four CLI commands
in the right order, and hits a 2 GB model download with no progress indication.
Any one of those loses most people.

**Solution: one command, and a first-run wizard for everything else.**

```bash
docker compose up
```

That must be genuinely sufficient. To get there:

- **Model pull moves inside the stack.** An `init` service pulls the default
  model on first boot and reports progress, instead of a README instruction
  people skip and then hit confusing 404s from Ollama.
- **Migrations run automatically** on API start (already true in the `app`
  profile).
- **Discovery and first ingest run automatically** on an empty database, so a new
  user sees jobs without knowing the CLI exists.
- **Setup status endpoint + UI banner**: "Downloading model (1.2 / 2.0 GB)",
  "Fetching jobs from 92 companies", "Scoring 220 jobs — 12 min left". Long
  silent waits read as breakage.

### 2. Onboarding replaces the CLI

A first-run flow in the UI, in this order, because each step gates the next:

1. **Profile** — name, contact, education, college.
2. **Import** — upload resume/documents → review parsed chunks → save.
   Blocking: matching is meaningless without a knowledge base.
3. **Filters** — role families, max years, preferred locations.
4. **Fetch jobs** — a button, not a terminal command.

Each screen states plainly why it's needed and how long it takes.

### 3. Hardware reality

An 8 GB laptop cannot run an 8B model comfortably, and a student who tries will
conclude the project is broken.

- **Detect available RAM at setup** and recommend accordingly:
  `llama3.2:3b` (~4 GB free), `llama3.1:8b` (~10 GB free).
- **Support an existing native Ollama** — many people already have one. Detect
  it on `11434` and offer to use it rather than pulling a second copy of the same
  model into a container. (The current 11435 port choice already anticipates this.)
  The local `run.sh` flow now probes `11434`, attempts a stale-process cleanup,
  and prints concrete recovery steps when bind errors occur.
- **State the time cost honestly up front**: scoring 100 jobs takes ~40 minutes on
  CPU. Surprise is worse than slowness.

### 4. It must not be India-only in the code

The filters are correct for the current user and wrong for everyone else. This is
the biggest *code* change in the release.

- Move `INDIA_TERMS` / `FOREIGN_TERMS` into a **region profile** (`india`, `us`,
  `eu`, `global`) selected in settings — same logic, different data.
- Ship the company seed list as **`companies.example.py`** plus regional lists, so
  a US student isn't stuck with Indian fintech and vice versa.
- Keep experience/seniority/role-family logic as-is: it's region-independent.

### 5. Privacy has to be provable, not claimed

The single strongest reason to trust this over a hosted resume tool: **your career
history never leaves your machine.** That claim has to be verifiable.

- A `PRIVACY.md` naming every outbound request the app makes: public job-board
  APIs, and nothing else. No telemetry, ever.
- The knowledge base and job history stay in one local SQLite file
  (`data/jobsearch.db`), which is also what makes "delete everything" honest.
  Generated resumes delete themselves after ten minutes.
- Export/delete-everything buttons in settings.

---

## Repo layout

```
job-search-assistant/
  README.md              # what it is, one-command setup, screenshots
  PRIVACY.md             # every network call, stated plainly
  CONTRIBUTING.md        # how to add a connector or a region
  LICENSE                # MIT
  .env.example
  docker-compose.yml     # full stack, profiles for dev vs all-in
  docs/
    ARCHITECTURE.md      # the diagram + why each decision
    FILTERING.md         # (exists) how filtering works
    OPEN_SOURCE.md       # this file
  backend/  web/         # unchanged
  landing/               # static one-pager (see below)
  .github/
    workflows/ci.yml     # pytest + eval on push
    ISSUE_TEMPLATE/
```

---

## The landing page

Deployed to Vercel free tier with a Neon serverless Postgres database for the signup wall. Built from the **existing UI's**
styling — same fonts, same restraint — so the page looks like the product rather
than a marketing site bolted on.

Structure:

1. **One sentence** on what it does, and the fact that it runs locally and free.
2. **The install command**, visible without scrolling, copy-button included.
3. **The unique bit — a "watch it think" walkthrough.** Not a feature list and
   not a video. An interactive strip that replays one real job through the
   pipeline, with real data from a demo dataset:

   ```
   1,925 jobs   →   filtered: 1,705        →   scored: 220   →   your list: 25
                    (senior · off-domain
                     · too many years —
                     every one with a reason)
   ```

   Click any stage and it expands to show actual examples: which jobs were cut and
   why, a real score decomposed into its five features, a resume bullet with a
   line drawn back to the accomplishment it came from.

   This works as the hero because **explainability is the product**. Every
   competitor shows a number; this shows the arithmetic. A visitor understands the
   whole system in thirty seconds, and it doubles as the strongest possible
   argument that the output is trustworthy.

4. **Three screenshots**: today's list, the "why" breakdown, a generated resume
   with source links.
5. **Link to the repo.** The app itself runs locally with no signup. The landing page includes an optional "wall" where visitors leave a name, country, and gender to get an avatar, and signing in with Google keeps their email address so there is a way to reach them. Nothing about the wall touches the local tool, whose privacy claim is about your resume never leaving your laptop.

---

## Work breakdown (one sprint)

| # | Task | Verify |
|---|---|---|
| 1 | `init` service: model pull with progress; auto-migrate; auto-discover on empty DB | Fresh clone → `docker compose up` → jobs visible, no CLI |
| 2 | Setup-status endpoint + UI progress banner | Banner shows model download and first ingest |
| 3 | First-run wizard (profile → import → filters → fetch) | New user reaches a ranked list without reading docs |
| 4 | Region profiles; `companies.example.py` + regional seed lists | Switch region → filters and companies change; tests pass per region |
| 5 | RAM detection + model recommendation; reuse native Ollama if present | 8 GB machine is steered to 3b; existing Ollama is detected |
| 6 | README rewrite, PRIVACY.md, CONTRIBUTING.md, LICENSE, screenshots | A stranger can follow it start to finish |
| 7 | Landing page with the interactive pipeline walkthrough and signup wall | Deploys to Vercel + Neon; walkthrough uses real demo data |
| 8 | CI: pytest + eval harness on push | Green badge; a seeded regression fails the build |
| 9 | **Clean-machine test** | Wipe volumes, fresh clone, follow README exactly, time it |

**Task 9 is the real acceptance test.** Everything else is a guess about what a
new user experiences; that one measures it. Target: **under 60 minutes** from
`git clone` to a ranked list, most of it unattended download and scoring.

---

## Deliberately out of scope

- **A hosted version.** It would require paying for LLM inference, storing other
  people's resumes, and defending that data — abandoning the local-first property
  that makes the project worth trusting.
- **Accounts, teams, sharing.** Single-user local software needs none of it.
- **A browser extension.** Real value, but a separate distribution problem with
  its own review process. After v1.
