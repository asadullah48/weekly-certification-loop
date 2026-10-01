# Weekly heartbeat for the certification loop. Invoked by Windows Task Scheduler
# (see register-task.ps1). Runs the DISCOVER stage with Claude Code headless; the agent
# then calls loop/certloop.py, which verifies, drafts, checks, logs and pushes.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$stamp = Get-Date -Format "yyyy-MM-dd"
New-Item -ItemType Directory -Force (Join-Path $root "logs") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $root "inbox") | Out-Null
$log = Join-Path $root "logs\heartbeat-$stamp.log"
$config = Get-Content -Raw (Join-Path $root "loop\config.json") | ConvertFrom-Json

"[$(Get-Date -Format o)] heartbeat start" | Out-File -FilePath $log -Encoding utf8
git pull --ff-only 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

$prompt = (Get-Content -Raw (Join-Path $root "loop\PROMPT.md")).Replace("{{DATE}}", $stamp)
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { $claude = Join-Path $env:USERPROFILE ".local\bin\claude.exe" }

& $claude -p $prompt `
    --max-budget-usd $config.budget.max_usd_per_run `
    --allowedTools "WebSearch" "WebFetch" "Read" "Write" "Glob" "Bash(python loop/certloop.py:*)" `
    2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"[$(Get-Date -Format o)] heartbeat end (exit $LASTEXITCODE)" | Out-File -FilePath $log -Append -Encoding utf8
exit $LASTEXITCODE
