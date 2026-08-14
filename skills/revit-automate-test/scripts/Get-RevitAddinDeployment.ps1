param(
    [string] $RevitYear = "2027",

    [Parameter(Mandatory = $true)]
    [string] $PluginName,

    [ValidateSet("User", "Machine", "Both")]
    [string] $Scope = "User",

    [string] $AddinRoot = "",

    [string] $AddinFileName = "",

    [string] $ExpectedAssemblyName = "",

    [string] $DataRoot = "",

    [switch] $RequireAssembly,

    [switch] $FailOnMissing,

    [int] $MaxListedFiles = 80
)

$ErrorActionPreference = "Stop"

function Get-DefaultAddinRoots {
    param(
        [string] $Year,
        [string] $SelectedScope
    )

    $roots = @()
    if ($SelectedScope -eq "User" -or $SelectedScope -eq "Both") {
        $roots += [pscustomobject]@{
            Scope = "User"
            Path = Join-Path $env:APPDATA "Autodesk\Revit\Addins\$Year"
        }
    }

    if ($SelectedScope -eq "Machine" -or $SelectedScope -eq "Both") {
        $roots += [pscustomobject]@{
            Scope = "Machine"
            Path = Join-Path $env:ProgramData "Autodesk\Revit\Addins\$Year"
        }
    }

    return $roots
}

function Get-ChildText {
    param(
        [System.Xml.XmlNode] $Node,
        [string] $Name
    )

    $child = $Node.ChildNodes |
        Where-Object { $_.LocalName -eq $Name } |
        Select-Object -First 1

    if ($null -eq $child) {
        return ""
    }

    return [string] $child.InnerText
}

function Resolve-AssemblyPath {
    param(
        [string] $AddinPath,
        [string] $AssemblyValue
    )

    if ([string]::IsNullOrWhiteSpace($AssemblyValue)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($AssemblyValue)) {
        return [System.IO.Path]::GetFullPath($AssemblyValue)
    }

    return [System.IO.Path]::GetFullPath(
        (Join-Path (Split-Path -Parent $AddinPath) $AssemblyValue))
}

function Test-AddinMatchesPlugin {
    param(
        [string] $AddinPath,
        [System.Xml.XmlNode] $AddinNode,
        [string] $Name
    )

    $escaped = [regex]::Escape($Name)
    $leaf = [System.IO.Path]::GetFileNameWithoutExtension($AddinPath)
    $candidateText = @(
        $leaf,
        (Get-ChildText -Node $AddinNode -Name "Name"),
        (Get-ChildText -Node $AddinNode -Name "Assembly"),
        (Get-ChildText -Node $AddinNode -Name "FullClassName")
    ) -join "`n"

    return $candidateText -match $escaped
}

function Read-AddinEntries {
    param([System.IO.FileInfo] $File)

    try {
        [xml] $doc = Get-Content -LiteralPath $File.FullName -Raw
        $nodes = $doc.SelectNodes("//*[local-name()='AddIn']")
        if ($null -eq $nodes -or $nodes.Count -eq 0) {
            return @()
        }

        return @($nodes)
    }
    catch {
        Write-Host "ADDIN_XML_PARSE_ERROR=$($File.FullName)"
        Write-Host "ADDIN_XML_PARSE_EXCEPTION=$($_.Exception.GetType().FullName): $($_.Exception.Message)"
        return @()
    }
}

function Write-AssemblyEvidence {
    param(
        [string] $AssemblyPath,
        [string] $ExpectedName,
        [bool] $Require
    )

    if ([string]::IsNullOrWhiteSpace($AssemblyPath)) {
        Write-Host "ASSEMBLY_RESOLVED="
        if ($Require) {
            return $false
        }

        return $true
    }

    Write-Host "ASSEMBLY_RESOLVED=$AssemblyPath"

    if (-not (Test-Path -LiteralPath $AssemblyPath)) {
        Write-Host "ASSEMBLY_EXISTS=false"
        return (-not $Require)
    }

    $item = Get-Item -LiteralPath $AssemblyPath
    $hash = Get-FileHash -LiteralPath $AssemblyPath -Algorithm SHA256
    Write-Host "ASSEMBLY_EXISTS=true"
    Write-Host "ASSEMBLY_LENGTH=$($item.Length)"
    Write-Host "ASSEMBLY_LAST_WRITE=$($item.LastWriteTime.ToString('s'))"
    Write-Host "ASSEMBLY_FILE_VERSION=$($item.VersionInfo.FileVersion)"
    Write-Host "ASSEMBLY_PRODUCT_VERSION=$($item.VersionInfo.ProductVersion)"
    Write-Host "ASSEMBLY_SHA256=$($hash.Hash)"

    $ok = $true
    if (-not [string]::IsNullOrWhiteSpace($ExpectedName)) {
        $actualName = [System.IO.Path]::GetFileName($AssemblyPath)
        Write-Host "ASSEMBLY_EXPECTED_NAME=$ExpectedName"
        Write-Host "ASSEMBLY_ACTUAL_NAME=$actualName"
        if ($actualName -ne $ExpectedName) {
            Write-Host "ASSEMBLY_NAME_MATCH=false"
            $ok = $false
        }
        else {
            Write-Host "ASSEMBLY_NAME_MATCH=true"
        }
    }

    $pluginDir = Split-Path -Parent $AssemblyPath
    Write-Host "PLUGIN_DIR=$pluginDir"
    if (Test-Path -LiteralPath $pluginDir) {
        $files = @(Get-ChildItem -LiteralPath $pluginDir -Recurse -File -ErrorAction SilentlyContinue)
        $dirs = @(Get-ChildItem -LiteralPath $pluginDir -Recurse -Directory -ErrorAction SilentlyContinue)
        Write-Host "PLUGIN_DIR_FILE_COUNT=$($files.Count)"
        Write-Host "PLUGIN_DIR_DIR_COUNT=$($dirs.Count)"

        $runtimeDirs = @($dirs | Where-Object { $_.Name -in @("runtime", "runtimes") })
        if ($runtimeDirs.Count -gt 0) {
            Write-Host "RUNTIME_DIRS_BEGIN"
            $runtimeDirs | Select-Object -First $MaxListedFiles | ForEach-Object {
                Write-Host $_.FullName
            }
            Write-Host "RUNTIME_DIRS_END"
        }

        $pdbFiles = @($files | Where-Object { $_.Extension -eq ".pdb" })
        if ($pdbFiles.Count -gt 0) {
            Write-Host "PDB_FILES_BEGIN"
            $pdbFiles | Select-Object -First $MaxListedFiles | ForEach-Object {
                Write-Host $_.FullName
            }
            Write-Host "PDB_FILES_END"
        }

        Write-Host "PLUGIN_DIR_TOP_LEVEL_BEGIN"
        Get-ChildItem -LiteralPath $pluginDir -Force -ErrorAction SilentlyContinue |
            Sort-Object PSIsContainer, Name |
            Select-Object -First $MaxListedFiles |
            ForEach-Object {
                $kind = if ($_.PSIsContainer) { "DIR " } else { "FILE" }
                Write-Host ("{0} {1} {2}" -f $kind, $_.LastWriteTime.ToString("s"), $_.FullName)
            }
        Write-Host "PLUGIN_DIR_TOP_LEVEL_END"
    }

    return $ok
}

function Write-DataRootEvidence {
    param([string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    $resolved = [System.IO.Path]::GetFullPath($Path)
    Write-Host "DATA_ROOT=$resolved"
    if (-not (Test-Path -LiteralPath $resolved)) {
        Write-Host "DATA_ROOT_EXISTS=false"
        return
    }

    $item = Get-Item -LiteralPath $resolved
    Write-Host "DATA_ROOT_EXISTS=true"
    Write-Host "DATA_ROOT_LAST_WRITE=$($item.LastWriteTime.ToString('s'))"

    $files = @(Get-ChildItem -LiteralPath $resolved -Recurse -File -ErrorAction SilentlyContinue)
    $dirs = @(Get-ChildItem -LiteralPath $resolved -Recurse -Directory -ErrorAction SilentlyContinue)
    Write-Host "DATA_ROOT_FILE_COUNT=$($files.Count)"
    Write-Host "DATA_ROOT_DIR_COUNT=$($dirs.Count)"
    Write-Host "DATA_ROOT_TOP_LEVEL_BEGIN"
    Get-ChildItem -LiteralPath $resolved -Force -ErrorAction SilentlyContinue |
        Sort-Object PSIsContainer, Name |
        Select-Object -First 40 |
        ForEach-Object {
            $kind = if ($_.PSIsContainer) { "DIR " } else { "FILE" }
            Write-Host ("{0} {1} {2}" -f $kind, $_.LastWriteTime.ToString("s"), $_.FullName)
        }
    Write-Host "DATA_ROOT_TOP_LEVEL_END"
}

if ([string]::IsNullOrWhiteSpace($AddinFileName)) {
    $AddinFileName = "$PluginName.addin"
}

$roots = if ([string]::IsNullOrWhiteSpace($AddinRoot)) {
    Get-DefaultAddinRoots -Year $RevitYear -SelectedScope $Scope
}
else {
    @([pscustomobject]@{
        Scope = "Custom"
        Path = [System.IO.Path]::GetFullPath($AddinRoot)
    })
}

Write-Host "REVIT_YEAR=$RevitYear"
Write-Host "PLUGIN_NAME=$PluginName"
Write-Host "ADDIN_SCOPE=$Scope"

$foundAnyAddin = $false
$matchedAnyEntry = $false
$ok = $true

foreach ($root in $roots) {
    Write-Host "ADDIN_ROOT_$($root.Scope.ToUpperInvariant())=$($root.Path)"
    if (-not (Test-Path -LiteralPath $root.Path)) {
        Write-Host "ADDIN_ROOT_EXISTS_$($root.Scope.ToUpperInvariant())=false"
        continue
    }

    Write-Host "ADDIN_ROOT_EXISTS_$($root.Scope.ToUpperInvariant())=true"
    $candidates = @()
    $exact = Join-Path $root.Path $AddinFileName
    if (Test-Path -LiteralPath $exact) {
        $candidates += Get-Item -LiteralPath $exact
    }

    $scan = @(Get-ChildItem -LiteralPath $root.Path -Filter "*.addin" -File -ErrorAction SilentlyContinue)
    foreach ($file in $scan) {
        if (-not ($candidates | Where-Object { $_.FullName -eq $file.FullName })) {
            $candidates += $file
        }
    }

    foreach ($candidate in $candidates) {
        $entries = @(Read-AddinEntries -File $candidate)
        foreach ($entry in $entries) {
            if (-not (Test-AddinMatchesPlugin -AddinPath $candidate.FullName -AddinNode $entry -Name $PluginName)) {
                continue
            }

            $foundAnyAddin = $true
            $matchedAnyEntry = $true

            $name = Get-ChildText -Node $entry -Name "Name"
            $type = ""
            if ($entry.Attributes["Type"]) {
                $type = $entry.Attributes["Type"].Value
            }
            $assemblyRaw = Get-ChildText -Node $entry -Name "Assembly"
            $assemblyResolved = Resolve-AssemblyPath -AddinPath $candidate.FullName -AssemblyValue $assemblyRaw

            Write-Host "ADDIN_FILE=$($candidate.FullName)"
            Write-Host "ADDIN_FILE_LENGTH=$($candidate.Length)"
            Write-Host "ADDIN_FILE_LAST_WRITE=$($candidate.LastWriteTime.ToString('s'))"
            Write-Host "ADDIN_NAME=$name"
            Write-Host "ADDIN_TYPE=$type"
            Write-Host "ADDIN_ASSEMBLY_RAW=$assemblyRaw"
            Write-Host "ADDIN_FULL_CLASS_NAME=$(Get-ChildText -Node $entry -Name 'FullClassName')"
            Write-Host "ADDIN_CLIENT_ID=$(Get-ChildText -Node $entry -Name 'ClientId')"
            Write-Host "ADDIN_VENDOR_ID=$(Get-ChildText -Node $entry -Name 'VendorId')"

            $assemblyOk = Write-AssemblyEvidence `
                -AssemblyPath $assemblyResolved `
                -ExpectedName $ExpectedAssemblyName `
                -Require ([bool] $RequireAssembly)

            if (-not $assemblyOk) {
                $ok = $false
            }
        }
    }
}

Write-DataRootEvidence -Path $DataRoot

if (-not $foundAnyAddin) {
    Write-Host "ADDIN_FOUND=false"
    if ($FailOnMissing) {
        exit 1
    }
}
else {
    Write-Host "ADDIN_FOUND=true"
}

if (-not $matchedAnyEntry) {
    Write-Host "ADDIN_ENTRY_MATCH=false"
    if ($FailOnMissing) {
        exit 1
    }
}
else {
    Write-Host "ADDIN_ENTRY_MATCH=true"
}

if (-not $ok) {
    exit 2
}

exit 0
