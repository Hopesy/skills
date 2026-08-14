# Plugin E2E Automation Checklist

Use this reference as a fill-in checklist. Keep the test tied to real host behavior and evidence.

## Boundary Matrix

| Boundary | Trigger | Proves | Does not prove |
| --- | --- | --- | --- |
| Service-level | Direct class/method/API call | Core logic can run | Host can load plugin, UI path works |
| Command-entry | Host command/menu/ribbon/shortcut | Plugin entry and host integration work | Full user workflow and UI state work |
| Full UI E2E | Real host UI interaction | Deployment, loading, UI, dependencies, business path work | Pure logic is exhaustively covered |

For plugin acceptance, use full UI E2E unless there is a concrete reason not to.

## Facts To Collect

| Item | Evidence |
| --- | --- |
| Feature behavior | command code, ViewModel, service method, user-visible workflow |
| Host executable | Path exists and version is correct |
| Host process name | `Get-Process`, task list, browser profile, or host CLI |
| Plugin loading mechanism | Manifest, registry, extension profile, package folder, autoload config |
| Deploy command | Build/deploy script or project target that updates host-loaded files |
| Loaded artifact | DLL/package/extension file timestamp and version in deployed location |
| Test file/workspace | Project/document/profile used by the host |
| Plugin startup | Main log line, host extension list, loaded module, UI panel |
| Dependency readiness | Service log, port listener, database, provider config, MCP connection |
| Real entry point | Stable UI locator, command ID, menu/ribbon path, shortcut |
| Expected result | Host state change, log line, server call, file/database/network side effect |

## Feature Automation Design

Before running UIA actions, write a short feature-specific plan:

```text
Feature:
Entry point:
Required Revit state:
Required plugin state:
UI locators to inspect/add:
Action sequence:
Model-view clicks:
Expected evidence:
Failure logs to collect:
Cleanup/rollback:
```

Use `references/feature-test-design.md` for the full design method. The script calls are execution tools; they are not a substitute for understanding the feature.

## Bundled Script Mapping

| Need | Script | Typical proof |
| --- | --- | --- |
| Check obfuscated/staged DLL before launching Revit | `scripts/Test-DotNetAssemblyLoad.ps1` | `LOAD_SMOKE_OK`, no `BadImageFormatException` |
| Prove real Revit Addins deployment state | `scripts/Get-RevitAddinDeployment.ps1` | `.addin` entry, resolved assembly, version/hash, stale `.pdb`/runtime evidence |
| Read latest Revit Journal and plugin log | `scripts/Get-RevitPluginEvidence.ps1` | `API_SUCCESS`, plugin startup log, or localized error evidence |
| Launch real Revit for startup smoke | `scripts/Start-RevitPluginSmoke.ps1` | current Revit process, Journal `API_SUCCESS`, plugin startup log |
| Drive Revit ribbon/WPF controls/model clicks | `scripts/Invoke-RevitWpfUiAutomation.ps1` | UIA dump, control action evidence, model-view click coordinates |
| Validate a Revit `.NET template` package end to end | `scripts/Test-RevitTemplatePackage.ps1` | custom-hive generation, generated installer Release build, R27 payload load smoke |

Use scripts for deterministic steps; use this checklist for host/UI-specific judgment and evidence planning.

## Readiness Gates

Do not proceed until the necessary gates pass.

| Gate | Typical check |
| --- | --- |
| Host started | Process exists and responds |
| File/workspace loaded | Window title, host API, document list, project state |
| Deployment current | `.addin` resolves to the expected DLL, and file hash/timestamp matches the build/install under test |
| Plugin loaded | Startup log, loaded modules, extension list, panel visible |
| Services ready | Log says connected, port opens, health endpoint, MCP connected |
| UIA tree available | Revit top-level windows can be dumped and saved |
| WPF controls ready | target window title and target `AutomationId`/`Name` exist, button enabled, busy state cleared |
| Revit model view stable | fixed test model/view/window geometry is loaded before coordinate clicks |

Use bounded polling. On timeout, collect process state and recent logs.

## Preferred Locators

| UI technology | Prefer | Avoid |
| --- | --- | --- |
| WPF/WinForms | UI Automation `AutomationId`, `Name`, `HelpText`, patterns | Coordinates |
| Web/Electron | Playwright role/label/test id/text locators | CSS based on layout only |
| Ribbon/menu hosts | Documented command ID or automation name | Pixel clicks |
| Revit model canvas | fixed test model/view + window-relative coordinates | absolute screen coordinates |
| CLI-capable hosts | Official CLI/API command | Reverse-engineered private calls |

## Windows UI Automation Skeleton

```powershell
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$p = Get-Process HostProcessName -ErrorAction Stop | Select-Object -First 1
$root = [System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
if ($null -eq $root) { throw 'Unable to access host UI Automation root.' }

$input = $root.FindFirst(
  [System.Windows.Automation.TreeScope]::Descendants,
  [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
    'InputAutomationId'))

if ($null -eq $input) { throw 'Input element not found.' }

$valuePattern = $null
if ($input.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$valuePattern)) {
  $valuePattern.SetValue('test input')
} else {
  $input.SetFocus()
  throw 'Input does not expose ValuePattern; decide whether keyboard fallback is safe.'
}

$buttons = $root.FindAll(
  [System.Windows.Automation.TreeScope]::Descendants,
  [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button))

$target = $null
foreach ($button in $buttons) {
  if ($button.Current.AutomationId -eq 'RunButton'
      -or $button.Current.Name -eq 'Run'
      -or $button.Current.HelpText -eq 'Run') {
    $target = $button
    break
  }
}

if ($null -eq $target) { throw 'Action button not found.' }

$invoke = $null
if (-not $target.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$invoke)) {
  throw 'Action button does not expose InvokePattern.'
}

$invoke.Invoke()
```

## Revit/WPF UIA Flow

For Revit plugins with WPF panels:

1. Read current XAML and add stable `AutomationProperties.AutomationId` when controls do not expose reliable names.
2. Start Revit and verify plugin load.
3. Dump UIA tree:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -Action Dump `
  -OutputPath "$env:TEMP\revit-uia.txt"
```

4. Invoke the Revit ribbon command:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -Action Invoke `
  -NameRegex "柜子|槽板|参数化" `
  -ControlType Button `
  -MouseFallback
```

5. Edit WPF inputs and invoke the plugin action:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -WindowTitleRegex "Finio.*参数化柜子" `
  -Action SetValue `
  -AutomationId CabinetWidthInput `
  -Value 1200
```

6. For Revit `PickObject` prompts, click a deterministic point in the model view:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -WindowTitleRegex "Autodesk Revit" `
  -Action ClickPoint `
  -WindowX 760 `
  -WindowY 430
```

7. Verify by plugin log, Journal, model element count, exported file, or database side effect.

## Generic PowerShell Flow

```powershell
$ErrorActionPreference = 'Stop'

$repo = 'repo path'
$hostExe = 'host exe path'
$testFile = 'test file path'
$pluginArtifact = 'deployed plugin artifact path'
$mainLog = 'main log path'
$serviceLog = 'service log path'

if (-not (Test-Path -LiteralPath $hostExe)) { throw "Host not found: $hostExe" }
if (-not (Test-Path -LiteralPath $testFile)) { throw "Test file not found: $testFile" }

Set-Location -LiteralPath $repo
dotnet build .\Plugin\Plugin.csproj -c Debug -v:minimal

Get-Item -LiteralPath $pluginArtifact |
  Select-Object FullName,Length,LastWriteTime,
    @{n='ProductVersion';e={$_.VersionInfo.ProductVersion}},
    @{n='FileVersion';e={$_.VersionInfo.FileVersion}} |
  Format-List

Start-Process -FilePath $hostExe -ArgumentList "`"$testFile`""

$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
  if (Test-Path -LiteralPath $mainLog) {
    $recent = Get-Content -LiteralPath $mainLog -Tail 200
    if ($recent -match 'plugin started' -and $recent -match 'service connected') {
      $ready = $true
      break
    }
  }
  Start-Sleep -Seconds 3
}
if (-not $ready) { throw 'Plugin not ready.' }

# Trigger the real entry point here.

Get-Content -LiteralPath $mainLog -Tail 500 |
  Select-String -Pattern 'input received|command started|command completed|error|exception'

if (Test-Path -LiteralPath $serviceLog) {
  Get-Content -LiteralPath $serviceLog -Tail 500 |
    Select-String -Pattern 'request|response|tools/call|command'
}
```

## Failure Triage

| Symptom | First place to inspect |
| --- | --- |
| Artifact cannot be copied | Existing host process locking DLL/package |
| MSI install succeeds but Revit does not load plugin | `.addin` root, feature selection, resolved assembly path, deployed DLL hash |
| Uninstall leaves Addins folder residue | MSI component ownership, wildcard cleanup policy, pre-existing manual files |
| Host starts but plugin has no logs | Manifest, registry, extension folder, trust dialog, startup exception |
| Startup log exists but UI entry is missing | Dock/panel visibility, UI initialization, changed automation IDs |
| Input was set but no business log appears | Button/command not invoked, command disabled, busy state, wrong window |
| Business log appears but no external call | Provider/service config, dependency readiness, network error |
| Tool-like text appears but no execution | Protocol leakage; require structured call and server-side request |
| Server call exists but host state unchanged | Host transaction failure, invalid command args, document state, permissions |
| Result appears but test is flaky | Replace sleeps/coordinates with readiness gates and stable locators |

## Completion Criteria

The test is credible only when it confirms:

- Host-loaded deployed artifact is current.
- Plugin startup is observed in the real host.
- Required dependency readiness is observed.
- The feature-specific workflow is understood and mapped to concrete UIA/mouse/key actions.
- The action sequence uses real user-facing entry points and inputs.
- Downstream behavior is verified outside the automation script itself.
- Failure logs are captured when a stage fails.
- Secrets are redacted from all output.
