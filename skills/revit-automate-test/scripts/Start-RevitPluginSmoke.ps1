param(
    [string] $RevitYear = "2027",

    [Parameter(Mandatory = $true)]
    [string] $PluginName,

    [string] $RevitExe = "",

    [string] $PluginLogPath = "",

    [string] $JournalDir = "",

    [int] $TimeoutSeconds = 150,

    [string] $Language = "CHS",

    [switch] $ClickTrustDialog,

    [switch] $KeepOpen,

    [switch] $CollectOnly
)

$ErrorActionPreference = "Stop"

function Get-DefaultRevitExe {
    param([string] $Year)

    return Join-Path $env:ProgramFiles "Autodesk\Revit $Year\Revit.exe"
}

function Try-ClickTrustDialog {
    param([int] $ProcessId)

    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes

    $windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll(
        [System.Windows.Automation.TreeScope]::Children,
        [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
            $ProcessId))

    foreach ($window in $windows) {
        $buttons = $window.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::Button))

        for ($i = 0; $i -lt $buttons.Count; $i++) {
            $button = $buttons.Item($i)
            $name = $button.Current.Name
            if ($name -match "Load once|Load this time|加载一次|載入一次|载入一次|始终加载|始終載入|Always Load|Always") {
                $invoke = $null
                if ($button.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref] $invoke)) {
                    Write-Host "TRUST_DIALOG_CLICK=$name"
                    $invoke.Invoke()
                    return $true
                }
            }
        }
    }

    return $false
}

function Find-LatestJournal {
    param(
        [string] $Year,
        [string] $OverrideDir
    )

    $journalDir = if ([string]::IsNullOrWhiteSpace($OverrideDir)) {
        Join-Path $env:LOCALAPPDATA "Autodesk\Revit\Autodesk Revit $Year\Journals"
    }
    else {
        $OverrideDir
    }

    if (-not (Test-Path -LiteralPath $journalDir)) {
        return $null
    }

    return Get-ChildItem -LiteralPath $journalDir -Filter "journal.*.txt" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

$evidenceScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "Get-RevitPluginEvidence.ps1"

if ($CollectOnly) {
    $evidenceArgs = @{
        RevitYear = $RevitYear
        PluginName = $PluginName
        RequireSuccess = $true
    }

    if (-not [string]::IsNullOrWhiteSpace($JournalDir)) {
        $evidenceArgs.JournalDir = $JournalDir
    }

    if (-not [string]::IsNullOrWhiteSpace($PluginLogPath)) {
        $evidenceArgs.PluginLogPath = $PluginLogPath
    }

    & $evidenceScript @evidenceArgs
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($RevitExe)) {
    $RevitExe = Get-DefaultRevitExe -Year $RevitYear
}

if (-not (Test-Path -LiteralPath $RevitExe)) {
    throw "Revit executable not found: $RevitExe"
}

$existing = Get-Process Revit -ErrorAction SilentlyContinue
if ($existing) {
    $ids = ($existing | Select-Object -ExpandProperty Id) -join ", "
    throw "Existing Revit process found ($ids). Refusing to launch a second smoke instance."
}

$start = Get-Date
$process = Start-Process -FilePath $RevitExe -ArgumentList @("/language", $Language) -PassThru
Write-Host "REVIT_PID=$($process.Id)"
Write-Host "REVIT_START_TIME=$($start.ToString('s'))"

$success = $false
$errorFound = $false
$journalEvidence = @()
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

try {
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5

        if ($ClickTrustDialog) {
            [void] (Try-ClickTrustDialog -ProcessId $process.Id)
        }

        $latest = Find-LatestJournal -Year $RevitYear -OverrideDir $JournalDir
        if ($latest) {
            $pattern = "The requested assembly '$([regex]::Escape($PluginName)),|API_SUCCESS \{ Starting External Application: $([regex]::Escape($PluginName))|API_ERROR \{ Starting External Application: $([regex]::Escape($PluginName))|BadImageFormat|Illegal tables|Enclosing type|TaskDialog_External_Tools_External_Tool_Failure"
            $matches = Select-String -Path $latest.FullName -Pattern $pattern -ErrorAction SilentlyContinue
            if ($matches) {
                $journalEvidence = $matches | Select-Object -Last 20
                if ($matches | Select-String -Pattern "API_ERROR|BadImageFormat|Illegal tables|Enclosing type|TaskDialog_External_Tools_External_Tool_Failure") {
                    $errorFound = $true
                    break
                }

                if ($matches | Select-String -Pattern "API_SUCCESS \{ Starting External Application: $([regex]::Escape($PluginName))") {
                    $success = $true
                    break
                }
            }
        }

        if (-not [string]::IsNullOrWhiteSpace($PluginLogPath) -and (Test-Path -LiteralPath $PluginLogPath)) {
            $log = Get-Item -LiteralPath $PluginLogPath
            if ($log.LastWriteTime -ge $start.AddSeconds(-5)) {
                $recent = Get-Content -LiteralPath $PluginLogPath -Tail 80
                if ($recent -match "插件启动|plugin started|Application started") {
                    $success = $true
                    break
                }
            }
        }
    }
}
finally {
    Write-Host "REVIT_LOAD_SUCCESS=$success"
    Write-Host "REVIT_LOAD_ERROR=$errorFound"

    if ($journalEvidence) {
        Write-Host "JOURNAL_EVIDENCE_BEGIN"
        $journalEvidence | ForEach-Object {
            Write-Host ("{0}:{1}: {2}" -f (Split-Path $_.Path -Leaf), $_.LineNumber, $_.Line.Trim())
        }
        Write-Host "JOURNAL_EVIDENCE_END"
    }

    if (-not $KeepOpen -and -not $process.HasExited) {
        $closed = $process.CloseMainWindow()
        Write-Host "REVIT_CLOSE_MAIN_WINDOW=$closed"
        Start-Sleep -Seconds 10
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            Write-Host "REVIT_STOPPED_FORCE=true"
        }
    }
}

if ($errorFound) { exit 2 }
if ($success) { exit 0 }
exit 1
