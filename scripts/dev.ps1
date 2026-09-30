# Start backend (FastAPI :8000) and frontend (Vite :5173) without hanging the shell.
# Do NOT use Start-Process -RedirectStandardOutput/-NoNewWindow for long-running servers.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Start-Server {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList,
        [Parameter(Mandatory)][string]$WorkingDirectory
    )
    Start-Process -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden
}

function Wait-Http {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [int]$TimeoutSec = 20
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-RestMethod -Uri $Uri -TimeoutSec 2 | Out-Null
            return $true
        }
        catch {
            Start-Sleep -Milliseconds 400
        }
    }
    return $false
}

# Backend: uv is a real exe; npm is not — wrap npm in cmd.exe
Start-Server -FilePath 'uv' `
    -ArgumentList @('run', 'uvicorn', 'backend.main:app', '--port', '8000') `
    -WorkingDirectory (Join-Path $root 'backend')

Start-Server -FilePath 'cmd.exe' `
    -ArgumentList @('/c', 'npm', 'run', 'dev') `
    -WorkingDirectory (Join-Path $root 'frontend')

if (-not (Wait-Http -Uri 'http://localhost:8000/api/health' -TimeoutSec 20)) {
    Write-Error 'Backend did not become ready on :8000'
    exit 1
}
if (-not (Wait-Http -Uri 'http://localhost:5173/api/health' -TimeoutSec 20)) {
    Write-Error 'Frontend proxy did not become ready on :5173'
    exit 1
}

Write-Host 'Backend:  http://localhost:8000  (docs: /docs)'
Write-Host 'Frontend: http://localhost:5173  (/api/* proxied to :8000)'
Invoke-RestMethod -Uri 'http://localhost:5173/api/health' | ConvertTo-Json -Compress
Invoke-RestMethod -Uri 'http://localhost:5173/api/hello?name=React' | ConvertTo-Json -Compress
