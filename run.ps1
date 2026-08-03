<#
.SYNOPSIS
  Sets up whatever is missing, then starts the app. Safe to run every time.

.DESCRIPTION
  One script for both first run and every run after, because a student on a
  borrowed laptop should not have to know which one they are doing. Every step
  checks before it acts, so the second run skips straight to starting the app.

  Usage (from the repo root):
      powershell -ExecutionPolicy Bypass -File .\run.ps1

  The -ExecutionPolicy flag is in the documented command on purpose: unsigned
  scripts are blocked by default on Windows, and that failure looks like the
  project is broken rather than like a machine setting.

  There is no database to install. The app stores everything in data/jobsearch.db.
#>

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Web = Join-Path $Root "web"
$Venv = Join-Path $Backend ".venv\Scripts\python.exe"
$Model = "llama3.2:3b"

function Say($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "    $msg" -ForegroundColor DarkGray }

function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Update-Path {
    <#
      Put anything just installed onto this process's PATH.

      An installer writes the machine and user PATH into the registry, but a
      process that is already running keeps the copy it started with. That is
      the entire reason this script used to end with "open a NEW terminal and
      run this again" after naming something missing. Rebuilding the variable
      here lets the install and the thing that needs it happen in one run,
      which is the difference between four commands and a scavenger hunt.
    #>
    $parts = @(
        [Environment]::GetEnvironmentVariable("Path", "Machine"),
        [Environment]::GetEnvironmentVariable("Path", "User")
    ) | Where-Object { $_ }
    $env:Path = $parts -join ";"

    # Ollama installs per user, and is the one most likely to be left off the
    # PATH we can see even after a refresh.
    $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
    if ((Test-Path $ollama) -and ($env:Path -notlike "*$ollama*")) {
        $env:Path = "$env:Path;$ollama"
    }
}

function Install-Winget($name, $id) {
    <#
      Install one package and refresh the PATH. Says nothing about whether it
      worked; every caller decides that by looking for the command afterwards.

      winget is left to write straight to the console because this can be a
      long download and a silent screen reads as a hang. $ErrorActionPreference
      is relaxed around it for the reason described on Probe below: under
      "Stop", anything a native command puts on stderr becomes a terminating
      error, and winget is chatty on stderr even when it succeeds.
    #>
    if (-not (Have "winget")) { return }

    Say "Installing $name"
    Ok "Windows may ask for permission. Say yes."

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # --silent keeps the vendor installer's own windows out of the way. The
        # two agreement flags stop winget stopping to ask a question nobody is
        # watching for.
        $flags = @(
            "install", "--id", $id, "-e", "--source", "winget", "--silent",
            "--accept-package-agreements", "--accept-source-agreements"
        )
        & winget @flags
    } finally {
        $ErrorActionPreference = $previous
    }

    Update-Path
}

function Ensure($cmd, $name, $id, $how) {
    <#
      Install $name if $cmd is missing, and say so plainly if that did not work.

      Success is "the command resolves now", never winget's exit code. winget
      reports non-zero for perfectly good outcomes, the package already being
      present among them, so its exit code answers a different question from
      the one being asked here.

      Every failure path ends exactly where this function used to begin: name
      the tool, print the command to run by hand, stop. Installing things
      automatically can leave someone better off than before, never worse.
    #>
    if (Have $cmd) { return }

    Install-Winget $name $id
    if (Have $cmd) { Ok "$name installed"; return }

    Write-Host "`n$name is not installed, and installing it here did not work." -ForegroundColor Red
    Write-Host "  $how"
    Write-Host "  Then open a NEW terminal and run this script again."
    exit 1
}

function Probe($block) {
    <#
      Run a native command that is *allowed* to fail, and return its stdout.

      $ErrorActionPreference = "Stop" makes PowerShell 5.1 treat anything a
      native executable writes to stderr as a terminating error - even when the
      exit code is 0. Every check below is asking a question whose answer may
      legitimately be "no" ("are the packages installed?", "does this python
      work?"), and "no" is usually delivered as a traceback on stderr. Without
      relaxing the preference here, finding out that work is needed aborts the
      script instead of doing the work.
    #>
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { return (& $block 2>$null | Out-String).Trim() }
    catch { return "" }
    finally { $ErrorActionPreference = $previous }
}

function Find-Python {
    <#
      The name of an interpreter that actually runs and is new enough, or null.

      Bare `python` on Windows is frequently the Microsoft Store stub, which
      prints nothing and opens the Store instead of running, so this proves an
      interpreter works rather than trusting that the name resolves. The `py`
      launcher is tried first because it is the one that survives that.

      Being a function rather than a block of script matters now: it is asked
      twice, once before installing Python and once after, and the second call
      is the one that has to notice what the first call could not see.
    #>
    foreach ($candidate in @("py", "python", "python3")) {
        if (-not (Have $candidate)) { continue }
        $version = Probe { & $candidate -c "import sys; print(sys.version_info >= (3, 10))" }
        if ($version -eq "True") { return $candidate }
    }
    return $null
}

# --- 1. Prerequisites -------------------------------------------------------
Say "Checking prerequisites"
Ensure "node" "Node.js" "OpenJS.NodeJS.LTS" "winget install OpenJS.NodeJS.LTS -e"
Ensure "ollama" "Ollama" "Ollama.Ollama" "winget install Ollama.Ollama -e"

# Python is asked for by capability, not by name, so it cannot go through
# Ensure: the Store stub means `python` can resolve while no interpreter
# exists. Install when the search comes back empty, then search again.
$Python = Find-Python
if (-not $Python) {
    Install-Winget "Python" "Python.Python.3.12"
    $Python = Find-Python
}
if (-not $Python) {
    Write-Host "`nNo working Python 3.10 or newer was found, and installing one here did not work." -ForegroundColor Red
    Write-Host "  winget install Python.Python.3.12 -e"
    Write-Host "  Then open a NEW terminal and run this script again."
    exit 1
}
Ok "node, ollama and $Python all present"

# --- 2. Model ---------------------------------------------------------------
Say "Checking the language model"
# Ollama normally runs as a background service, but it can be stopped or not
# yet started after a fresh install - in which case every ollama command fails
# with a connection error rather than saying so.
try { Invoke-WebRequest "http://localhost:11434/api/version" -UseBasicParsing -TimeoutSec 3 | Out-Null }
catch {
    Ok "Starting the Ollama server..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    $waited = 0
    while ($true) {
        Start-Sleep -Seconds 2
        $waited += 2
        try {
            Invoke-WebRequest "http://localhost:11434/api/version" -UseBasicParsing -TimeoutSec 3 | Out-Null
            break
        } catch { }
        if ($waited -ge 60) {
            Write-Host "`nOllama would not start. Try running 'ollama serve' yourself." -ForegroundColor Red
            exit 1
        }
    }
}

$models = Probe { ollama list }
if ($models -notmatch [regex]::Escape($Model)) {
    Ok "Downloading $Model (about 2 GB, one time)..."
    ollama pull $Model
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nModel download failed. Check your connection and re-run." -ForegroundColor Red
        exit 1
    }
}
Ok "$Model ready"

# --- 3. Backend -------------------------------------------------------------
Say "Preparing the backend"
if (-not (Test-Path $Venv)) {
    Ok "Creating the virtual environment..."
    Push-Location $Backend
    try { & $Python -m venv .venv } finally { Pop-Location }
}

# Has the install already happened? `find_spec` answers that without importing
# anything, which matters twice over.
#
# It must not raise: an `import` of a missing module writes a traceback to
# stderr, and with $ErrorActionPreference = "Stop" PowerShell turns a native
# command's stderr into a *terminating* error. So the check for "packages are
# missing" would kill the script instead of installing them - a bug only a
# first-time user could ever hit, since it needs an empty venv to fire.
#
# It is also far quicker: importing sentence_transformers drags in PyTorch and
# takes seconds, on every single run, to answer a question about file layout.
$check = "import importlib.util as u; " +
         "print(all(u.find_spec(m) is not None for m in ('fastapi','sentence_transformers','alembic')))"
$installed = Probe { & $Venv -c $check }

if ($installed -ne "True") {
    Ok "Installing Python packages. This is the slow part: three to ten minutes,"
    Ok "most of it PyTorch. It has not frozen, and it only happens once."
    & $Venv -m pip install --disable-pip-version-check -q --upgrade pip
    & $Venv -m pip install --disable-pip-version-check -r (Join-Path $Backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nInstalling Python packages failed." -ForegroundColor Red
        exit 1
    }
}

# Creates data/jobsearch.db on the first run and is a no-op on every one after.
Ok "Applying database migrations..."
Push-Location $Backend
try {
    & $Venv -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nMigrations failed." -ForegroundColor Red
        exit 1
    }
} finally { Pop-Location }
Ok "Backend ready"

# --- 4. Frontend ------------------------------------------------------------
Say "Preparing the frontend"
if (-not (Test-Path (Join-Path $Web "node_modules"))) {
    Ok "Installing npm packages..."
    Push-Location $Web
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "`nnpm install failed." -ForegroundColor Red
            exit 1
        }
    } finally { Pop-Location }
}
Ok "Frontend ready"

# --- 5. Start ---------------------------------------------------------------
Say "Starting the app"

# Starting a second copy on a taken port produces two windows that die on
# arrival, and the health check below would still pass against the *old* one -
# which looks like success while running someone else's code. Refuse instead.
$busy = @()
foreach ($port in 8000, 3000) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        $busy += $port
    }
}
if ($busy.Count -gt 0) {
    Write-Host "`nPort $($busy -join ' and ') already in use." -ForegroundColor Red
    Write-Host "  Another copy of this app is probably still running. Close its windows,"
    Write-Host "  or free the ports with:"
    Write-Host ""
    Write-Host "    foreach (`$p in 3000,8000) { Get-NetTCPConnection -State Listen -LocalPort `$p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id `$_.OwningProcess -Force } }"
    Write-Host ""
    Write-Host "  Then run this script again."
    exit 1
}

# Separate windows, not background jobs: when something goes wrong later the
# student needs to be able to see the log and Ctrl+C it.
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$Backend'; & '$Venv' -m uvicorn app.main:app --reload --port 8000"
)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$Web'; npm run dev"
)

$waited = 0
while ($true) {
    Start-Sleep -Seconds 2
    $waited += 2
    try {
        $r = Invoke-WebRequest "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { break }
    } catch { }
    if ($waited -ge 120) {
        Write-Host "`nThe backend did not come up. Check the backend window for the error." -ForegroundColor Yellow
        exit 1
    }
}

Start-Sleep -Seconds 3
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "  The app is running at http://localhost:3000" -ForegroundColor Green
Write-Host "  Two new windows opened - closing them stops the app."
Write-Host "  Next time, just run this script again."
Write-Host ""
