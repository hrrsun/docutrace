$ErrorActionPreference='Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    try {
        $health=Invoke-RestMethod 'http://127.0.0.1:18783/health' -TimeoutSec 2
        if ($health.status -eq 'ok') { exit 0 }
    } catch {}
    Start-Process -FilePath (Get-Command python.exe).Source -ArgumentList '-m','studio.runner' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -RedirectStandardError '.runtime/runner-error.log' -RedirectStandardOutput '.runtime/runner-output.log'
    $deadline=(Get-Date).AddSeconds(15)
    do {
        try {
            $health=Invoke-RestMethod 'http://127.0.0.1:18783/health' -TimeoutSec 2
            if ($health.status -eq 'ok') { exit 0 }
        } catch {}
        Start-Sleep -Seconds 1
    } until ((Get-Date) -gt $deadline)
    throw 'Local sandbox executor failed to start'
} finally { Pop-Location }
