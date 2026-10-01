# One-time setup: register the weekly heartbeat with Windows Task Scheduler.
# Usage:  powershell -ExecutionPolicy Bypass -File loop\register-task.ps1 [-Day Monday] [-Time 09:00]
# Remove: Unregister-ScheduledTask -TaskName "WeeklyCertificationLoop" -Confirm:$false
param(
    [string]$Day = "Monday",
    [string]$Time = "09:00"
)

$script = Join-Path $PSScriptRoot "heartbeat.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $Day -At $Time
# StartWhenAvailable: if the PC was off at the scheduled time, run at next startup instead of skipping the week.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) -RunOnlyIfNetworkAvailable

Register-ScheduledTask -TaskName "WeeklyCertificationLoop" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Weekly Certification Loop: discover free certifications, publish to GitHub" -Force | Out-Null
Get-ScheduledTask -TaskName "WeeklyCertificationLoop" | Select-Object TaskName, State, @{n="NextRun";e={(Get-ScheduledTaskInfo $_).NextRunTime}}
