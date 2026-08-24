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

# Everything this run prints, kept on disk.
#
# When setup fails on somebody else's laptop, the only thing they can send back
# is what was on screen, and on a first run most of it has already scrolled
# away. -Force overwrites the previous copy rather than growing forever; the
# run worth reading is always the last one. PowerShell flushes and closes a
# transcript when the process ends, including every `exit 1` below, so there is
# no Stop-Transcript to forget.
#
# It holds every line this script prints, which is enough to say which step
# stopped and why. It does not hold what pip, npm and ollama print: a native
# program writes to the console directly and a transcript only sees a
# pipeline. Routing them through one would take away their progress output,
# and a ten minute PyTorch install with nothing moving on screen is the exact
# thing that makes people close the window.
#
# Failing to open it must not stop the app - a folder this script cannot write
# to is a real situation, and losing the log is not worth losing the run.
$LogFile = Join-Path $Root "setup-log.txt"
try { Start-Transcript -Path $LogFile -Force | Out-Null } catch { }

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

# The three things this app needs, and everything this script knows about
# getting each one. A table rather than arguments threaded through a chain of
# functions, because the download page turned out to matter as much as the
# winget id the moment it became clear winget is not always there.
#
# Admin: Node ships a per-machine MSI and Python's installer writes the `py`
# launcher into C:\Windows, so both need administrator rights. Ollama installs
# into the current user's own folder and must NOT be elevated - installed as
# an administrator it lands in the administrator's profile, along with every
# model it later downloads, where the person who started this cannot see it.
$Prereqs = [ordered]@{
    node = @{
        Name = "Node.js"; Id = "OpenJS.NodeJS.LTS"; Admin = $true
        Url = "https://nodejs.org/en/download"
        Hint = "Download the Windows Installer (.msi) and run it."
    }
    python = @{
        Name = "Python"; Id = "Python.Python.3.12"; Admin = $true
        Url = "https://www.python.org/downloads/windows/"
        Hint = "Run the installer and tick 'Add python.exe to PATH' on the first screen."
    }
    ollama = @{
        Name = "Ollama"; Id = "Ollama.Ollama"; Admin = $false
        Url = "https://ollama.com/download/windows"
        Hint = "Download OllamaSetup.exe and run it."
    }
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$identity).IsInRole(
        [Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Test-Winget {
    <#
      Whether winget can install anything, which is a different question from
      whether the name resolves.

      AppData\Local\Microsoft\WindowsApps holds a zero byte "app execution
      alias" for winget that sits on the PATH whether or not App Installer is
      actually there; running it opens the Microsoft Store instead of
      installing. Windows 10 machines often have no winget at all. Either way
      Get-Command says yes - the same trap the Store's python stub sets, which
      is why Find-Python proves an interpreter runs instead of trusting a name.

      Both cases used to end with this script printing a `winget install ...`
      command that could not have worked either, which is the worst possible
      answer for the person this script exists for.
    #>
    if (-not (Have "winget")) { return $false }
    return (Probe { winget --version }) -match '\d'
}

function Get-WingetArgs($id) {
    # --silent keeps the vendor installer's own wizard out of the way. The two
    # agreement flags stop winget stopping to ask a question nobody is watching
    # for.
    @("install", "--id", $id, "-e", "--source", "winget", "--silent",
      "--accept-package-agreements", "--accept-source-agreements")
}

function Install-Here($key) {
    <#
      Install one package as the current user, in this window.

      winget writes to the console as it goes, because this can be a long
      download and a silent screen reads as a hang. Out-Host is what puts it in
      the transcript as well: a native program writes to the console directly,
      where Start-Transcript cannot see it, and only output routed through a
      pipeline is recorded.

      $ErrorActionPreference is relaxed around it for the reason described on
      Probe below: under "Stop" anything a native command puts on stderr
      becomes a terminating error, and winget is chatty on stderr even when it
      succeeds.
    #>
    Ok "Installing $($Prereqs[$key].Name)..."
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & winget @(Get-WingetArgs $Prereqs[$key].Id) | Out-Host }
    finally { $ErrorActionPreference = $previous }
    Update-Path
}

function Install-Elevated($keys) {
    <#
      Install the per-machine packages through a single permission prompt.

      Elevating one child process instead of the whole script is the point.
      Everything else here - the virtual environment, npm's cache, the model
      Ollama downloads, the two windows at the end - belongs to the person
      sitting in front of the machine, and running any of it as administrator
      writes their app into an account they never sign into.

      One prompt for both packages rather than one each, because a permission
      dialog that appears twice reads like something has gone wrong.

      Owning the prompt also means being able to say what happened to it.
      Left to ask for themselves, a silent MSI and a silent Python bundle
      decline quietly when they cannot elevate, and all this script could see
      afterwards was a tool that still was not installed. Cancelling
      Start-Process -Verb RunAs throws, so refusal arrives as an event rather
      than as an absence.
    #>
    $names = ($keys | ForEach-Object { $Prereqs[$_].Name }) -join " and "
    $commands = ($keys | ForEach-Object {
        "winget " + ((Get-WingetArgs $Prereqs[$_].Id) -join " ")
    }) -join "; "

    Ok "$names install for the whole computer, so Windows has to ask permission."
    Ok "Choose Yes on the prompt. A second window does the work and closes itself."
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $commands
        )
    } catch {
        Ok "That permission prompt was refused, or this account cannot give it."
    }
    Update-Path
}

function Show-ManualSetup($keys, $reason) {
    <#
      Hand the job back, in a form somebody who does not write code can finish.

      The download pages are opened rather than only printed, because typing an
      address is a step that can go wrong and clicking a window already sitting
      open is not. Every path out of this script that cannot install something
      ends here, and none of them end on a command line any more.
    #>
    Write-Host "`n$reason" -ForegroundColor Red
    Write-Host "  Install these yourself - it is a download and a Next-Next-Finish each:"
    Write-Host ""
    foreach ($key in $keys) {
        Write-Host ("  - {0}   {1}" -f $Prereqs[$key].Name, $Prereqs[$key].Url)
        Write-Host ("      {0}" -f $Prereqs[$key].Hint) -ForegroundColor DarkGray
        Start-Process $Prereqs[$key].Url -ErrorAction SilentlyContinue
    }
    Write-Host ""
    Write-Host "  Those pages are now open in your browser."
    Write-Host "  Once they have all finished installing, run run.cmd again."
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

function Get-PinnedModel {
    <#
      The model named in .env, or null. This is what the backend will load,
      whatever this script decides, so it is also what this script must use.
    #>
    $envFile = Join-Path $Root ".env"
    if (-not (Test-Path $envFile)) { return $null }
    $line = Select-String -Path $envFile -Pattern '^\s*OLLAMA_MODEL\s*=\s*(\S+)' |
            Select-Object -First 1
    if (-not $line) { return $null }
    return $line.Matches[0].Groups[1].Value
}

function Save-ModelChoice($model) {
    <#
      Tell the backend which model was chosen.

      This script pulls a model and backend/app/config.py has its own default,
      and until now they were two separate copies of the same string. Changing
      one here without writing it down would download the right model and then
      run the wrong one, which fails as a connection error naming a model the
      user never asked for.
    #>
    Add-Content -Path (Join-Path $Root ".env") -Value "OLLAMA_MODEL=$model"
    Ok "Wrote OLLAMA_MODEL=$model to .env"
}

function Test-PythonExe($exe) {
    # Runs, and is new enough. Both halves matter, and neither can be read off
    # a filename.
    return (Probe { & $exe -c "import sys; print(sys.version_info >= (3, 10))" }) -eq "True"
}

function Find-Python {
    <#
      An interpreter that actually runs and is new enough, or null.

      Bare `python` on Windows is frequently the Microsoft Store stub, which
      prints nothing and opens the Store instead of running, so this proves an
      interpreter works rather than trusting that the name resolves. The `py`
      launcher is tried first because it is the one that survives that.

      The search of known folders is the same idea one step further. Python is
      only added to the PATH when its installer is asked to, and somebody
      clicking through that wizard by hand has no reason to know which box does
      that. Without this, they install exactly what they were told to install
      and this script still says Python is missing - which is the point where a
      person stops believing anything it tells them. A full path works in every
      place $Python is used.

      Being a function rather than a block of script matters: it is asked
      twice, once before installing Python and once after, and the second call
      is the one that has to notice what the first call could not see.
    #>
    foreach ($candidate in @("py", "python", "python3")) {
        if (-not (Have $candidate)) { continue }
        if (Test-PythonExe $candidate) { return $candidate }
    }

    $known = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python3*\python.exe"),
        (Join-Path $env:ProgramFiles "Python3*\python.exe")
    )
    foreach ($pattern in $known) {
        # Newest first, so a machine carrying an old 3.8 alongside a fresh 3.12
        # does not get stopped by the one that fails the version test.
        $found = Get-ChildItem $pattern -ErrorAction SilentlyContinue |
                 Sort-Object Name -Descending
        foreach ($exe in $found) {
            if (Test-PythonExe $exe.FullName) { return $exe.FullName }
        }
    }
    return $null
}

# --- 1. Prerequisites -------------------------------------------------------
Say "Checking prerequisites"

if (Test-Admin) {
    # Not fatal, because somebody may have a reason. Said out loud, because
    # "run it as administrator" is the first thing anyone suggests when a setup
    # script fails, and here it is the one change that makes things worse:
    # Ollama and its models would install into the administrator's profile and
    # be missing from every ordinary run afterwards.
    Write-Host "    This is running as Administrator, which it does not need to be." -ForegroundColor Yellow
    Write-Host "    Ollama installs per user, so it would end up in the administrator's" -ForegroundColor Yellow
    Write-Host "    account instead of yours. Closing this and double-clicking run.cmd" -ForegroundColor Yellow
    Write-Host "    normally is the safer way round." -ForegroundColor Yellow
}

# Everything missing is found in one pass, then installed together.
#
# Checking and installing one tool at a time stopped at the first thing that
# would not install, without ever mentioning the other two - so a laptop with
# none of them learned about its three missing prerequisites across three runs,
# each one ending in a red message.
#
# Python is asked for by capability rather than by name: the Store stub means
# `python` can resolve on a machine with no interpreter on it.
$Python = Find-Python
$missing = @()
foreach ($key in $Prereqs.Keys) {
    $present = if ($key -eq "python") { [bool]$Python } else { Have $key }
    if (-not $present) { $missing += $key }
}

if ($missing.Count -gt 0) {
    Say ("Installing what is missing: " +
         (($missing | ForEach-Object { $Prereqs[$_].Name }) -join ", "))

    if (-not (Test-Winget)) {
        Show-ManualSetup $missing (
            "This computer has no working copy of winget, which is what this script " +
            "installs things with.")
    }

    # Per-user packages first and outside the elevation, for the reason on
    # $Prereqs: elevating Ollama puts it in the wrong account.
    foreach ($key in $missing) {
        if (-not $Prereqs[$key].Admin) { Install-Here $key }
    }
    $elevated = @($missing | Where-Object { $Prereqs[$_].Admin })
    if ($elevated.Count -gt 0) { Install-Elevated $elevated }

    # Whether that worked is answered by looking for the tools again, never by
    # winget's exit code: winget reports non-zero for perfectly good outcomes,
    # the package already being present among them.
    $Python = Find-Python
    $stillMissing = @($missing | Where-Object {
        if ($_ -eq "python") { -not $Python } else { -not (Have $_) }
    })
    if ($stillMissing.Count -gt 0) {
        Show-ManualSetup $stillMissing "Some of that did not install."
    }
}
Ok "Node.js, Ollama and Python ($Python) are all present"

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

<#
  Which model this laptop can actually hold.

  Chosen here rather than beside the other variables at the top of the file,
  because it calls a function. PowerShell reads a script in order and a call
  above its own definition is not an error until it runs, at which point it is
  "The term 'Get-PinnedModel' is not recognized" on the first line of output.
  Which is exactly what shipped, and what a parse check does not catch.

  The download size is not the number that matters. This app runs the model
  with a 16k context, which roughly doubles it. Measured with `ollama ps`, on
  CPU:

      llama3.2:3b   2.0 GB download   3.9 GB resident
      llama3.2:1b   1.3 GB download   1.9 GB resident

  And the model is not the only thing running. Before it there is already
  around 5 GB in use: Windows itself, this app's Python backend (which loads a
  torch embedding model), the web server, and a browser with the app open. On
  top of that the person is using their laptop for other things.

  So 3b wants about 9 GB before its owner opens anything of their own, which is
  why it took 8 GB machines down rather than merely running slowly.

  The cut is at 15 rather than 16 on purpose. Windows reserves some memory for
  hardware and reports the rest, so a 16 GB laptop says 15.7 and a `-ge 16`
  test would quietly send every one of them to the smaller model.

  A weaker model writes a worse resume. A laptop that runs out of memory writes
  no resume and frightens the person using it.
#>
$Models = @{
    "llama3.2:1b" = @{ Download = "1.3 GB"; Memory = 1.9 }
    "llama3.2:3b" = @{ Download = "2 GB"; Memory = 3.9 }
    "llama3.1:8b" = @{ Download = "4.7 GB"; Memory = 9.0 }
}
# What the OS, this app's backend, the web server and a browser are already
# holding before the model loads.
$OverheadGB = 5

$RamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)

# A model named in .env wins. That is either a deliberate choice or this
# script's own line from a previous run, and choosing again over the top of it
# would download a model the backend is not going to load. The old
# .env.example shipped OLLAMA_MODEL uncommented, so there are people carrying
# a pinned 3b on a laptop that cannot hold it; they get told rather than
# quietly overruled.
$Pinned = $false
$Model = Get-PinnedModel
if ($Model) {
    $Pinned = $true
} elseif ($RamGB -ge 15) {
    $Model = "llama3.2:3b"
} else {
    $Model = "llama3.2:1b"
}

$needs = $Models[$Model].Memory
if ($Pinned) {
    Ok "$Model is set in .env, so that is what runs ($RamGB GB on this machine)"
    if ($needs -and ($needs + $OverheadGB) -gt $RamGB) {
        Write-Host ("    Warning: $Model needs about {0} GB while running, and this app plus" -f $needs) -ForegroundColor Yellow
        Write-Host ("    Windows and a browser already use about $OverheadGB GB of your $RamGB GB.") -ForegroundColor Yellow
        Write-Host ("    Remove the OLLAMA_MODEL line from .env to let this script choose one that fits.") -ForegroundColor Yellow
    }
} else {
    Ok "$RamGB GB of memory on this machine, so: $Model"
    if ($RamGB -lt 8) {
        Ok "That is tight even for this model. Close what you can while the app runs."
    }
}

$models = Probe { ollama list }
if ($models -notmatch [regex]::Escape($Model)) {
    $size = $Models[$Model].Download
    Ok ("Downloading $Model" + $(if ($size) { " (about $size, one time)" } else { "" }) + "...")
    ollama pull $Model
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nModel download failed. Check your connection and re-run." -ForegroundColor Red
        exit 1
    }
}
if (-not $Pinned) { Save-ModelChoice $Model }
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
#
# But "something is installed" is not "what requirements.txt now asks for". A
# pull that adds a dependency leaves all three of these probes passing and the
# new package absent, so the stamp answers the question the probe cannot: is
# this venv built from the requirements.txt sitting here today?
$check = "import importlib.util as u; " +
         "print(all(u.find_spec(m) is not None for m in ('fastapi','sentence_transformers','alembic')))"
$installed = Probe { & $Venv -c $check }

$req = Join-Path $Backend "requirements.txt"
$stamp = Join-Path $Backend ".venv\.requirements"
$stale = -not (Test-Path $stamp) -or
         ((Get-FileHash $req).Hash -ne (Get-FileHash $stamp).Hash)

if (($installed -ne "True") -or $stale) {
    Ok "Installing Python packages. The first time this is the slow part: three to"
    Ok "ten minutes, most of it PyTorch. It has not frozen."
    & $Venv -m pip install --disable-pip-version-check -q --upgrade pip
    & $Venv -m pip install --disable-pip-version-check -r $req
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nInstalling Python packages failed." -ForegroundColor Red
        exit 1
    }
    Copy-Item $req $stamp -Force
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
# Every time, not only when node_modules is missing. That folder existing means
# *an* install happened once, not that it matches the package.json that just
# arrived with a pull - so the version that added a dependency reached everyone
# who already had the app as a missing-module stack trace on startup, which is
# the worst possible first impression of an upgrade. npm answers "up to date"
# in about a second when nothing has changed, and that second is worth it.
Ok "Checking npm packages..."
Push-Location $Web
try {
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nnpm install failed." -ForegroundColor Red
        exit 1
    }
} finally { Pop-Location }
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
