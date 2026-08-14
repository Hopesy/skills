# Feature Test Design

Use this reference before automating a plugin feature. The goal is not to run a fixed script. The goal is to let the agent understand the feature, choose the correct automation primitives, execute them, and judge the result from independent evidence.

## Core Loop

```text
Understand feature
  -> identify user-facing entry points
  -> inspect WPF/Revit implementation and current locators
  -> map each user action to a supported automation primitive
  -> define evidence that proves the feature worked
  -> run actions with bundled scripts
  -> analyze logs/Journals/model outputs
  -> revise locators or test setup when evidence is weak
```

The bundled scripts provide capabilities. The agent must still design the feature-specific path.

## Feature Intake

Read the current code and artifacts, not old assumptions.

| Need | Inspect |
| --- | --- |
| Ribbon entry | `ApplicationUI.cs`, command registration, `.addin`, UIA tree dump |
| Command behavior | `IExternalCommand`, command availability, ViewModel command, service method |
| WPF panel | `.xaml`, `.xaml.cs`, ViewModel properties, command bindings, custom control templates |
| Revit pick workflow | Revit API calls such as `PickObject`, status text, cancellation path |
| Expected model result | transactions, family names, element tags, parameters, updater side effects |
| Result evidence | plugin log, Journal, database/file changes, exported model state, Revit element count |

If the feature uses a WPF panel, inspect the current XAML for `AutomationProperties.AutomationId`. If it is missing and a long-lived test is expected, add stable automation IDs rather than relying on visual order.

## Action Mapping

Map user-visible behavior to the narrowest reliable primitive:

| User action | Primitive | Script |
| --- | --- | --- |
| Open plugin from Revit ribbon | `Invoke` or `Click` on button by UIA locator | `Invoke-RevitWpfUiAutomation.ps1` |
| Wait for panel/dialog | wait by window title and UIA control | `Invoke-RevitWpfUiAutomation.ps1 -Action Wait` |
| Change numeric/text parameter | `SetValue` by AutomationId | `Invoke-RevitWpfUiAutomation.ps1 -Action SetValue` |
| Enable/disable option | `Toggle` by AutomationId | `Invoke-RevitWpfUiAutomation.ps1 -Action Toggle` |
| Choose mode/type | `Select` on RadioButton/list item, or `Invoke` when template exposes button-like behavior | `Invoke-RevitWpfUiAutomation.ps1` |
| Run command button | `Invoke`, with mouse fallback only if required | `Invoke-RevitWpfUiAutomation.ps1 -Action Invoke -MouseFallback` |
| Click wall/face/back panel/family instance in Revit view | window-relative `ClickPoint` in fixed model/view | `Invoke-RevitWpfUiAutomation.ps1 -Action ClickPoint` |
| End continuous pick loop | `SendKeys "{ESC}"` | `Invoke-RevitWpfUiAutomation.ps1 -Action SendKeys` |
| Prove plugin loaded | Journal/plugin log evidence | `Get-RevitPluginEvidence.ps1` |
| Prove deployment is current | `.addin`, DLL hash/version/timestamp | `Get-RevitAddinDeployment.ps1` |
| Catch broken obfuscation | assembly-load smoke | `Test-DotNetAssemblyLoad.ps1` |

Use coordinate clicks only for Revit model canvas actions. Do not use coordinates for WPF inputs, buttons, tabs, menus, or dialogs unless it is a short throwaway diagnostic and the limitation is reported.

## Evidence Design

Every automated feature test needs a pass condition outside the input script:

| Feature type | Strong evidence |
| --- | --- |
| Opens UI | window title plus required controls in UIA dump |
| Updates settings | UI value after edit plus persisted file/database/config value |
| Creates Revit elements | transaction success, log line, element count, element names/tags/parameters |
| Modifies selected model element | before/after parameter or geometry evidence |
| Loads family | family symbol exists and expected type is active |
| Deletes generated content | generated element count goes to zero; non-owned user data remains |
| Installer/uninstaller behavior | verbose MSI log plus deployment/data directory evidence |
| Obfuscated plugin load | assembly-load success plus Revit Journal `API_SUCCESS` |

When only one evidence source exists, report the residual risk. For example, a log line without model state proves the command ran, not necessarily that geometry is correct.

## Planning Template

Use this compact plan before executing an unfamiliar feature:

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

Then execute with the bundled scripts. Update the plan if the UIA dump or code inspection disproves the initial locator assumptions.

## Example: Cabinet Generator

This is an example shape for a Finio-like feature, not a hardcoded recipe:

```text
Feature: generate a cabinet from a picked wall point.
Entry point: Revit ribbon button for cabinet command.
Required Revit state: deterministic test RVT, known wall visible in active view.
UI locators: cabinet window title, width/depth/height inputs, split-back switch, pick-wall button, generate button.
Actions:
  1. invoke ribbon button
  2. wait for cabinet WPF window
  3. set width/depth/height
  4. toggle desired options
  5. invoke pick-wall button
  6. click fixed wall point in Revit model view
  7. invoke generate button
Evidence:
  - status text or plugin log says pick completed
  - transaction/log says generation completed
  - generated element count or tags match expectation
Cleanup:
  - invoke delete button or run cleanup command
```

## Example: Slab Panel Placement

```text
Feature: place slab panels on generated back panels.
Precondition: cabinet/back panels already generated in fixed model view.
Entry point: Revit ribbon button for slab panel command.
Actions:
  1. invoke slab panel ribbon button
  2. wait for slab panel WPF window
  3. set top/bottom offsets and mode
  4. invoke place button
  5. click one or more deterministic back-panel points in the Revit model view
  6. send Escape to finish continuous pick
Evidence:
  - plugin log reports placed count
  - family instances or tags for slab panels exist
  - frame/updater side effect exists when expected
```

## Failure Analysis

Analyze failures by where the chain broke:

| Stage | Typical failure | Response |
| --- | --- | --- |
| Feature understanding | wrong command or wrong precondition | re-read command/ViewModel/service code |
| Locator discovery | UIA cannot find control | dump tree; add `AutomationProperties.AutomationId`; avoid order-based locators |
| UI action | input changed visually but binding not updated | check `UpdateSourceTrigger`, focus loss, command enablement |
| Revit pick | click misses target | reset model view/window geometry; use window-relative coordinates |
| External event | button clicked but command did not execute | inspect busy state, modal blockers, plugin log, Revit Journal |
| Result verification | weak or ambiguous evidence | add log/model export/query before claiming pass |

The correct response to weak evidence is to improve observability or test setup, not to mark the UI click as success.
