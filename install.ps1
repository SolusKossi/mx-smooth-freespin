# Installs mx_scroll_mode.py for the current user and starts it at every logon.
# No admin rights, no service, no scheduled task: a copy in %LOCALAPPDATA% and a
# shortcut in the user's Startup folder that runs it with pythonw.exe.
#   pwsh -File install.ps1             install (or update) and start
#   pwsh -File install.ps1 -Uninstall  stop, remove shortcut and files
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$dir      = Join-Path $env:LOCALAPPDATA 'MXSmoothScroll'
$script   = Join-Path $dir 'mx_scroll_mode.py'
$shortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'MX Smooth Scroll.lnk'

function Stop-Running {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like '*mx_scroll_mode.py*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force; "stopped PID $($_.ProcessId)" }
}

Stop-Running
if ($Uninstall) {
    Remove-Item $shortcut, $dir -Recurse -Force -ErrorAction SilentlyContinue
    'uninstalled'
    return
}

$pythonw = (Get-Command pythonw.exe).Source
New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'mx_scroll_mode.py') $script -Force

$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($shortcut)
$lnk.TargetPath       = $pythonw
$lnk.Arguments        = "`"$script`" run"
$lnk.WorkingDirectory = $dir
$lnk.Description      = 'MX Master: smooth scrolling in free-spin, line by line in ratchet'
$lnk.Save()

Start-Process $pythonw -ArgumentList "`"$script`"", 'run' -WorkingDirectory $dir
"installed to $dir, startup shortcut $shortcut, started with $pythonw"
