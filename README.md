# AI Career Assistant

Finds jobs you can actually get, scores them so you can see *why*, and writes a
tailored resume grounded in work you've really done.

Built for **students and new grads**. Pick your region (India, US, UK, Europe,
Canada, Australia, Singapore, or anywhere), your target roles, and how much
experience you have — the filters follow.

Runs entirely on your machine. **No API keys, no paid services, no data leaves
your laptop.**

---

## What it does

**1. Finds jobs.** Reads public job boards from 90+ companies across Greenhouse,
Lever, Ashby and SmartRecruiters — Paytm, Meesho, PhonePe, Freshworks, Stripe,
Databricks, Notion, and more. **Search for any company by name** in settings: if
it has a public board on any of those platforms, one click adds it.

**2. Filters hard.** Drops senior roles, roles wanting more experience than you
have, non-engineering roles, and jobs outside your region. Every exclusion
carries a reason you can read.

**3. Scores explainably.** No black box — five weighted features you can inspect:

```
score = 0.30·required-skill coverage
      + 0.25·semantic similarity
      + 0.15·preferred-skill coverage
      + 0.15·keyword overlap
      + 0.15·preference fit
```

**4. Writes a truthful resume.** RAG over your own experience. Every bullet is
traced to a real accomplishment you entered — anything the model can't trace, or
any metric it invents, is rejected before it reaches the page. One-page,
single-column, ATS-parseable PDF, verified by round-tripping it through a text
extractor.

**5. Helps you get referred.** Builds targeted searches for the five kinds of
people worth contacting (alumni, recruiters, engineering leaders, people already
in the role, founders) plus a short grounded opening message. **Nothing is
scraped** — you run the search, so your LinkedIn account is never at risk.

**6. Suggests what to build.** One portfolio project specific to that company,
aimed at the skills the role wants that your experience can't yet prove.

---

## Setup

**You need nothing set up first.** On Windows and macOS the script installs
[Python 3.10+](https://www.python.org/downloads/), [Node 20+](https://nodejs.org/)
and [Ollama](https://ollama.com/download) itself if they are missing, using
winget or Homebrew. On Linux it names what is missing and gives you the command.

**No database to install, and no Docker.** Everything is stored in one SQLite
file at `data/jobsearch.db` — see [Why SQLite](#why-sqlite).

First, Git, which is what fetches the code. Safe to run if you already have it:

**Windows** `winget install Git.Git -e` ·
**macOS** `xcode-select --install` ·
**Linux** `sudo apt install git -y`

Then:

```bash
git clone https://github.com/Maan-Teckwani/unemployed.git
```
```bash
cd unemployed
```

**Windows**
```bash
.\run.cmd
```

**macOS / Linux**
```bash
./run.sh
```

`run.cmd` just launches `run.ps1` with the execution-policy flag Windows needs
for unsigned scripts, so you do not have to type it. Double-clicking it in
Explorer works too. `powershell -ExecutionPolicy Bypass -File .\run.ps1` still
works if you prefer it.

That's the whole setup. The script downloads the model, builds the virtual
environment, installs both dependency trees, creates the database, launches the
backend and frontend, and opens the app.

First run takes about ten minutes — PyTorch and a 2 GB model. **Run the exact
same command every time after**: every step checks before it acts, so later
runs skip straight to starting the app. There is nothing else to remember, and
no `.env` file to write.

Open **http://localhost:3000**.

<details>
<summary>Running it by hand instead</summary>

The script is only doing this, and nothing is stopping you doing it yourself.
Once:
```bash
ollama pull llama3.2:3b
```
Terminal 1 — backend (`python3` and `.venv/bin/python` on macOS/Linux):
```bash
cd backend && python -m venv .venv && .venv\Scripts\python.exe -m pip install -r requirements.txt
```
```bash
.venv\Scripts\python.exe -m alembic upgrade head
```
```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
Terminal 2 — frontend:
```bash
cd web && npm install && npm run dev
```
</details>

<details>
<summary>Coming from the Postgres version?</summary>

Earlier builds kept everything in Postgres. To bring that data across, start
the old container, then run this once — it reads Postgres and writes the new
SQLite file, changing nothing on the Postgres side:
```bash
cd backend && .venv\Scripts\python.exe -m app.db.migrate_from_postgres
```
Once you're happy the app looks right, the container and its volume can go:
```bash
docker rm -f jobsearch-postgres && docker volume rm jobsearch_pgdata
```
</details>

<details>
<summary>Everything in Docker instead</summary>

No host Python, Node or Ollama; hot reload is the trade:
```bash
docker compose --profile app up -d
```
This adds a containerised Ollama on port **11435** and an `init` service that
pulls the model in the background — watch it with `docker logs -f jobsearch-init`.
Nothing waits on it, so open **http://localhost:3000** right away; scoring just
won't produce results until the model finishes.
</details>

> Every `python -m app...` command below assumes `backend/.venv` is activated,
> or is run as `.venv\Scripts\python.exe -m app...`.

---

## First run

1. **Profile** — name, email, education, and your college (used to find alumni).
2. **Import** — upload your resume and any project/achievement documents. They're
   parsed into accomplishment "chunks" that you review and edit before saving.
   *This is the most important step: match and resume quality are bounded by how
   rich your knowledge base is.* The first import is slower than the rest: it
   downloads the embedding model (~130 MB, once, cached on disk after that).
3. **Filters** — **your region**, role families, max years of experience, and
   preferred locations. Set the region first: it decides which jobs are even
   stored.
4. **Find companies** (once, ~5 min) — ships with 90+ already discovered, so this
   is only needed if you want more:
   ```bash
   python -m app.ingestion.discover
   ```
   Or search for companies by name in **Filters → Companies**, one at a time.
5. **Fetch jobs** (~2 min):
   ```bash
   python -m app.ingestion.run
   ```
6. **Score them** (~40 min — this is the local LLM working):
   ```bash
   python -m app.ingestion.enrich --top 100
   ```
7. Open **http://localhost:3000** and start applying.

In the Docker profile, steps 5–6 run automatically once a day.

---

## Using a different model

Any Ollama model works. Bigger models write better resume bullets but are slower:

```bash
ollama pull llama3.1:8b
```
Then copy `.env.example` to `.env` at the repo root, set
`OLLAMA_MODEL=llama3.1:8b`, and restart the backend. `llama3.2:3b` is the
default because it runs comfortably on 8 GB of RAM; with 16 GB or more,
`llama3.1:8b` writes noticeably better resume bullets. Whatever you set has to
show up in `ollama list`.

On the all-in-Docker path the model lives in the container instead, so pull it
there — `docker exec jobsearch-ollama ollama pull llama3.1:8b`. That container
publishes `11435` precisely so it can't collide with a native install on
`11434`.

---

## Adding companies

**From the UI:** *Filters → Companies* → type a name → **Search** → **Add**. It
probes all four ATS platforms live and tells you which one hosts them.

**In bulk:** add names to `backend/app/connectors/companies.py`, then:
```bash
python -m app.ingestion.discover
```

Either way, a board is only accepted if it actually has jobs in **your region** —
board slugs collide across vendors (Ashby's `navi` is a US startup, not the Indian
neobank), so this check is what stops the wrong company being added.

---

## Checking it still works

```bash
python -m pytest tests/ -q
```
```bash
python -m app.eval.run
```
The eval prints extraction quality, filter leaks, and resume traceability against
your live data. `0 filter leak(s)` means nothing is slipping past the filters.

---

## How it's built

| | |
|---|---|
| Backend | FastAPI · SQLAlchemy · Alembic |
| Database | SQLite (one file, `data/jobsearch.db`) |
| Embeddings | `bge-small-en-v1.5` (384-dim, local) |
| LLM | Ollama (`llama3.2:3b` by default) |
| Frontend | Next.js · Tailwind · shadcn/ui |

**Where AI is used:** extracting requirements from job descriptions, embedding
for semantic search, generating resume bullets, drafting outreach, designing
project ideas.

**Where it deliberately isn't:** ranking is a transparent weighted formula, not
"ask the model if it's a good match". Deduplication, expiry, seniority and role
classification, and years-of-experience parsing are all deterministic — faster,
free, testable, and they don't change their mind between runs.

### Why SQLite

This ran on PostgreSQL with pgvector first. Moving to SQLite deleted the single
biggest source of setup failure — Docker, WSL2, a reboot, a port, a container,
a volume — for one user running one app on their own laptop.

The reason it costs nothing here is that Postgres was never doing Postgres-shaped
work. Vector similarity had **two** SQL call sites, both searching the knowledge
base: one person's career, a few dozen rows. The expensive path — scoring
thousands of jobs — already computed similarity in numpy, and the original
schema declined to build a vector index at all, on the grounds that "with a
personal KB (tens of chunks) an exact scan is fine". Those two queries moved
into numpy and joined the code that was already there. Nothing ever queried
*inside* an array or JSON document either, so those columns became plain JSON.

What SQLite genuinely costs: concurrent writes are serialised. The app does have
two writers — the API and the ingestion pipeline, which runs for tens of minutes
— so the database is opened in WAL mode with a busy timeout, letting reads
continue during writes instead of the UI freezing mid-fetch. See
[`app/db/session.py`](backend/app/db/session.py).

The honest limit: this would be the wrong call for multiple concurrent users, or
a knowledge base of ~100k chunks where brute-force similarity stops being free.
Neither describes one person's job search.

### Resumes expire

Generated resumes are deleted ten minutes after they're made, along with their
PDFs. A resume is derived from the knowledge base and the job — both stored
permanently — so keeping it duplicates data the app already has. In the LaTeX
case that duplicate is your entire Overleaf document. Regenerating costs one
model call and reflects your *current* knowledge base, which a stored copy
wouldn't. See [`app/db/retention.py`](backend/app/db/retention.py).

See [TEST_FLOW.md](TEST_FLOW.md) for a manual walkthrough of every feature.

## Useful checks
- API health: http://localhost:8000/health
- API docs (Swagger): http://localhost:8000/docs
- DB shell: `sqlite3 data/jobsearch.db` — or open that file in any SQLite viewer
- Back it up: copy `data/jobsearch.db` somewhere. That one file is everything.
