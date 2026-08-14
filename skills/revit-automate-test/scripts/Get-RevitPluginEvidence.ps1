param(
    [string] $RevitYear = "2027",

    [Parameter(Mandatory = $true)]
    [string] $PluginName,

    [string] $JournalDir = "",

    [string] $PluginLogPath = "",

    [string] $SuccessPattern = "",

    [string] $ErrorPattern = "",

    [switch] $RequireSuccess,

    [int] $Tail = 80
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($JournalDir)) {
    $JournalDir = Join-Path $env:LOCALAPPDATA "Autodesk\Revit\Autodesk Revit $RevitYear\Journals"
}

if ([string]::IsNullOrWhiteSpace($SuccessPattern)) {
    $escaped = [regex]::Escape($PluginName)
    $SuccessPattern = "API_SUCCESS \{ Starting External Application: $escaped|The requested assembly '$escaped,"
}

if ([string]::IsNullOrWhiteSpace($ErrorPattern)) {
    $escaped = [regex]::Escape($PluginName)
    $ErrorPattern = "API_ERROR \{ Starting External Application: $escaped|BadImageFormat|Illegal tables|Enclosing type|TaskDialog_External_Tools_External_Tool_Failure|Failed to resolve assembly '$escaped"
}

if (-not (Test-Path -LiteralPath $JournalDir)) {
    throw "Journal directory not found: $JournalDir"
}

$latest = Get-ChildItem -LiteralPath $JournalDir -Filter "journal.*.txt" -ErrorAction Stop |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($null -eq $latest) {
    throw "No Revit journal files found in: $JournalDir"
}

Write-Host "JOURNAL=$($latest.FullName)"
Write-Host "JOURNAL_LAST_WRITE=$($latest.LastWriteTime.ToString('s'))"
Write-Host "JOURNAL_SIZE=$($latest.Length)"

$successMatches = Select-String -Path $latest.FullName -Pattern $SuccessPattern -ErrorAction SilentlyContinue
$errorMatches = Select-String -Path $latest.FullName -Pattern $ErrorPattern -ErrorAction SilentlyContinue
$pluginMatches = Select-String -Path $latest.FullName -Pattern ([regex]::Escape($PluginName)) -ErrorAction SilentlyContinue

if ($pluginMatches) {
    Write-Host "PLUGIN_JOURNAL_EVIDENCE_BEGIN"
    $pluginMatches | Select-Object -Last $Tail | ForEach-Object {
        Write-Host ("{0}: {1}" -f $_.LineNumber, $_.Line.Trim())
    }
    Write-Host "PLUGIN_JOURNAL_EVIDENCE_END"
}

if ($errorMatches) {
    Write-Host "PLUGIN_ERROR_EVIDENCE_BEGIN"
    $errorMatches | Select-Object -Last $Tail | ForEach-Object {
        Write-Host ("{0}: {1}" -f $_.LineNumber, $_.Line.Trim())
    }
    Write-Host "PLUGIN_ERROR_EVIDENCE_END"
}

if ($successMatches) {
    Write-Host "PLUGIN_SUCCESS_EVIDENCE_BEGIN"
    $successMatches | Select-Object -Last $Tail | ForEach-Object {
        Write-Host ("{0}: {1}" -f $_.LineNumber, $_.Line.Trim())
    }
    Write-Host "PLUGIN_SUCCESS_EVIDENCE_END"
}

if (-not [string]::IsNullOrWhiteSpace($PluginLogPath)) {
    if (Test-Path -LiteralPath $PluginLogPath) {
        $log = Get-Item -LiteralPath $PluginLogPath
        Write-Host "PLUGIN_LOG=$($log.FullName)"
        Write-Host "PLUGIN_LOG_LAST_WRITE=$($log.LastWriteTime.ToString('s'))"
        Write-Host "PLUGIN_LOG_SIZE=$($log.Length)"
        Write-Host "PLUGIN_LOG_TAIL_BEGIN"
        Get-Content -LiteralPath $PluginLogPath -Tail $Tail
        Write-Host "PLUGIN_LOG_TAIL_END"
    }
    else {
        Write-Host "PLUGIN_LOG_MISSING=$PluginLogPath"
    }
}

if ($errorMatches) {
    Write-Host "REVIT_PLUGIN_EVIDENCE=ERROR"
    exit 2
}

if ($successMatches) {
    Write-Host "REVIT_PLUGIN_EVIDENCE=SUCCESS"
    exit 0
}

Write-Host "REVIT_PLUGIN_EVIDENCE=NO_MATCH"
if ($RequireSuccess) {
    exit 1
}

exit 0
