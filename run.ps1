param(
    [int]$Port = 8000,
    [string]$HostAddress = "0.0.0.0",
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating local Python environment..."
    python -m venv (Join-Path $ProjectRoot ".venv")
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
}

if (-not $env:ADMIN_PASSWORD) {
    $env:ADMIN_PASSWORD = "teacher123"
    Write-Warning "ADMIN_PASSWORD is not set. Temporary classroom password: teacher123"
}

Set-Location $ProjectRoot
$existing = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "课堂服务已经在运行: http://127.0.0.1:$Port"
    Write-Host "局域网访问请使用本机 IPv4 地址和端口 $Port。"
    exit 0
}

if ($Background) {
    $logDir = Join-Path $ProjectRoot "data\logs"
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $stdout = Join-Path $logDir "web.stdout.log"
    $stderr = Join-Path $logDir "web.stderr.log"
    Start-Process -FilePath $VenvPython -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", "$Port") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr | Out-Null
    Start-Sleep -Milliseconds 800
    $started = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if (-not $started) {
        Write-Error "课堂服务启动失败，请查看 data/logs/web.stderr.log"
        exit 1
    }
    Write-Host "课堂服务已在后台启动: http://127.0.0.1:$Port"
    Write-Host "局域网访问请使用本机 IPv4 地址和端口 $Port。"
    exit 0
}

& $VenvPython -m uvicorn app.main:app --host $HostAddress --port $Port
