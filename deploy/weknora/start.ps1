param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $ErrorActionPreference = 'Continue'
    docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
    $engineExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($engineExit) {
        Write-Output 'Starting Docker Desktop...'
        docker desktop start --timeout 120
        if ($LASTEXITCODE) { throw 'Docker Desktop did not start; check Desktop diagnostics' }
        $deadline = (Get-Date).AddSeconds(120)
        do {
            $ErrorActionPreference = 'Continue'
            docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
            $ready = $LASTEXITCODE -eq 0
            $ErrorActionPreference = 'Stop'
            if (-not $ready) { Start-Sleep -Seconds 2 }
        } until ($ready -or (Get-Date) -gt $deadline)
        if (-not $ready) { throw 'Docker engine is not ready' }
    }
    try {
        Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3 | Out-Null
    } catch {
        Write-Output 'Starting local Ollama...'
        Start-Process -FilePath (Get-Command ollama.exe).Source -ArgumentList 'serve' -WindowStyle Hidden
        $deadline = (Get-Date).AddSeconds(30)
        $ready = $false
        do {
            try {
                Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null
                $ready = $true
            } catch { Start-Sleep -Seconds 1 }
        } until ($ready -or (Get-Date) -gt $deadline)
        if (-not $ready) { throw 'Ollama is not reachable on port 11434' }
    }
    python init.py
    if ($LASTEXITCODE) { throw 'Unable to initialize local configuration' }
    python ../../tools/configure_model.py
    if ($LASTEXITCODE) { throw 'Local interactive model setup failed' }
    & (Join-Path $PSScriptRoot '..\..\tools\start_runner.ps1')
    if ($LASTEXITCODE) { throw 'Sandbox executor failed to start' }
    python ../../tools/configure_runner.py
    if ($LASTEXITCODE) { throw 'Sandbox executor configuration failed' }
    $ErrorActionPreference = 'Continue'
    docker image inspect docagent/studio:1 docagent/evidence-tools:1 2>$null | Out-Null
    $imageExit=$LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($imageExit -or $Rebuild) {
        docker compose -p docagent build studio evidence-tools
        if ($LASTEXITCODE) { throw 'Studio image build failed' }
    }
    docker compose -p docagent up -d --no-build --wait --wait-timeout 300
    if ($LASTEXITCODE) { throw 'WeKnora startup failed; inspect docker compose -p docagent ps -a' }
    # Refresh Nginx upstream resolution after backend recreation.
    docker compose -p docagent restart frontend
    if ($LASTEXITCODE) { throw 'Frontend restart failed' }
    python healthcheck.py
    if ($LASTEXITCODE) { throw 'Readiness verification failed; see healthcheck output' }
    Write-Output 'Knowledge Studio: http://127.0.0.1:18780/studio/'
    Write-Output 'WeKnora platform: http://127.0.0.1:18780/platform/knowledge-bases'
} finally { Pop-Location }
