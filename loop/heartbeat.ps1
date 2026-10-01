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
# A stale ANTHROPIC_API_KEY in the environment overrides the claude.ai login in headless mode
# (401 "API key is invalid"). Drop it for this process only so the subscription login is used.
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { $claude = Join-Path $env:USERPROFILE ".local\bin\claude.exe" }

# Lean session: no skills, no MCP servers (the global setup adds ~50k context tokens per run),
# and a mid-tier model, which is plenty for search-and-summarise. The budget cap is the hard stop.
& $claude -p $prompt `
    --model $config.budget.model `
    --max-budget-usd $config.budget.max_usd_per_run `
    --disable-slash-commands --strict-mcp-config --mcp-config '{\"mcpServers\":{}}' `
    --allowedTools "WebSearch" "WebFetch" "Read" "Write" "Glob" "Bash(python loop/certloop.py:*)" `
    2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"[$(Get-Date -Format o)] heartbeat end (exit $LASTEXITCODE)" | Out-File -FilePath $log -Append -Encoding utf8
exit $LASTEXITCODE
