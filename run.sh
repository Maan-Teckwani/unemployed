#!/usr/bin/env bash
# Sets up whatever is missing, then starts the app. Safe to run every time.
#
# One script for both first run and every run after, because you should not
# have to know which one you are doing. Every step checks before it acts, so
# the second run skips straight to starting the app.
#
# There is no database to install: everything lives in data/jobsearch.db.
#
#   ./run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
WEB="$ROOT/web"
VENV="$BACKEND/.venv/bin/python"

# Which model this machine can actually hold.
#
# The download size is not the number that matters. This app runs the model
# with a 16k context, which roughly doubles it. Measured with `ollama ps`, on
# CPU:
#
#     llama3.2:3b   2.0 GB download   3.9 GB resident
#     llama3.2:1b   1.3 GB download   1.9 GB resident
#
# And the model is not the only thing running. Before it there is already
# around 5 GB in use: the OS, this app's Python backend (which loads a torch
# embedding model), the web server, and a browser with the app open. On top of
# that the person is using their machine for other things.
#
# So 3b wants about 9 GB before its owner opens anything of their own, which is
# why it took 8 GB machines down rather than merely running slowly.
#
# The cut is at 15 rather than 16 because a machine reserves some memory for
# hardware and reports the rest, so a 16 GB laptop says 15.7 and a `>= 16` test
# would quietly send every one of them to the smaller model.
#
# When the amount cannot be read, the small model wins. Being slightly worse is
# recoverable; running the machine out of memory is not.
total_ram_gb() {
  if [ -r /proc/meminfo ]; then
    awk '/^MemTotal:/ { printf "%d", $2 / 1048576 }' /proc/meminfo
  elif have sysctl; then
    echo $(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
  else
    echo 0
  fi
}

# What each model holds while running, rounded up, and what it costs to fetch.
# Plain case statements rather than associative arrays: macOS still ships bash
# 3.2, where `declare -A` is a syntax error.
model_memory_gb() {
  case "$1" in
    llama3.2:1b) echo 2 ;;
    llama3.2:3b) echo 4 ;;
    llama3.1:8b) echo 9 ;;
    *) echo 0 ;;
  esac
}
model_download() {
  case "$1" in
    llama3.2:1b) echo "1.3 GB" ;;
    llama3.2:3b) echo "2 GB" ;;
    llama3.1:8b) echo "4.7 GB" ;;
    *) echo "" ;;
  esac
}

# The OS, this app's backend, the web server and a browser, before the model.
OVERHEAD_GB=5

# The model named in .env, if any. That is what the backend will load whatever
# this script decides, so it is what this script has to use too.
pinned_model() {
  [ -f "$ROOT/.env" ] || return 0
  sed -n 's/^[[:space:]]*OLLAMA_MODEL[[:space:]]*=[[:space:]]*\([^[:space:]]*\).*/\1/p' \
    "$ROOT/.env" | head -1
}

say() { printf "\n==> %s\n" "$1"; }
ok() { printf "    %s\n" "$1"; }
die() { printf "\n%s\n" "$1" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

need() {
  have "$1" || die "$2 is not installed.
  $3
  Then open a new terminal and run this script again."
}

# Put Homebrew on the PATH, installing it first if it is not here at all.
#
# Apple Silicon puts brew in /opt/homebrew and Intel in /usr/local, and neither
# is on the PATH of a shell that has never seen it, so `shellenv` does that part
# rather than us guessing.
#
# The installer needs sudo, which means macOS asks for the login password. That
# is the operating system asking, not this script, and it cannot be suppressed.
# Saying so first is the difference between an expected prompt and an alarming
# one. NONINTERACTIVE stops brew adding a second prompt of its own on top.
setup_brew() {
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$candidate" ] && eval "$("$candidate" shellenv)" && return 0
  done
  have brew && return 0

  say "Installing Homebrew"
  ok "macOS will ask for your login password. That is macOS, not this script."
  NONINTERACTIVE=1 /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || true

  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$candidate" ] && eval "$("$candidate" shellenv)" && return 0
  done
  have brew
}

# Install $2 with Homebrew if $1 is missing, then fall back to the old message.
#
# Success is "the command resolves now", never brew's exit code, for the same
# reason as on Windows: brew reports failure for benign outcomes such as the
# formula already being installed.
ensure() {
  have "$1" && return 0
  if setup_brew; then
    say "Installing $3"
    brew install "$2" || true
    have "$1" && { ok "$3 installed"; return 0; }
  fi
  die "$3 is not installed, and installing it here did not work.
  $4
  Then open a new terminal and run this script again."
}

# --- 1. Prerequisites -------------------------------------------------------
say "Checking prerequisites"
if [ "$(uname)" = "Darwin" ]; then
  HINT_NODE="brew install node"; HINT_PY="brew install python@3.12"
  HINT_OLLAMA="brew install ollama"

  # The formula, not the cask. It gives a plain CLI with no .app to launch,
  # which is what the `ollama serve` handling below already expects.
  ensure node node "Node.js" "$HINT_NODE"
  ensure python3 python@3.12 "Python" "$HINT_PY"
  ensure ollama ollama "Ollama" "$HINT_OLLAMA"
else
  # Linux keeps naming what is missing rather than installing it. The install
  # routes here vary by distribution and every one of them wants sudo, which is
  # a much bigger thing to do unasked than a per user Homebrew.
  HINT_NODE="sudo apt install nodejs npm"; HINT_PY="sudo apt install python3 python3-venv"
  HINT_OLLAMA="curl -fsSL https://ollama.com/install.sh | sh"

  need node "Node.js" "$HINT_NODE"
  need python3 "Python" "$HINT_PY"
  need ollama "Ollama" "$HINT_OLLAMA"
fi

# Only a floor, not a ceiling: requirements.txt uses minimum bounds so pip
# resolves whatever has wheels for this interpreter.
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || die "Python 3.10 or newer is required (found $(python3 --version)).
  $HINT_PY"
ok "node, python and ollama all present"

# --- 2. Model ---------------------------------------------------------------
say "Checking the language model"
# `brew install ollama` installs the binary but starts no server, so every
# ollama command would fail with a connection error. Start one ourselves if
# nothing is listening; a desktop install that already runs is left alone.
if ! curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
  ok "Starting the Ollama server..."
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  waited=0
  until curl -sf http://localhost:11434/api/version >/dev/null 2>&1; do
    sleep 2; waited=$((waited + 2))
    [ "$waited" -ge 60 ] && die "Ollama would not start. See /tmp/ollama-serve.log"
  done
fi

RAM_GB="$(total_ram_gb)"
PINNED="$(pinned_model)"
if [ -n "$PINNED" ]; then
  MODEL="$PINNED"
  ok "$MODEL is set in .env, so that is what runs (${RAM_GB} GB on this machine)"
  NEEDS="$(model_memory_gb "$MODEL")"
  if [ "$NEEDS" -gt 0 ] && [ $((NEEDS + OVERHEAD_GB)) -gt "$RAM_GB" ]; then
    ok "Warning: $MODEL needs about ${NEEDS} GB while running, and this app plus"
    ok "the OS and a browser already use about ${OVERHEAD_GB} GB of your ${RAM_GB} GB."
    ok "Remove the OLLAMA_MODEL line from .env to let this script choose one that fits."
  fi
else
  if [ "$RAM_GB" -ge 15 ]; then MODEL="llama3.2:3b"; else MODEL="llama3.2:1b"; fi
  ok "${RAM_GB} GB of memory on this machine, so: $MODEL"
  if [ "$RAM_GB" -lt 8 ] && [ "$RAM_GB" -gt 0 ]; then
    ok "That is tight even for this model. Close what you can while the app runs."
  fi
fi

if ! ollama list 2>/dev/null | grep -q "$MODEL"; then
  SIZE="$(model_download "$MODEL")"
  ok "Downloading $MODEL${SIZE:+ (about $SIZE, one time)}..."
  ollama pull "$MODEL" || die "Model download failed. Check your connection and re-run."
fi

# The backend reads OLLAMA_MODEL from .env and has its own default, so a model
# pulled here without being written down is one that gets downloaded and then
# not used.
if [ -z "$PINNED" ]; then
  printf 'OLLAMA_MODEL=%s\n' "$MODEL" >> "$ROOT/.env"
  ok "Wrote OLLAMA_MODEL=$MODEL to .env"
fi
ok "$MODEL ready"

# --- 3. Backend -------------------------------------------------------------
say "Preparing the backend"
[ -x "$VENV" ] || (cd "$BACKEND" && python3 -m venv .venv)

# Has the install already happened? `find_spec` answers that without importing
# anything - importing sentence_transformers drags in PyTorch and takes seconds,
# on every run, to answer a question about file layout.
CHECK='import importlib.util as u; import sys; sys.exit(0 if all(u.find_spec(m) for m in ("fastapi","sentence_transformers","alembic")) else 1)'
if ! "$VENV" -c "$CHECK" >/dev/null 2>&1; then
  ok "Installing Python packages. This is the slow part: three to ten minutes,"
  ok "most of it PyTorch. It has not frozen, and it only happens once."
  "$VENV" -m pip install --disable-pip-version-check -q --upgrade pip
  "$VENV" -m pip install --disable-pip-version-check -r "$BACKEND/requirements.txt"
fi

# Creates data/jobsearch.db on the first run and is a no-op on every one after.
ok "Applying database migrations..."
(cd "$BACKEND" && "$VENV" -m alembic upgrade head)
ok "Backend ready"

# --- 4. Frontend ------------------------------------------------------------
say "Preparing the frontend"
[ -d "$WEB/node_modules" ] || (cd "$WEB" && npm install)
ok "Frontend ready"

# --- 5. Start ---------------------------------------------------------------
say "Starting the app"

# Starting a second copy on a taken port dies on arrival, and the health check
# below would still pass against the *old* one - success that is really someone
# else's process. Refuse instead.
for port in 8000 3000; do
  if curl -sf -m 2 "http://localhost:$port" >/dev/null 2>&1 \
     || curl -sf -m 2 "http://localhost:$port/health" >/dev/null 2>&1; then
    die "Port $port is already in use.
  Another copy of this app is probably still running. Stop it, then run this
  script again."
  fi
done

(cd "$BACKEND" && "$VENV" -m uvicorn app.main:app --reload --port 8000) &
BACK_PID=$!
(cd "$WEB" && npm run dev) &
WEB_PID=$!

# Ctrl+C should take the whole app down, not orphan half of it.
trap 'kill $BACK_PID $WEB_PID 2>/dev/null || true' INT TERM EXIT

waited=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  sleep 2; waited=$((waited + 2))
  [ "$waited" -ge 120 ] && die "The backend did not come up. Check the output above."
done

printf "\n  The app is running at http://localhost:3000\n"
printf "  Press Ctrl+C to stop. Next time, just run this script again.\n\n"
wait
