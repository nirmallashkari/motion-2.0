param([ValidateSet('run','reset','check')][string]$Action = 'run',
      [switch]$NoPause, [switch]$DryRun, [string]$Confirmation = '', [string]$Workspace = '')
$ErrorActionPreference = 'Stop'
$taskWorkspace = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot 'engines\python\.venv\Scripts\python.exe'
$taskResult = 1
function Test-MotionLocalOllama {
    try {
        # Do not send loopback health checks through configured system proxies.
        $taskRequest=[Net.WebRequest]::Create('http://127.0.0.1:11434/api/tags')
        $taskRequest.Proxy=$null
        $taskRequest.Timeout=2000
        $taskResponse=$taskRequest.GetResponse()
        $taskResponse.Close()
        return $true
    } catch { return $false }
}
try {
    Set-Location -LiteralPath $taskWorkspace
    if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Motion Python environment is missing. Run SETUP_MOTION.bat first.' }
    $env:PYTHONUTF8 = '1'
    $taskArguments = @((Join-Path $PSScriptRoot 'motion.py'), $Action)
    if ($Workspace) { $taskArguments += @('--workspace', (Resolve-Path -LiteralPath $Workspace).Path) }
    $taskConfigRoot=if($Workspace) { (Resolve-Path -LiteralPath $Workspace).Path } else { $taskWorkspace }
    $taskConfigPath=Join-Path $taskConfigRoot '_SYSTEM\local_ai.json'
    if($Action -eq 'run' -and (Test-Path -LiteralPath $taskConfigPath)) {
        $taskConfig=Get-Content -LiteralPath $taskConfigPath -Raw | ConvertFrom-Json
        $taskCloudEnabled=$false
        $taskCloudConfigPath=Join-Path $taskConfigRoot '_SYSTEM\cloud_planner.json'
        if(Test-Path -LiteralPath $taskCloudConfigPath) { $taskCloudEnabled=(Get-Content -LiteralPath $taskCloudConfigPath -Raw | ConvertFrom-Json).enabled }
        if($taskConfig.authoring_mode -eq 'hybrid' -and $taskConfig.enabled -and -not $taskCloudEnabled) {
            $taskServiceReady=$false
            $taskServiceReady=Test-MotionLocalOllama
            if(-not $taskServiceReady) {
                $taskOllama=Get-Command 'ollama.exe' -ErrorAction SilentlyContinue
                if($taskOllama) {
                    $env:OLLAMA_HOST='127.0.0.1:11434'
                    $env:OLLAMA_NO_CLOUD='1'
                    $taskServiceLogs=Join-Path $PSScriptRoot 'reports'
                    try {
                        $null=Start-Process -FilePath $taskOllama.Source -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskServiceLogs 'ollama-service.stdout.log') -RedirectStandardError (Join-Path $taskServiceLogs 'ollama-service.stderr.log')
                        for($taskAttempt=0;$taskAttempt -lt 12;$taskAttempt++) {
                            Start-Sleep -Milliseconds 500
                            if(Test-MotionLocalOllama) { $taskServiceReady=$true; break }
                        }
                    } catch { Write-Host 'Local Ollama startup failed; the planner will report and use registered fallback.' }
                }
                if(-not $taskServiceReady) { Write-Host 'Local Ollama is unavailable; registered scene fallback remains available.' }
            }
        }
    }
    if ($DryRun) { $taskArguments += '--dry-run' }
    if ($Confirmation) { $taskArguments += @('--confirmation', $Confirmation) }
    & $taskPython @taskArguments
    $taskResult = $LASTEXITCODE
    # Retain the installed asset notices in hybrid deliveries too.
    $taskStatePath=Join-Path $taskConfigRoot 'OUTPUT\SYSTEM_STATUS.json'
    if($taskResult -eq 0 -and $Action -eq 'run' -and (Test-Path -LiteralPath $taskStatePath)) {
        $taskState=Get-Content -LiteralPath $taskStatePath -Raw | ConvertFrom-Json
        if($taskState.status -eq 'ready' -and $taskState.mode -eq 'hybrid') {
            $taskDelivery=[IO.Path]::GetFullPath($taskState.delivery)
            $taskDeliveryBoundary=[IO.Path]::GetFullPath((Join-Path $taskConfigRoot 'OUTPUT\deliveries'))+[IO.Path]::DirectorySeparatorChar
            if(-not $taskDelivery.StartsWith($taskDeliveryBoundary,[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid delivery boundary for asset notices.' }
            $taskLicenseTarget=Join-Path $taskDelivery 'licenses'
            New-Item -ItemType Directory -Path $taskLicenseTarget -Force | Out-Null
            foreach($taskNotice in @('microsoft_LICENSE','tabler_LICENSE')) {
                Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('assets\github\'+$taskNotice)) -Destination (Join-Path $taskLicenseTarget $taskNotice) -Force
            }
            # A 3D action can resolve a cue absent from the older 2D vocabulary.
            # Report actual abstract Python shots, keeping base coverage separately.
            $taskQa=Get-Content -LiteralPath (Join-Path $taskConfigRoot 'OUTPUT\qa_report.json') -Raw | ConvertFrom-Json
            $taskAbstract=@($taskQa.scenes | Where-Object { $_.engine -eq 'python' -and $_.id -like 'abstract_story__*' } | ForEach-Object {
                if($_.id -match '^abstract_story__(\d+)_') { [int]$Matches[1] }
            } | Select-Object -Unique)
            $taskProvenancePath=Join-Path $taskDelivery 'system_provenance.json'
            $taskProvenance=Get-Content -LiteralPath $taskProvenancePath -Raw | ConvertFrom-Json
            if(-not $taskProvenance.PSObject.Properties['unrecognized_2d_cues']) {
                $taskProvenance | Add-Member -NotePropertyName 'unrecognized_2d_cues' -NotePropertyValue $taskProvenance.abstract_cues
            }
            $taskProvenance.abstract_cues=$taskAbstract
            $taskProvenance | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $taskProvenancePath -Encoding UTF8
            $taskAbstractLabel=if($taskAbstract.Count) { '['+($taskAbstract -join ', ')+']' } else { 'none' }
            foreach($taskSummaryRoot in @((Join-Path $taskConfigRoot 'OUTPUT'),$taskDelivery)) {
                $taskSummaryPath=Join-Path $taskSummaryRoot 'RUN_SUMMARY.txt'
                $taskSummary=Get-Content -LiteralPath $taskSummaryPath -Raw
                $taskSummary=[regex]::Replace($taskSummary,'(?m)^Abstract source cues: .*$',('Abstract source cues: '+$taskAbstractLabel+'. Unknown meaning is not verified.'))
                Set-Content -LiteralPath $taskSummaryPath -Value $taskSummary -Encoding UTF8
            }
        }
    }
} catch { $taskResult=1; Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red }
if (-not $NoPause) { [void](Read-Host 'Press Enter to close') }
exit $taskResult
