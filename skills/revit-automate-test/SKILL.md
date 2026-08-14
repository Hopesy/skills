---
name: revit-automate-test
description: Design, run, stabilize, and diagnose real-host automation tests for Revit plugins and Revit plugin templates. Use when Codex needs to analyze a Revit plugin feature and decide how to automate it, verify MSI deployment, .addin loading, Confuser/obfuscation output, Revit Journal evidence, plugin startup logs, Revit ribbon/command entry points, WPF plugin windows, UI Automation flows, TextBox/CheckBox/RadioButton input changes, Revit model-view mouse clicks, generated template projects, or flaky Revit plugin E2E smoke tests.
license: MIT
metadata:
  author: hopesy
  version: "1.0.0"
---

# Revit Automate Test

Use this skill to prove a Revit plugin works through the same path a user actually uses:

```text
understand feature behavior
  -> map user actions to automation primitives
  -> build/deploy package
  -> real Revit .addin loading mechanism
  -> current deployed artifact evidence
  -> Revit Journal/plugin log startup evidence
  -> real ribbon/command/WPF UI entry point
  -> Revit model-view mouse input when the plugin waits for user picks
  -> independent result evidence
```

Do not replace host E2E validation with direct service calls unless the user explicitly asks for service-level testing.
Do not treat bundled scripts as the test plan. The agent must analyze each plugin feature, choose the right action sequence, execute it with the scripts, and judge the result from independent evidence.

## Feature-First Workflow

1. Read current plugin code, XAML, command registration, and logs for the feature under test.
2. Identify the user-visible workflow: ribbon entry, WPF windows, inputs, command buttons, Revit picks, expected model or data result.
3. Map each user action to a capability: UIA dump/wait/invoke/set/toggle/select, model-view click, SendKeys, deployment evidence, Journal/log collection, assembly-load smoke.
4. Define pass/fail evidence before executing. Prefer Revit model state, plugin logs, Journal lines, file/database side effects, or exported evidence.
5. Execute with the bundled scripts and save high-signal artifacts: UIA dump, command output, logs, hashes, model/result evidence.
6. If a step fails, diagnose the broken stage instead of blindly retrying.

Read `references/feature-test-design.md` when planning how to automate an unfamiliar plugin feature or when converting a manual test scenario into an executable Revit/WPF E2E flow.

## Bundled Scripts

Prefer these scripts before rewriting PowerShell from scratch.

```text
scripts/Test-DotNetAssemblyLoad.ps1
```

Use for fast pre-Revit validation of a deployed or staged .NET plugin assembly. It catches `BadImageFormatException`, illegal metadata, and malformed nested-type metadata before launching Revit.
Use `-ExpectedType` only when the type is known to be preserved by the obfuscation rules. For obfuscated Revit plugins, assembly load success is the pre-Revit gate; Journal `API_SUCCESS` is the entry-type proof.

```powershell
& "$skillRoot\scripts\Test-DotNetAssemblyLoad.ps1" `
  -AssemblyPath "$env:APPDATA\Autodesk\Revit\Addins\2027\Finio\Finio.dll" `
  -TargetFramework net10.0
```

```text
scripts/Get-RevitAddinDeployment.ps1
```

Use before launching Revit or after MSI install/uninstall to prove the real Addins deployment state. It parses the `.addin`, resolves the target assembly path, prints file version/hash/timestamp, lists top-level plugin directory contents, flags `runtime`/`runtimes` directories and `.pdb` files, and can also summarize the shared Data root.

```powershell
& "$skillRoot\scripts\Get-RevitAddinDeployment.ps1" `
  -RevitYear 2027 `
  -PluginName Finio `
  -ExpectedAssemblyName Finio.dll `
  -DataRoot "$env:APPDATA\Finio\Data" `
  -RequireAssembly `
  -FailOnMissing
```

```text
scripts/Get-RevitPluginEvidence.ps1
```

Use after a Revit run to collect the latest Journal evidence and optional plugin log tail. Add `-RequireSuccess` when the absence of `API_SUCCESS` should fail the test.

```powershell
& "$skillRoot\scripts\Get-RevitPluginEvidence.ps1" `
  -RevitYear 2027 `
  -PluginName Finio `
  -PluginLogPath "$env:APPDATA\Finio\Data\Logs\Finio$(Get-Date -Format yyyyMMdd).log" `
  -RequireSuccess
```

```text
scripts/Start-RevitPluginSmoke.ps1
```

Use for a conservative real Revit startup smoke. It refuses to launch when another Revit process already exists, checks Journal/log evidence, optionally clicks trust dialogs, and closes only the process it started.

```powershell
& "$skillRoot\scripts\Start-RevitPluginSmoke.ps1" `
  -RevitYear 2027 `
  -PluginName Finio `
  -PluginLogPath "$env:APPDATA\Finio\Data\Logs\Finio$(Get-Date -Format yyyyMMdd).log"
```

```text
scripts/Test-RevitTemplatePackage.ps1
```

Use for `.NET template` repositories. It packs the template, installs it into a custom hive, generates a project, builds the generated installer in `Release`, and runs the assembly-load smoke on the generated R27 payload.

```powershell
& "$skillRoot\scripts\Test-RevitTemplatePackage.ps1" `
  -NuspecPath ".\Saury.Revit.Template.nuspec" `
  -ShortName saury-revit `
  -ProjectName TemplateSmoke
```

Read `references/checklist.md` when designing a new end-to-end flow, adding command/ribbon interaction, or diagnosing a flaky run.
Read `references/revit-wpf-ui-automation.md` when testing WPF plugin windows, changing input values, clicking Revit ribbon commands, or driving Revit model-view picks.

```text
scripts/Invoke-RevitWpfUiAutomation.ps1
```

Use as the default UI action runner. It can dump Revit/UIA trees, wait for windows/controls, invoke or mouse-click buttons, set WPF TextBox values, toggle checkboxes, select radio/list items, send keys, and click fixed points inside the Revit model view.

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -Action Invoke `
  -NameRegex "Cabinet|Create Cabinet" `
  -ControlType Button `
  -MouseFallback

& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -WindowTitleRegex "Finio.*Cabinet" `
  -Action SetValue `
  -AutomationId CabinetWidthInput `
  -Value 1200
```

## Test Boundary

Pick the narrowest boundary that proves the user's claim.

| Boundary | Use when | Evidence |
| --- | --- | --- |
| Assembly-load smoke | Confuser/obfuscation, bad metadata, packaged DLL loadability | `LOAD_SMOKE_OK`, no `BadImageFormatException` |
| Deployment evidence | MSI/build deploy state, `.addin` path, stale files, uninstall residue | `.addin` entry, assembly version/hash/timestamp, plugin dir summary |
| Package/install smoke | MSI output, feature selection, deployment path | MSI exit code/log, deployed artifact hash/timestamp |
| Revit startup smoke | `.addin` loading, startup exceptions, trust prompt behavior | Journal `API_SUCCESS`, plugin startup log |
| WPF/UI Automation E2E | Ribbon command, WPF parameter panel, Revit pick workflow | UIA dump/actions plus plugin log/model/file/database side effect |
| Template smoke | Generated project and generated installer behavior | custom-hive generation, generated Release MSI, load smoke |

For plugin acceptance, prefer package/install smoke + Revit startup smoke + at least one WPF/UI Automation E2E path. For obfuscation changes, always run assembly-load smoke before launching Revit.

## Required Facts

Before running or editing tests, identify:

- Revit year and executable path.
- Plugin loading mechanism: `.addin`, Addins directory, registry, or installer feature.
- Build command and whether it deploys to the real Revit Addins location.
- Current deployed artifact path and version/hash/timestamp.
- Plugin startup log path, if the plugin has one.
- Latest Revit Journal directory.
- Real user entry point when testing behavior: ribbon button, WPF window title, command button, input AutomationId, shortcut, dialog, or model-view click.
- Current WPF locator state: `AutomationProperties.AutomationId`, `Name`, `x:Name`, button `Content`, tab `Header`, and custom-control templates.
- Safety boundary: existing Revit processes, unsaved documents, paid APIs, credentials, destructive file/database changes.

Ask the user only if continuing could test the wrong plugin, wrong Revit version, wrong account, or a destructive target. Otherwise choose a conservative test path and proceed.

## Standard Workflows

### Obfuscated MSI Plugin

1. Build the Release installer with the project's documented command.
2. Confirm build logs show the intended obfuscation/protection list.
3. Install the MSI with a verbose log when possible.
4. Verify the `.addin`, resolved assembly, version/hash/timestamp, and plugin directory with `Get-RevitAddinDeployment.ps1`.
5. Run `Test-DotNetAssemblyLoad.ps1` on the deployed main assembly.
6. Launch Revit only after deployment evidence and assembly load both succeed.
7. Collect Journal and plugin log evidence with `Get-RevitPluginEvidence.ps1`.
8. If needed, trigger a real ribbon command using UI Automation or a documented command entry point.

If assembly-load smoke fails, do not retry Revit. Diagnose the obfuscator/protection list first.

### Revit Template Repository

1. Run `Test-RevitTemplatePackage.ps1` against the template `.nuspec`.
2. Confirm the generated project name replaces assembly names, installer names, environment variable prefixes, `.addin`, and output MSI names.
3. Confirm the generated installer `Release` build runs obfuscation for every supported Revit year.
4. Run assembly-load smoke on the generated R27 payload.

Use a custom hive and temp directory so the test does not pollute the user's global template installation.

### Real Revit Startup

1. Check for existing `Revit` processes. Do not force-close user-owned sessions unless the user clearly authorized it.
2. Start Revit with the target year/language.
3. Handle trust dialogs, license prompts, and modal blockers as part of the test.
4. Wait by evidence, not fixed sleeps: Journal lines, plugin log, window readiness, or command UI availability.
5. Close only the Revit process started by the test.

### WPF UI Automation E2E

1. Re-read the current plugin XAML before writing locators. Prefer `AutomationProperties.AutomationId`; add stable IDs when testability changes are in scope.
2. Write a feature-specific action/evidence plan before executing. Use `references/feature-test-design.md`.
3. Dump the Revit UIA tree with `Invoke-RevitWpfUiAutomation.ps1 -Action Dump` and keep the dump as evidence.
4. Invoke the Revit ribbon command by stable UIA locator. Use `-MouseFallback` only when Revit exposes the button without `InvokePattern`.
5. Wait for the plugin WPF window by title regex.
6. Set WPF inputs by `AutomationId`, toggle switches, select radio/list items, and invoke the plugin command button.
7. When the plugin enters a Revit selection loop, click model geometry by window-relative coordinates in a fixed test RVT/view.
8. Send `{ESC}` after continuous pick workflows.
9. Verify the downstream result through plugin logs, Journal, Revit model state, exported evidence, or database/file side effects.

Do not rely on coordinate clicks for WPF controls. Coordinates are acceptable only for the Revit model canvas, because UIA does not expose individual Revit elements/faces as controls.

## Failure Triage

Diagnose by stage:

| Symptom | Inspect first |
| --- | --- |
| Build succeeds but Revit cannot load | Assembly-load smoke, obfuscation rules, deployed DLL hash |
| MSI says success but plugin is absent | `Get-RevitAddinDeployment.ps1`, `.addin` root, feature selection, verbose MSI log |
| Uninstall leaves plugin files | deployment evidence script on every supported Revit year, MSI ownership, manual leftovers |
| `Illegal tables in compressed metadata stream` | `invalid metadata` or similar metadata protection |
| `Enclosing type(s) not found` | constants/string protection or malformed obfuscator metadata |
| Plugin has no startup log | `.addin`, Addins path, trust dialog, Journal startup exception |
| Journal has `API_ERROR` | exception near `Starting External Application`, plugin dependencies |
| Ribbon button missing | startup/Ribbon initialization, add-in load, UIA tree dump, localized button `Name` |
| WPF input missing | XAML lacks `AutomationProperties.AutomationId`, template hides inner control, wrong window title regex |
| Button clicked but no result | command disabled, wrong window, pending modal dialog, missing Revit external event/log side effect |
| Revit model click misses | unstable test model/view/window size, wrong window-relative coordinates |
| Tool-like text but no execution | protocol leakage; require server-side call/log evidence |

## Reporting Standard

Report only high-signal facts:

- Commands run and what each proved.
- Deployed artifact path/version/hash if relevant.
- Revit Journal evidence lines.
- Plugin log evidence lines.
- Whether failure was build, package, load, startup, UI invocation, or business result.
- What remains unverified.

Do not include secrets. Redact tokens, API keys, credentials, connection strings, checkout links, and paid-service details.
