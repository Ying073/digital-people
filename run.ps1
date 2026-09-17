param(
    [int]$Port = 8000,
    [string]$HostAddress = "0.0.0.0",
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvRoot = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

function Test-VenvPython {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        return $false
    }
    & $VenvPython -c "import sys; raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

function Install-ProjectDependencies {
    & $VenvPython -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install project dependencies. Check the network connection and try again."
    }
}

function Test-ClassroomServer {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/status" -UseBasicParsing -TimeoutSec 1
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-VenvPython)) {
    if (Test-Path -LiteralPath $VenvRoot) {
        $resolvedRoot = (Resolve-Path -LiteralPath $VenvRoot).Path
        $expectedRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot ".venv"))
        if ($resolvedRoot -ne $expectedRoot) {
            throw "Refusing to remove unexpected virtual environment path: $resolvedRoot"
        }
        Write-Warning "The existing virtual environment is invalid and will be rebuilt."
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
    }
    $bootstrapPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $bootstrapPython) {
        throw "Python was not found. Install Python 3.11 or newer and run this script again."
    }
    Write-Host "Creating local Python environment..."
    & $bootstrapPython.Source -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0 -or -not (Test-VenvPython)) {
        throw "Failed to create the local Python environment."
    }
    Install-ProjectDependencies
}

& $VenvPython -c "import fastapi, uvicorn, multipart, docx, pypdf" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing missing project dependencies..."
    Install-ProjectDependencies
}

if (-not $env:ADMIN_PASSWORD) {
    $env:ADMIN_PASSWORD = "teacher123"
    Write-Warning "ADMIN_PASSWORD is not set. Temporary classroom password: teacher123"
}

Set-Location $ProjectRoot
if (Test-ClassroomServer) {
    Write-Host "课堂服务已经在运行: http://127.0.0.1:$Port"
    Write-Host "局域网访问请使用本机 IPv4 地址和端口 $Port。"
    exit 0
}

if ($Background) {
    $logDir = Join-Path $ProjectRoot "data\logs"
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $stdout = Join-Path $logDir "web.stdout.log"
    $stderr = Join-Path $logDir "web.stderr.log"
    $server = Start-Process -FilePath $VenvPython -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", "$Port") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $started = $null
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($server.HasExited) {
            break
        }
        if (Test-ClassroomServer) {
            $started = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $started) {
        Write-Error "课堂服务启动失败，请查看 data/logs/web.stderr.log"
        exit 1
    }
    Write-Host "课堂服务已在后台启动: http://127.0.0.1:$Port"
    Write-Host "局域网访问请使用本机 IPv4 地址和端口 $Port。"
    exit 0
}

& $VenvPython -m uvicorn app.main:app --host $HostAddress --port $Port
