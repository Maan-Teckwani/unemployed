"""Central configuration. Reads from environment / .env via pydantic-settings.

Keeping every tunable here (DB URL, model name, embedding dimension) means
swapping the embedding model or database is a config change, not a code change.

The defaults are the local setup — a SQLite file in data/, Ollama installed
natively on 11434 — so a fresh clone runs with no .env at all and nothing to
install but Ollama. A .env only exists to override something.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute, not "..env": the backend is started from backend/ but .env lives at
# the repo root, and a relative env_file is resolved against the *current
# working directory*. Left relative, the root .env is silently never read.
REPO_ROOT = Path(__file__).resolve().parents[2]

# The database is one file holding one person's data. Absolute for the same
# reason .env is: the API starts from backend/ but the `python -m app...` CLIs
# are run from wherever, and a relative sqlite path would quietly create a
# second, empty database next to whichever directory you were standing in.
DB_PATH = REPO_ROOT / "data" / "jobsearch.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    # utf-8-sig, not utf-8: Windows PowerShell writes UTF-8 *with a BOM*, and a
    # BOM makes the first key parse as "﻿DATABASE_URL" — so the first line
    # of the file is the one line that silently does nothing. -sig strips it if
    # present and is identical to utf-8 when it isn't.
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8-sig", extra="ignore"
    )

    # SQLite: no server to install, start, or keep running, which is the whole
    # reason this app no longer needs Docker. A postgresql+psycopg:// URL still
    # works for anyone who would rather point at a real server.
    database_url: str = f"sqlite+pysqlite:///{DB_PATH.as_posix()}"
    # A native Ollama install (the documented setup) owns 11434. The optional
    # docker-compose Ollama publishes 11435 so the two can coexist.
    ollama_url: str = "http://localhost:11434"
    # Local LLM for extraction (and later resume generation). Small + fast by
    # default; the review step catches any mistakes. For higher quality set
    # OLLAMA_MODEL=llama3.1:8b (larger download, slower on CPU).
    ollama_model: str = "llama3.2:3b"

    # Optional: send the LLM work to a hosted model instead of the local one.
    #
    # Everything here is empty by default and the app is complete without it.
    # It exists because a 3b model on a laptop CPU writes about thirteen tokens
    # a second, which is thirty seconds to read one job description and a
    # minute and a half to tailor a resume. The same work against a hosted
    # model is about a second. Nothing else changes: same prompts, same
    # validation, same refusal to print anything the knowledge base cannot back.
    #
    # One OpenAI-compatible code path rather than an adapter per vendor, because
    # Groq, Gemini, OpenRouter and OpenAI all speak it and writing four of them
    # would be four times the code and four times the things that can be wrong.
    #
    #   LLM_BASE_URL=https://api.groq.com/openai/v1
    #   LLM_API_KEY=...
    #   LLM_MODEL=llama-3.3-70b-versatile
    #
    # The key is read from the local .env and sent to that provider and nowhere
    # else. Setting it does mean job descriptions and knowledge base text leave
    # the machine, which is the whole of what the local default protects, so it
    # is opt-in and stays that way.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # ONE embedding model for everything that gets compared (KB + jobs).
    # EMBEDDING_DIM must match the model's output size.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # How long a generated resume is kept before it is deleted, with its PDF.
    # Resumes are derived from the knowledge base and the job, both of which are
    # stored permanently - so keeping them is duplicating data the app already
    # has, and in the LaTeX case that duplicate is the user's whole Overleaf
    # document. Regenerating is one LLM call and reflects the current KB.
    resume_ttl_minutes: int = 10


# Single shared settings instance.
settings = Settings()
