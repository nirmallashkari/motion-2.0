param([switch]$WithSpeech, [switch]$NoPause)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskVenv = Join-Path $PSScriptRoot 'engines\python\.venv'
$taskPython = Join-Path $taskVenv 'Scripts\python.exe'
$taskExit = 1
try {
    Set-Location -LiteralPath $taskRoot
    foreach ($taskFolder in @('INPUT','OUTPUT','_SYSTEM\work','_SYSTEM\reports','_SYSTEM\secrets')) {
        New-Item -ItemType Directory -Path (Join-Path $taskRoot $taskFolder) -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $taskPython)) {
        if (-not (Get-Command py.exe -ErrorAction SilentlyContinue)) { throw 'Install Python 3.13 for Windows with the Python launcher.' }
        & py -3.13 -m venv $taskVenv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 environment creation failed.' }
    }
    $taskRequirements = if ($WithSpeech) { 'requirements-speech.txt' } else { 'requirements.txt' }
    & $taskPython -m pip install -r (Join-Path $taskRoot $taskRequirements)
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    if ($WithSpeech) {
        & $taskPython (Join-Path $taskRoot 'tools\download_speech_model.py')
        if ($LASTEXITCODE -ne 0) { throw 'Speech model installation failed.' }
    }
    # Never truncate a key or overwrite the account-bound encrypted backup.
    $taskKey = Join-Path $PSScriptRoot 'secrets\deepseek_api_key.txt'
    if (-not (Test-Path -LiteralPath $taskKey)) { [IO.File]::WriteAllText($taskKey, '') }
    foreach ($taskTool in @('ffmpeg','ffprobe')) {
        if (-not (Get-Command $taskTool -ErrorAction SilentlyContinue)) { throw "$taskTool is missing from PATH. Install FFmpeg and reopen the terminal." }
    }
    & $taskPython (Join-Path $taskRoot 'tools\check_environment.py')
    if ($LASTEXITCODE -ne 0) { throw 'Blender check failed. Install Blender 5.1.1 or set MOTION_BLENDER.' }
    Write-Host 'Setup complete. Save your API key locally, add script + voice to INPUT, and run RUN_VIDEO.bat.'
    $taskExit = 0
} catch { Write-Host ('SETUP ERROR: ' + $_.Exception.Message) -ForegroundColor Red }
if (-not $NoPause) { [void](Read-Host 'Press Enter to close') }
exit $taskExit
