# Revit WPF UI Automation

Use this reference when the task requires real UI behavior: Revit ribbon buttons, WPF plugin windows, TextBox/CheckBox/RadioButton changes, and Revit model-view clicks.

For feature-level test design, read `feature-test-design.md` first, then use this file to execute the UI layer.

## Core Rule

Drive the same surface the user drives, then verify outside the automation call.

```text
Revit loaded plugin
  -> UIA finds ribbon/window/control
  -> UIA invokes or clicks the command
  -> UIA edits WPF parameters
  -> mouse click targets the Revit model view when the Revit API is waiting for PickObject
  -> plugin log, Journal, Revit model state, or exported evidence proves the result
```

Do not treat a successful UIA click as a passed test. The click is only an input. The pass condition is the downstream Revit/plugin result.

## Testability Pass

Before writing a brittle UI test, inspect the current WPF implementation:

```powershell
rg -n "AutomationProperties|x:Name|Content=|Header=|TextBox|Button|CheckBox|RadioButton|Slider" . -g "*.xaml"
```

Prefer stable locators in this order:

| Target | Preferred locator | Notes |
| --- | --- | --- |
| Plugin windows | `WindowTitleRegex` | Example: `Finio.*参数化柜子` |
| WPF inputs/buttons | `AutomationProperties.AutomationId` | Add IDs to product XAML when absent and testability is in scope |
| Revit ribbon buttons | `NameRegex` + `ControlType Button` | Revit often exposes localized button text/tooltip rather than custom IDs |
| WPF custom controls | expose AutomationProperties on the outer control and inner `TextBox`/`Button` | Templates can hide useful labels from UIA |
| Revit model elements | mouse coordinates in a fixed test model/view | UIA cannot see Revit model geometry as element-level controls |

For Finio-style panels, add explicit automation IDs before relying on text-box order. Good examples:

```xml
<Button AutomationProperties.AutomationId="CabinetPickWallButton"
        Content="拾取墙面" />
<TextBox AutomationProperties.AutomationId="CabinetWidthInput"
         Text="{Binding Options.Width}" />
<CheckBox AutomationProperties.AutomationId="CabinetSplitBackPanelsSwitch" />
<Button AutomationProperties.AutomationId="SlabPlaceButton"
        Content="放置槽板" />
```

For custom controls such as a `SliderField`, expose the logical name on the root and a stable ID on the inner value TextBox. If the template cannot expose the inner input, UI tests should operate on the root only when it exposes `ValuePattern` or a reliable child.

## Script Usage

Use `scripts/Invoke-RevitWpfUiAutomation.ps1` as the default action runner.

### Revit-Owned WPF Windows

Non-modal WPF windows opened by a Revit add-in may not appear as independent desktop root windows. Revit often exposes them as descendant `ControlType=Window` nodes under the main Revit window. Always pass the Revit process id/name and a plugin window title regex, then let the script search child windows:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessId $revitPid `
  -WindowTitleRegex "Finio.*参数化柜子" `
  -Action Wait `
  -ControlType Window
```

Do not conclude that a command failed just because a desktop-root window lookup did not find the WPF window. First dump the Revit process tree and check for a child window title.

### Revit Ribbon Buttons

Revit ribbon commands can expose more than one UIA node for the same visible button. Prefer the innermost `ControlType=Button` when present:

```text
ControlType=Custom AutomationId='...CabinetCommand_RibbonItemControl' Name='柜子'
  ControlType=Button AutomationId='...CabinetCommand' Name='柜子'
```

The wrapper `Custom` element may expose only `SynchronizedInputPattern`; invoking or center-clicking it can produce only hover/tooltip evidence. Use the child `Button` with `InvokePattern` when available. If only a custom wrapper is exposed, record Journal evidence such as `Jrn.RibbonEvent "Execute external command:..."` before treating the action as successful.

### Foreground And Tooltip Interference

Mouse-based fallback must bring the target Revit window to the foreground before clicking. Otherwise Windows can send the click to a foreground terminal/browser even though UIA located a Revit element.

During Revit command mode, transient tooltip/shadow windows such as `ClassName='SysShadow'` can temporarily be the first UIA window for the process. For model-view coordinate clicks, pass a main-window title regex:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessId $revitPid `
  -WindowTitleRegex "Autodesk Revit" `
  -Action ClickPoint `
  -WindowX 1050 `
  -WindowY 520
```

This keeps window-relative coordinates anchored to the actual Revit main window rather than to a tooltip window.

Dump visible UIA tree for Revit:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -Action Dump `
  -MaxDepth 7 `
  -OutputPath "$env:TEMP\revit-uia.txt"
```

Click or invoke a Revit ribbon button:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -Action Invoke `
  -NameRegex "柜子|参数化创建柜子" `
  -ControlType Button `
  -MouseFallback
```

Wait for a WPF plugin window:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -WindowTitleRegex "Finio.*参数化柜子" `
  -Action Wait `
  -ControlType Window
```

Set a WPF TextBox value:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -WindowTitleRegex "Finio.*参数化柜子" `
  -Action SetValue `
  -AutomationId CabinetWidthInput `
  -Value 1200
```

Toggle a WPF switch/checkbox:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -WindowTitleRegex "Finio.*参数化柜子" `
  -Action Toggle `
  -AutomationId CabinetSplitBackPanelsSwitch
```

Click a plugin command button:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -WindowTitleRegex "Finio.*参数化槽板" `
  -Action Invoke `
  -AutomationId SlabPlaceButton `
  -MouseFallback
```

Click inside the Revit model view while Revit is waiting for a PickObject-style selection:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -Action ClickPoint `
  -WindowTitleRegex "Autodesk Revit" `
  -WindowX 760 `
  -WindowY 430
```

Send Escape after a continuous pick loop:

```powershell
& "$skillRoot\scripts\Invoke-RevitWpfUiAutomation.ps1" `
  -ProcessName Revit `
  -Action SendKeys `
  -Keys "{ESC}"
```

## Finio-Style Smoke Shape

Use this as the target shape, not as a hardcoded script:

1. Build/deploy/install the plugin.
2. Run deployment evidence and assembly-load smoke.
3. Start Revit and wait for `API_SUCCESS`.
4. Dump UIA tree and save it as an artifact.
5. Invoke the Revit ribbon command: `柜子` or `槽板`.
6. Wait for the WPF window title: `Finio · 参数化柜子` or `Finio · 参数化槽板`.
7. Set inputs using `AutomationId`; if the current XAML lacks IDs, add them before writing long-lived tests.
8. Invoke the WPF command button.
9. If Revit prompts for element selection, click a deterministic point in a fixed test model/view.
10. Verify plugin logs, Journal lines, Revit transaction logs, created element count, or exported model evidence.

For Finio current ribbon evidence, the expected tab is `Finio`, modeling panel is `参数化建模`, and buttons are `柜子` and `槽板`; the service panel has `关于`. Re-read `ApplicationUI.cs` before relying on those names.

## Revit Model Clicks

UI Automation cannot identify individual Revit walls, faces, DirectShapes, or family instances inside the model canvas. For model picks:

- Use a dedicated test RVT with a deterministic startup view.
- Keep Revit window size, zoom, view orientation, and active view stable.
- Prefer one click per test step; after each click, wait for plugin status/log evidence.
- Store click coordinates relative to the Revit window, not absolute screen coordinates.
- Treat coordinate clicks as the last mile only. All WPF/ribbon controls should still use UIA locators.

If a coordinate click becomes flaky, create a small Revit-side test command or seed model view that exposes a predictable selection target. Do not replace end-to-end UI testing with service calls unless the user's claim is service-level.

## Failure Triage

| Symptom | Inspect first |
| --- | --- |
| UIA cannot find ribbon button | Dump Revit UIA tree, check tab selected state, localized `Name`, and loaded plugin state |
| WPF window appears but input cannot be found | XAML lacks `AutomationProperties.AutomationId`, template hides inner TextBox, or window title regex targets the wrong window |
| `SetValue` does nothing | control lacks `ValuePattern`; verify focus and binding update trigger, then use keyboard fallback only for throwaway tests |
| button click returns success but no Revit result | command disabled, wrong window, pending modal dialog, Revit external event not executed, or missing model selection |
| model click misses element | window/view geometry changed; reset test model view and use window-relative coordinates |
| continuous pick loop hangs | send `{ESC}` and inspect plugin status text/log for cancellation or exception |
