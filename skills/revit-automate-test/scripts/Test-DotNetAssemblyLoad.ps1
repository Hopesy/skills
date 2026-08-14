param(
    [Parameter(Mandatory = $true)]
    [string] $AssemblyPath,

    [string] $TargetFramework = "",

    [string] $ExpectedType = "",

    [string[]] $ProbeDirectory = @(),

    [switch] $GetTypes,

    [int] $TimeoutSeconds = 60,

    [string] $WorkRoot = ""
)

$ErrorActionPreference = "Stop"

function Resolve-TargetFramework {
    param([string] $Path, [string] $Explicit)

    if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
        return $Explicit
    }

    if ($Path -match "net8\.0") {
        return "net8.0"
    }

    return "net10.0"
}

function New-SafeTempDirectory {
    param([string] $Root)

    if ([string]::IsNullOrWhiteSpace($Root)) {
        $Root = Join-Path $env:TEMP "revit-plugin-loadsmoke"
    }

    $base = [System.IO.Path]::GetFullPath($Root)
    $temp = [System.IO.Path]::GetFullPath($env:TEMP)
    if (-not $base.StartsWith($temp, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "WorkRoot must be under TEMP for this smoke script: $base"
    }

    $dir = Join-Path $base ([Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    return $dir
}

$resolvedAssembly = [System.IO.Path]::GetFullPath($AssemblyPath)
if (-not (Test-Path -LiteralPath $resolvedAssembly)) {
    throw "Assembly not found: $resolvedAssembly"
}

$tfm = Resolve-TargetFramework -Path $resolvedAssembly -Explicit $TargetFramework
$work = New-SafeTempDirectory -Root $WorkRoot

$projectPath = Join-Path $work "LoadSmoke.csproj"
$programPath = Join-Path $work "Program.cs"

@"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>$tfm</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
"@ | Set-Content -LiteralPath $projectPath -Encoding UTF8

@'
using System.Reflection;
using System.Runtime.Loader;

var assemblyPath = Path.GetFullPath(args[0]);
var expectedType = args.Length > 1 && args[1] != "__NONE__" ? args[1] : string.Empty;
var getTypes = args.Length > 2 && bool.TryParse(args[2], out var parsedGetTypes) && parsedGetTypes;
var probeDirectories = args.Skip(3)
    .Where(path => !string.IsNullOrWhiteSpace(path))
    .Select(Path.GetFullPath)
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .ToArray();

var pluginDirectory = Path.GetDirectoryName(assemblyPath)
    ?? throw new InvalidOperationException("Missing plugin directory.");

AssemblyLoadContext.Default.Resolving += (_, assemblyName) =>
{
    foreach (var directory in new[] { pluginDirectory }.Concat(probeDirectories))
    {
        var candidate = Path.Combine(directory, assemblyName.Name + ".dll");
        if (File.Exists(candidate))
        {
            return AssemblyLoadContext.Default.LoadFromAssemblyPath(candidate);
        }
    }

    return null;
};

try
{
    Console.WriteLine("Loading " + assemblyPath);
    var assembly = AssemblyLoadContext.Default.LoadFromAssemblyPath(assemblyPath);
    Console.WriteLine("Loaded " + assembly.FullName);

    if (!string.IsNullOrWhiteSpace(expectedType))
    {
        var type = assembly.GetType(expectedType, throwOnError: false);
        if (type == null)
        {
            Console.WriteLine("LOAD_SMOKE_TYPE_MISSING " + expectedType);
            return 11;
        }

        Console.WriteLine("ExpectedType=" + type.FullName);
    }

    if (getTypes)
    {
        try
        {
            var types = assembly.GetTypes();
            Console.WriteLine("Types=" + types.Length);
        }
        catch (ReflectionTypeLoadException ex)
        {
            Console.WriteLine("LOAD_SMOKE_REFLECTION_TYPE_LOAD_EXCEPTION");
            foreach (var loaderException in ex.LoaderExceptions.Where(item => item != null).Take(40))
            {
                Console.WriteLine(loaderException!.GetType().FullName + ": " + loaderException.Message);
            }

            return 12;
        }
    }

    Console.WriteLine("LOAD_SMOKE_OK");
    return 0;
}
catch (BadImageFormatException ex)
{
    Console.WriteLine("LOAD_SMOKE_BAD_IMAGE");
    Console.WriteLine(ex.GetType().FullName + ": " + ex.Message);
    return 10;
}
catch (Exception ex)
{
    Console.WriteLine("LOAD_SMOKE_FAILED");
    Console.WriteLine(ex.GetType().FullName + ": " + ex.Message);
    Console.WriteLine(ex);
    return 20;
}
'@ | Set-Content -LiteralPath $programPath -Encoding UTF8

$expectedTypeArg = if ([string]::IsNullOrWhiteSpace($ExpectedType)) { "__NONE__" } else { $ExpectedType }

$arguments = @(
    "run",
    "--project",
    $projectPath,
    "--",
    $resolvedAssembly,
    $expectedTypeArg,
    [string] [bool] $GetTypes
) + $ProbeDirectory

$process = Start-Process -FilePath "dotnet" -ArgumentList $arguments -NoNewWindow -PassThru -RedirectStandardOutput (Join-Path $work "stdout.txt") -RedirectStandardError (Join-Path $work "stderr.txt")
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    $process.Kill()
    $process.WaitForExit()
    Write-Host "LOAD_SMOKE_TIMEOUT after $TimeoutSeconds seconds"
    exit 30
}
$stdout = Get-Content -LiteralPath (Join-Path $work "stdout.txt") -Raw -ErrorAction SilentlyContinue
$stderr = Get-Content -LiteralPath (Join-Path $work "stderr.txt") -Raw -ErrorAction SilentlyContinue

if (-not [string]::IsNullOrWhiteSpace($stdout)) {
    Write-Host $stdout.TrimEnd()
}

if (-not [string]::IsNullOrWhiteSpace($stderr)) {
    Write-Error $stderr.TrimEnd()
}

exit $process.ExitCode
