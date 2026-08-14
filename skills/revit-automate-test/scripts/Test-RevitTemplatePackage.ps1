param(
    [Parameter(Mandatory = $true)]
    [string] $NuspecPath,

    [string] $ShortName = "saury-revit",

    [string] $ProjectName = "TemplateSmoke",

    [string] $WorkRoot = "",

    [string] $InstallerProjectSuffix = ".Installer",

    [string] $Revit27TargetFramework = "net10.0-windows",

    [switch] $SkipAssemblyLoadSmoke
)

$ErrorActionPreference = "Stop"

function New-SafeWorkRoot {
    param([string] $Root)

    if ([string]::IsNullOrWhiteSpace($Root)) {
        $Root = Join-Path $env:TEMP "revit-template-smoke"
    }

    $resolvedRoot = [System.IO.Path]::GetFullPath($Root)
    $resolvedTemp = [System.IO.Path]::GetFullPath($env:TEMP)
    if (-not $resolvedRoot.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "WorkRoot must be under TEMP for this smoke script: $resolvedRoot"
    }

    if (Test-Path -LiteralPath $resolvedRoot) {
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Path $resolvedRoot -Force | Out-Null
    return $resolvedRoot
}

$resolvedNuspec = [System.IO.Path]::GetFullPath($NuspecPath)
if (-not (Test-Path -LiteralPath $resolvedNuspec)) {
    throw "Nuspec not found: $resolvedNuspec"
}

$root = New-SafeWorkRoot -Root $WorkRoot
$packageDir = Join-Path $root "pkg"
$hive = Join-Path $root "hive"
$out = Join-Path $root "out"
New-Item -ItemType Directory -Path $packageDir, $hive, $out -Force | Out-Null

Write-Host "SMOKE_ROOT=$root"
dotnet pack $resolvedNuspec -o $packageDir -v:minimal
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$package = Get-ChildItem -LiteralPath $packageDir -Filter "*.nupkg" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($null -eq $package) {
    throw "No nupkg produced in: $packageDir"
}

Write-Host "TEMPLATE_PACKAGE=$($package.FullName)"
dotnet new install $package.FullName --debug:custom-hive $hive
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$projectDir = Join-Path $out $ProjectName
dotnet new $ShortName -n $ProjectName -o $projectDir --debug:custom-hive $hive
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "GENERATED_PROJECT=$projectDir"

$installerProject = Join-Path $projectDir "$ProjectName$InstallerProjectSuffix\$ProjectName$InstallerProjectSuffix.csproj"
if (-not (Test-Path -LiteralPath $installerProject)) {
    throw "Generated installer project not found: $installerProject"
}

dotnet build $installerProject -c Release -v:minimal
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$msi = Get-ChildItem -LiteralPath (Join-Path (Split-Path -Parent $installerProject) "Output") -Filter "*.msi" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($null -eq $msi) {
    throw "No MSI produced by generated installer."
}

Write-Host "GENERATED_MSI=$($msi.FullName)"

if (-not $SkipAssemblyLoadSmoke) {
    $payloadDll = Join-Path (Split-Path -Parent $installerProject) "obj\InstallerPayload\Release_R27\$Revit27TargetFramework\$ProjectName.dll"
    if (-not (Test-Path -LiteralPath $payloadDll)) {
        throw "R27 payload assembly not found: $payloadDll"
    }

    $loadSmoke = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "Test-DotNetAssemblyLoad.ps1"
    & $loadSmoke -AssemblyPath $payloadDll -TargetFramework "net10.0"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "TEMPLATE_SMOKE_OK"
exit 0
