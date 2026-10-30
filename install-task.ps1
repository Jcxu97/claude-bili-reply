# Register the scheduled task bili-reply: one round every hour, hidden, runs without a logged-in user (S4U).
# Also register bili-reply-web, the status page, started at boot.
# -WebHost 127.0.0.1 keeps the page on this PC. Give a LAN or Tailscale address to open it from other devices;
# then a firewall rule allows the port from -AllowFrom only (default 100.64.0.0/10 is the Tailscale range).
param([string]$WebHost = '127.0.0.1', [int]$Port = 8789, [int]$Minutes = 60, [string]$AllowFrom = '100.64.0.0/10')
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = (Get-Command python).Source
$vbs = Join-Path $root 'run-hidden.vbs'
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
$act = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"{0}" "{1}" "{2}" round' -f $vbs, $py, (Join-Path $root 'run.py')) -WorkingDirectory $root
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes $Minutes)
$p = New-ScheduledTaskPrincipal -UserId $me -LogonType S4U
Unregister-ScheduledTask -TaskName 'bili-reply' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName 'bili-reply' -Settings $s -Action $act -Principal $p -Trigger $t | Out-Null
Get-ScheduledTask -TaskName 'bili-reply' | Select-Object TaskName, State

$w = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"{0}" "{1}" "{2}" {3} {4}' -f $vbs, $py, (Join-Path $root 'web.py'), $WebHost, $Port) -WorkingDirectory $root
$ws = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1)
Unregister-ScheduledTask -TaskName 'bili-reply-web' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName 'bili-reply-web' -Settings $ws -Action $w -Principal $p -Trigger (New-ScheduledTaskTrigger -AtStartup) | Out-Null
Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like "*$root*web.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-ScheduledTask -TaskName 'bili-reply-web'
if ($WebHost -ne '127.0.0.1' -and -not (Get-NetFirewallRule -DisplayName 'bili-reply-web' -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName 'bili-reply-web' -Direction Inbound -Protocol TCP -LocalPort $Port -RemoteAddress $AllowFrom -Action Allow | Out-Null
}
"Status page: http://${WebHost}:$Port"
