$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    if (Test-Path ".vendor") { $env:PYTHONPATH = (Resolve-Path ".vendor").Path + [IO.Path]::PathSeparator + $env:PYTHONPATH }
    python -m streamlit run app.py --server.address 127.0.0.1
} finally { Pop-Location }

