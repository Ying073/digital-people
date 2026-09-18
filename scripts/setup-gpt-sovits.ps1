param(
    [ValidateSet("CU126", "CU128", "CPU")]
    [string]$Device = "CU128",
    [ValidateSet("HF", "HF-Mirror", "ModelScope")]
    [string]$Source = "ModelScope"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LocalRoot = Join-Path $ProjectRoot ".local"
$Repository = Join-Path $LocalRoot "GPT-SoVITS"
$EnvironmentName = "GPTSoVits"
$Remote = "https://github.com/RVC-Boss/GPT-SoVITS.git"

$conda = Get-Command conda -ErrorAction Stop
$git = Get-Command git -ErrorAction Stop
New-Item -ItemType Directory -Path $LocalRoot -Force | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $Repository ".git") -PathType Container)) {
    Write-Host "Cloning the official GPT-SoVITS repository..."
    & $git.Source clone --depth 1 $Remote $Repository
    if ($LASTEXITCODE -ne 0) { throw "Failed to clone GPT-SoVITS." }
} else {
    Write-Host "Using existing GPT-SoVITS checkout: $Repository"
}

$environmentPayload = (& $conda.Source env list --json) | ConvertFrom-Json
$environmentExists = @($environmentPayload.envs) | Where-Object { (Split-Path -Leaf $_) -eq $EnvironmentName }
if (-not $environmentExists) {
    Write-Host "Creating Conda environment $EnvironmentName with Python 3.10..."
    & $conda.Source create -n $EnvironmentName python=3.10 -y
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the GPT-SoVITS Conda environment." }
}
& $conda.Source run -n $EnvironmentName python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "The GPT-SoVITS environment must use Python 3.10." }

Push-Location $Repository
try {
    Write-Host "Installing FFmpeg and CMake in the isolated environment..."
    & $conda.Source install -n $EnvironmentName -y -q -c conda-forge ffmpeg cmake
    if ($LASTEXITCODE -ne 0) { throw "Failed to install FFmpeg and CMake." }
    # Windows PowerShell 5.1 turns native stderr merged with 2>&1 into a terminating
    # NativeCommandError before the upstream installer can inspect the exit code.
    # Use a temporary compatibility copy that only removes that stream merge.
    $officialInstaller = Join-Path $Repository "install.ps1"
    $compatibleInstaller = Join-Path $Repository "install.codex-compatible.ps1"
    $officialRequirements = Join-Path $Repository "requirements.txt"
    $compatibleRequirements = Join-Path $Repository "requirements.codex-zh.txt"
    $requirementsText = [System.IO.File]::ReadAllText($officialRequirements)
    $requirementsText = [regex]::Replace($requirementsText, "(?m)^pyopenjtalk[^\r\n]*\r?\n?", "")
    $requirementsText = [regex]::Replace($requirementsText, "(?m)^jieba_fast[^\r\n]*\r?\n?", "")
    $requirementsText = [regex]::Replace($requirementsText, "(?m)^--no-binary=opencc\r?\n?", "")
    $requirementsText = [regex]::Replace($requirementsText, "(?m)^opencc\s*\r?\n?", "")
    $requirementsText += "`nopencc-python-reimplemented`n"
    [System.IO.File]::WriteAllText($compatibleRequirements, $requirementsText, [System.Text.UTF8Encoding]::new($false))

    $chineseModules = @(
        (Join-Path $Repository "GPT_SoVITS\text\chinese.py"),
        (Join-Path $Repository "GPT_SoVITS\text\chinese2.py")
    )
    foreach ($modulePath in $chineseModules) {
        $moduleText = [System.IO.File]::ReadAllText($modulePath)
        if ($moduleText -notmatch "import jieba as jieba_fast") {
            $moduleText = [regex]::Replace(
                $moduleText,
                '(?m)^import jieba_fast\r?$',
                "try:`n    import jieba_fast`nexcept ImportError:`n    import jieba as jieba_fast"
            )
            $moduleText = [regex]::Replace(
                $moduleText,
                '(?m)^import jieba_fast\.posseg as psg\r?$',
                "try:`n    import jieba_fast.posseg as psg`nexcept ImportError:`n    import jieba.posseg as psg"
            )
            [System.IO.File]::WriteAllText($modulePath, $moduleText, [System.Text.UTF8Encoding]::new($false))
        }
    }
    $toneSandhiPath = Join-Path $Repository "GPT_SoVITS\text\tone_sandhi.py"
    $toneSandhiText = [System.IO.File]::ReadAllText($toneSandhiPath)
    if ($toneSandhiText -notmatch "import jieba as jieba_fast") {
        $toneSandhiText = [regex]::Replace(
            $toneSandhiText,
            '(?m)^import jieba_fast as jieba\r?$',
            "try:`n    import jieba_fast as jieba`nexcept ImportError:`n    import jieba"
        )
        [System.IO.File]::WriteAllText($toneSandhiPath, $toneSandhiText, [System.Text.UTF8Encoding]::new($false))
    }
    $installerText = [System.IO.File]::ReadAllText($officialInstaller)
    $installerText = $installerText.Replace(" install -y -q -c conda-forge @Args 2>&1", " install -y -q -c conda-forge @Args")
    $installerText = $installerText.Replace(" pip install @Args 2>&1", " pip install @Args")
    $installerText = $installerText.Replace(
        'Invoke-Pip torch torchcodec --index-url "https://download.pytorch.org/whl/cu128"',
        'Invoke-Pip torch==2.7.1+cu128 torchaudio==2.7.1+cu128 --index-url "https://download.pytorch.org/whl/cu128"'
    )
    $installerText = $installerText.Replace("Invoke-Pip -r requirements.txt", "Invoke-Pip -r requirements.codex-zh.txt")
    $installerText = [regex]::Replace(
        $installerText,
        '(?s)Write-Info "Downloading Open JTalk Dict\.\.\.".*?Write-Success "Open JTalk Dic Downloaded"',
        'Write-Info "Skipping Open JTalk for the Chinese-only runtime"'
    )
    [System.IO.File]::WriteAllText($compatibleInstaller, $installerText, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Running the official GPT-SoVITS installer ($Device, $Source)..."
    & $conda.Source run --no-capture-output -n $EnvironmentName powershell.exe -NoProfile -ExecutionPolicy Bypass -File $compatibleInstaller -Device $Device -Source $Source
    if ($LASTEXITCODE -ne 0) { throw "The official GPT-SoVITS installer failed." }
    & $conda.Source run -n $EnvironmentName python -c "import torch; print('Python environment ready; CUDA:', torch.cuda.is_available(), 'Torch:', torch.__version__)"
    if ($LASTEXITCODE -ne 0) { throw "GPT-SoVITS environment verification failed." }
    & $git.Source rev-parse HEAD
} finally {
    Remove-Item -LiteralPath (Join-Path $Repository "install.codex-compatible.ps1") -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Repository "requirements.codex-zh.txt") -Force -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "GPT-SoVITS setup completed. Start it with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\start-gpt-sovits.ps1 -Background"
