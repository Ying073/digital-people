param(
    [switch]$Background,
    [int]$Port = 9880
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Repository = Join-Path $ProjectRoot ".local\GPT-SoVITS"
$EnvironmentName = "GPTSoVits"
$HostAddress = "127.0.0.1"
$HealthUrl = "http://${HostAddress}:$Port/docs"
$conda = Get-Command conda -ErrorAction Stop

function Test-GptSovitsService {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $Repository "api_v2.py") -PathType Leaf)) {
    throw "GPT-SoVITS is not installed. Run scripts\setup-gpt-sovits.ps1 first."
}
if (Test-GptSovitsService) {
    Write-Host "GPT-SoVITS is already running at http://${HostAddress}:$Port"
    exit 0
}

$arguments = @(
    "run", "--no-capture-output", "-n", $EnvironmentName,
    "python", "api_v2.py", "-a", $HostAddress, "-p", "$Port",
    "-c", "GPT_SoVITS/configs/tts_infer.yaml"
)

Push-Location $Repository
try {
    if (-not $Background) {
        & $conda.Source @arguments
        exit $LASTEXITCODE
    }
    $logDirectory = Join-Path $ProjectRoot "data\logs"
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $stdout = Join-Path $logDirectory "gpt-sovits.stdout.log"
    $stderr = Join-Path $logDirectory "gpt-sovits.stderr.log"
    $process = Start-Process -FilePath $conda.Source -ArgumentList $arguments -WorkingDirectory $Repository -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
} finally {
    Pop-Location
}

for ($attempt = 0; $attempt -lt 240; $attempt++) {
    if ($process.HasExited) { break }
    if (Test-GptSovitsService) {
        Write-Host "GPT-SoVITS is running at http://${HostAddress}:$Port"
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw "GPT-SoVITS did not become ready. Check data\logs\gpt-sovits.stderr.log."
