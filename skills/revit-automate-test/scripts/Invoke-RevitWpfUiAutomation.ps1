param(
    [string] $ProcessName = "Revit",

    [int] $ProcessId = 0,

    [string] $WindowTitleRegex = "",

    [ValidateSet("Dump", "Wait", "Invoke", "Click", "SetValue", "Toggle", "Select", "Expand", "Collapse", "SendKeys", "ClickPoint")]
    [string] $Action = "Dump",

    [string] $AutomationId = "",

    [string] $Name = "",

    [string] $NameRegex = "",

    [string] $HelpText = "",

    [string] $ClassName = "",

    [string] $ControlType = "",

    [string] $Value = "",

    [string] $Keys = "",

    [int] $TimeoutSeconds = 30,

    [int] $MaxDepth = 8,

    [int] $MaxResults = 200,

    [string] $OutputPath = "",

    [switch] $IncludeOffscreen,

    [switch] $MouseFallback,

    [int] $ScreenX = [int]::MinValue,

    [int] $ScreenY = [int]::MinValue,

    [int] $WindowX = [int]::MinValue,

    [int] $WindowY = [int]::MinValue,

    [int] $ElementOffsetX = 0,

    [int] $ElementOffsetY = 0,

    [int] $AfterDelayMs = 250
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RevitUiAutomationMouse
{
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    public static extern void mouse_event(int flags, int dx, int dy, int data, IntPtr extraInfo);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    public const int LeftDown = 0x0002;
    public const int LeftUp = 0x0004;
    public const int Restore = 9;
}
"@

function Get-PropertyValue {
    param(
        [System.Windows.Automation.AutomationElement] $Element,
        [System.Windows.Automation.AutomationProperty] $Property,
        [object] $Fallback = $null
    )

    try {
        $value = $Element.GetCurrentPropertyValue($Property, $true)
        if ($null -eq $value -or [object]::ReferenceEquals($value, [System.Windows.Automation.AutomationElement]::NotSupported)) {
            return $Fallback
        }

        return $value
    }
    catch {
        return $Fallback
    }
}

function Get-ControlTypeByName {
    param([string] $TypeName)

    if ([string]::IsNullOrWhiteSpace($TypeName)) {
        return $null
    }

    $property = [System.Windows.Automation.ControlType].GetProperty(
        $TypeName,
        [System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Static -bor [System.Reflection.BindingFlags]::IgnoreCase)

    if ($null -ne $property) {
        return $property.GetValue($null)
    }

    $field = [System.Windows.Automation.ControlType].GetField(
        $TypeName,
        [System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Static -bor [System.Reflection.BindingFlags]::IgnoreCase)

    if ($null -ne $field) {
        return $field.GetValue($null)
    }

    if ($null -eq $property -and $null -eq $field) {
        $knownProperties = [System.Windows.Automation.ControlType].GetProperties(
            [System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Static) |
            Select-Object -ExpandProperty Name
        $knownFields = [System.Windows.Automation.ControlType].GetFields(
            [System.Reflection.BindingFlags]::Public -bor [System.Reflection.BindingFlags]::Static) |
            Select-Object -ExpandProperty Name
        $known = @($knownProperties) + @($knownFields) | Sort-Object -Unique
        throw "Unknown ControlType '$TypeName'. Known values include: $($known -join ', ')"
    }
}

function Get-ControlTypeName {
    param([object] $Type)

    if ($null -eq $Type) {
        return ""
    }

    $programmatic = [string] $Type.ProgrammaticName
    if ($programmatic.StartsWith("ControlType.")) {
        return $programmatic.Substring("ControlType.".Length)
    }

    return $programmatic
}

function Get-ElementRect {
    param([System.Windows.Automation.AutomationElement] $Element)

    return [System.Windows.Rect] (Get-PropertyValue `
        -Element $Element `
        -Property ([System.Windows.Automation.AutomationElement]::BoundingRectangleProperty) `
        -Fallback ([System.Windows.Rect]::Empty))
}

function Set-AutomationWindowForeground {
    param([System.Windows.Automation.AutomationElement] $Window)

    if ($null -eq $Window) {
        return
    }

    $handleValue = Get-PropertyValue `
        -Element $Window `
        -Property ([System.Windows.Automation.AutomationElement]::NativeWindowHandleProperty) `
        -Fallback 0
    $handle = [IntPtr] ([int64] $handleValue)
    if ($handle -eq [IntPtr]::Zero) {
        return
    }

    [void] [RevitUiAutomationMouse]::ShowWindow($handle, [RevitUiAutomationMouse]::Restore)
    [void] [RevitUiAutomationMouse]::SetForegroundWindow($handle)
    Start-Sleep -Milliseconds 160
}

function Format-Element {
    param([System.Windows.Automation.AutomationElement] $Element)

    $nameValue = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::NameProperty) -Fallback "")
    $automationIdValue = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::AutomationIdProperty) -Fallback "")
    $classNameValue = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::ClassNameProperty) -Fallback "")
    $helpTextValue = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::HelpTextProperty) -Fallback "")
    $controlTypeValue = Get-ControlTypeName (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::ControlTypeProperty) -Fallback $null)
    $enabledValue = [bool] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::IsEnabledProperty) -Fallback $false)
    $offscreenValue = [bool] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::IsOffscreenProperty) -Fallback $true)
    $rect = Get-ElementRect -Element $Element

    return "ControlType=$controlTypeValue AutomationId='$automationIdValue' Name='$nameValue' ClassName='$classNameValue' HelpText='$helpTextValue' Enabled=$enabledValue Offscreen=$offscreenValue Rect=$($rect.Left),$($rect.Top),$($rect.Width),$($rect.Height)"
}

function Get-TargetProcesses {
    if ($ProcessId -gt 0) {
        return @(Get-Process -Id $ProcessId -ErrorAction Stop)
    }

    return @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)
}

function Get-ProcessWindows {
    param([System.Diagnostics.Process[]] $Processes)

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $windows = @()

    foreach ($process in $Processes) {
        $condition = [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
            $process.Id)

        $found = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)
        for ($i = 0; $i -lt $found.Count; $i++) {
            $window = $found.Item($i)
            $windows += $window
        }

        if ($windows.Count -eq 0 -and $process.MainWindowHandle -ne [IntPtr]::Zero) {
            $main = [System.Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
            if ($null -ne $main) {
                $windows += $main
            }
        }
    }

    return @($windows | Select-Object -Unique)
}

function Get-SearchRoots {
    param([System.Windows.Automation.AutomationElement[]] $Windows)

    if ([string]::IsNullOrWhiteSpace($WindowTitleRegex)) {
        return $Windows
    }

    $roots = @()
    $windowType = Get-ControlTypeByName -TypeName "Window"
    $windowCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        $windowType)

    foreach ($window in $Windows) {
        $windowName = [string] (Get-PropertyValue -Element $window -Property ([System.Windows.Automation.AutomationElement]::NameProperty) -Fallback "")
        if ($windowName -match $WindowTitleRegex) {
            $roots += $window
        }

        $childWindows = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $windowCondition)
        for ($i = 0; $i -lt $childWindows.Count; $i++) {
            $child = $childWindows.Item($i)
            $childName = [string] (Get-PropertyValue -Element $child -Property ([System.Windows.Automation.AutomationElement]::NameProperty) -Fallback "")
            if ($childName -match $WindowTitleRegex) {
                $roots += $child
            }
        }
    }

    return @($roots | Select-Object -Unique)
}

function Wait-ForWindows {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $processes = Get-TargetProcesses
        if ($processes.Count -gt 0) {
            $windows = Get-ProcessWindows -Processes $processes
            if ($windows.Count -gt 0) {
                return $windows
            }
        }

        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    if ($ProcessId -gt 0) {
        throw "No UI Automation windows found for process id $ProcessId within $TimeoutSeconds seconds."
    }

    throw "No UI Automation windows found for process '$ProcessName' within $TimeoutSeconds seconds."
}

function Test-ElementMatch {
    param([System.Windows.Automation.AutomationElement] $Element)

    $elementAutomationId = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::AutomationIdProperty) -Fallback "")
    $elementName = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::NameProperty) -Fallback "")
    $elementHelpText = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::HelpTextProperty) -Fallback "")
    $elementClassName = [string] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::ClassNameProperty) -Fallback "")
    $elementControlType = Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::ControlTypeProperty) -Fallback $null
    $elementOffscreen = [bool] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::IsOffscreenProperty) -Fallback $true)

    if (-not $IncludeOffscreen -and $elementOffscreen) {
        return $false
    }

    if (-not [string]::IsNullOrWhiteSpace($AutomationId) -and $elementAutomationId -ne $AutomationId) {
        return $false
    }

    if (-not [string]::IsNullOrWhiteSpace($Name) -and $elementName -ne $Name) {
        return $false
    }

    if (-not [string]::IsNullOrWhiteSpace($NameRegex) -and $elementName -notmatch $NameRegex) {
        return $false
    }

    if (-not [string]::IsNullOrWhiteSpace($HelpText) -and $elementHelpText -ne $HelpText) {
        return $false
    }

    if (-not [string]::IsNullOrWhiteSpace($ClassName) -and $elementClassName -ne $ClassName) {
        return $false
    }

    $wantedType = Get-ControlTypeByName -TypeName $ControlType
    if ($null -ne $wantedType -and $elementControlType.Id -ne $wantedType.Id) {
        return $false
    }

    return $true
}

function Find-ElementOnce {
    param([System.Windows.Automation.AutomationElement[]] $Windows)

    $searchRoots = Get-SearchRoots -Windows $Windows
    foreach ($window in $searchRoots) {
        if (Test-ElementMatch -Element $window) {
            return $window
        }

        $searchRoot = $window
        $candidates = $null
        if (-not [string]::IsNullOrWhiteSpace($AutomationId)) {
            $condition = [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
                $AutomationId)
            $candidates = $searchRoot.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
        }
        else {
            $candidates = $searchRoot.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition)
        }

        for ($i = 0; $i -lt $candidates.Count; $i++) {
            $candidate = $candidates.Item($i)
            if (Test-ElementMatch -Element $candidate) {
                return $candidate
            }
        }
    }

    return $null
}

function Wait-ForElement {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $windows = Wait-ForWindows
        $element = Find-ElementOnce -Windows $windows
        if ($null -ne $element) {
            return $element
        }

        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    throw "UI Automation element not found within $TimeoutSeconds seconds. Filters: AutomationId='$AutomationId', Name='$Name', NameRegex='$NameRegex', ControlType='$ControlType', WindowTitleRegex='$WindowTitleRegex'."
}

function Get-ClickPoint {
    param(
        [System.Windows.Automation.AutomationElement] $Element = $null,
        [System.Windows.Automation.AutomationElement[]] $Windows = @()
    )

    if ($ScreenX -ne [int]::MinValue -and $ScreenY -ne [int]::MinValue) {
        return [System.Drawing.Point]::new($ScreenX, $ScreenY)
    }

    if ($WindowX -ne [int]::MinValue -and $WindowY -ne [int]::MinValue) {
        if ($Windows.Count -eq 0) {
            $Windows = Wait-ForWindows
        }

        $windowRect = Get-ElementRect -Element $Windows[0]
        return [System.Drawing.Point]::new(
            [int] [Math]::Round($windowRect.Left + $WindowX),
            [int] [Math]::Round($windowRect.Top + $WindowY))
    }

    if ($null -eq $Element) {
        throw "Click requires an element, absolute -ScreenX/-ScreenY, or window-relative -WindowX/-WindowY."
    }

    $rect = Get-ElementRect -Element $Element
    if ($rect.IsEmpty -or $rect.Width -le 0 -or $rect.Height -le 0) {
        throw "Element has no clickable bounding rectangle: $(Format-Element -Element $Element)"
    }

    return [System.Drawing.Point]::new(
        [int] [Math]::Round($rect.Left + ($rect.Width / 2) + $ElementOffsetX),
        [int] [Math]::Round($rect.Top + ($rect.Height / 2) + $ElementOffsetY))
}

function Invoke-MouseClick {
    param([System.Drawing.Point] $Point)

    Write-Host "MOUSE_CLICK=$($Point.X),$($Point.Y)"
    [void] [RevitUiAutomationMouse]::SetCursorPos($Point.X, $Point.Y)
    Start-Sleep -Milliseconds 80
    [RevitUiAutomationMouse]::mouse_event([RevitUiAutomationMouse]::LeftDown, 0, 0, 0, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 80
    [RevitUiAutomationMouse]::mouse_event([RevitUiAutomationMouse]::LeftUp, 0, 0, 0, [IntPtr]::Zero)
}

function Invoke-ElementPattern {
    param(
        [System.Windows.Automation.AutomationElement] $Element,
        [System.Windows.Automation.AutomationPattern] $Pattern
    )

    $patternObject = $null
    if ($Element.TryGetCurrentPattern($Pattern, [ref] $patternObject)) {
        return $patternObject
    }

    return $null
}

function Invoke-Element {
    param([System.Windows.Automation.AutomationElement] $Element)

    $invokePattern = Invoke-ElementPattern -Element $Element -Pattern ([System.Windows.Automation.InvokePattern]::Pattern)
    if ($null -ne $invokePattern) {
        $invokePattern.Invoke()
        Write-Host "INVOKE_METHOD=InvokePattern"
        return
    }

    if ($MouseFallback) {
        Invoke-MouseClick -Point (Get-ClickPoint -Element $Element)
        Write-Host "INVOKE_METHOD=MouseFallback"
        return
    }

    throw "Element does not expose InvokePattern. Retry with -MouseFallback only if a center click is safe. Element: $(Format-Element -Element $Element)"
}

function Set-ElementValue {
    param([System.Windows.Automation.AutomationElement] $Element)

    $valuePattern = Invoke-ElementPattern -Element $Element -Pattern ([System.Windows.Automation.ValuePattern]::Pattern)
    if ($null -ne $valuePattern) {
        $valuePattern.SetValue($Value)
        Write-Host "SETVALUE_METHOD=ValuePattern"
        return
    }

    $Element.SetFocus()
    Start-Sleep -Milliseconds 120
    [System.Windows.Forms.SendKeys]::SendWait("^a")
    Start-Sleep -Milliseconds 80
    [System.Windows.Forms.SendKeys]::SendWait($Value)
    Write-Host "SETVALUE_METHOD=KeyboardFallback"
}

function Send-ElementKeys {
    param([System.Windows.Automation.AutomationElement] $Element = $null)

    $keysToSend = if ([string]::IsNullOrWhiteSpace($Keys)) { $Value } else { $Keys }
    if ([string]::IsNullOrWhiteSpace($keysToSend)) {
        throw "SendKeys requires -Keys or -Value."
    }

    if ($null -ne $Element) {
        $Element.SetFocus()
    }

    Start-Sleep -Milliseconds 120
    [System.Windows.Forms.SendKeys]::SendWait($keysToSend)
    Write-Host "SEND_KEYS=$keysToSend"
}

function Write-Dump {
    param([System.Windows.Automation.AutomationElement[]] $Windows)

    $lines = [System.Collections.Generic.List[string]]::new()

    function Walk {
        param(
            [System.Windows.Automation.AutomationElement] $Element,
            [int] $Depth
        )

        if ($Depth -gt $MaxDepth -or $lines.Count -ge $MaxResults) {
            return
        }

        $offscreenValue = [bool] (Get-PropertyValue -Element $Element -Property ([System.Windows.Automation.AutomationElement]::IsOffscreenProperty) -Fallback $true)
        if ($IncludeOffscreen -or -not $offscreenValue) {
            $lines.Add(("{0}{1}" -f ("  " * $Depth), (Format-Element -Element $Element)))
        }

        $children = $Element.FindAll(
            [System.Windows.Automation.TreeScope]::Children,
            [System.Windows.Automation.Condition]::TrueCondition)

        for ($i = 0; $i -lt $children.Count; $i++) {
            Walk -Element $children.Item($i) -Depth ($Depth + 1)
        }
    }

    foreach ($window in $Windows) {
        Walk -Element $window -Depth 0
    }

    if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
        $resolved = [System.IO.Path]::GetFullPath($OutputPath)
        $parent = Split-Path -Parent $resolved
        if (-not [string]::IsNullOrWhiteSpace($parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }

        $lines | Set-Content -LiteralPath $resolved -Encoding UTF8
        Write-Host "UIA_DUMP=$resolved"
    }
    else {
        $lines | ForEach-Object { Write-Host $_ }
    }

    Write-Host "UIA_DUMP_COUNT=$($lines.Count)"
}

$windows = Wait-ForWindows
Write-Host "UIA_WINDOW_COUNT=$($windows.Count)"
for ($i = 0; $i -lt $windows.Count; $i++) {
    Write-Host "UIA_WINDOW[$i]=$(Format-Element -Element $windows[$i])"
}

if ($Action -eq "Dump") {
    Write-Dump -Windows (Get-SearchRoots -Windows $windows)
    exit 0
}

if ($Action -eq "ClickPoint") {
    $clickWindows = Get-SearchRoots -Windows $windows
    if ($clickWindows.Count -eq 0) {
        $clickWindows = $windows
    }

    Set-AutomationWindowForeground -Window $clickWindows[0]
    Invoke-MouseClick -Point (Get-ClickPoint -Windows $clickWindows)
    Start-Sleep -Milliseconds $AfterDelayMs
    exit 0
}

$needsElement = @("Wait", "Invoke", "Click", "SetValue", "Toggle", "Select", "Expand", "Collapse")
$element = $null
if ($needsElement -contains $Action -or -not [string]::IsNullOrWhiteSpace($AutomationId) -or -not [string]::IsNullOrWhiteSpace($Name) -or -not [string]::IsNullOrWhiteSpace($NameRegex) -or -not [string]::IsNullOrWhiteSpace($ControlType)) {
    $element = Wait-ForElement
    Write-Host "ELEMENT_FOUND=$(Format-Element -Element $element)"
}

switch ($Action) {
    "Wait" {
        Start-Sleep -Milliseconds $AfterDelayMs
        exit 0
    }
    "Invoke" {
        Set-AutomationWindowForeground -Window $windows[0]
        Invoke-Element -Element $element
    }
    "Click" {
        Set-AutomationWindowForeground -Window $windows[0]
        Invoke-MouseClick -Point (Get-ClickPoint -Element $element)
    }
    "SetValue" {
        Set-ElementValue -Element $element
    }
    "Toggle" {
        $togglePattern = Invoke-ElementPattern -Element $element -Pattern ([System.Windows.Automation.TogglePattern]::Pattern)
        if ($null -eq $togglePattern) {
            throw "Element does not expose TogglePattern: $(Format-Element -Element $element)"
        }

        $togglePattern.Toggle()
        Write-Host "TOGGLE_METHOD=TogglePattern"
    }
    "Select" {
        $selectPattern = Invoke-ElementPattern -Element $element -Pattern ([System.Windows.Automation.SelectionItemPattern]::Pattern)
        if ($null -eq $selectPattern) {
            throw "Element does not expose SelectionItemPattern: $(Format-Element -Element $element)"
        }

        $selectPattern.Select()
        Write-Host "SELECT_METHOD=SelectionItemPattern"
    }
    "Expand" {
        $expandPattern = Invoke-ElementPattern -Element $element -Pattern ([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
        if ($null -eq $expandPattern) {
            throw "Element does not expose ExpandCollapsePattern: $(Format-Element -Element $element)"
        }

        $expandPattern.Expand()
        Write-Host "EXPAND_METHOD=ExpandCollapsePattern"
    }
    "Collapse" {
        $collapsePattern = Invoke-ElementPattern -Element $element -Pattern ([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
        if ($null -eq $collapsePattern) {
            throw "Element does not expose ExpandCollapsePattern: $(Format-Element -Element $element)"
        }

        $collapsePattern.Collapse()
        Write-Host "COLLAPSE_METHOD=ExpandCollapsePattern"
    }
    "SendKeys" {
        if ($null -eq $element -and $windows.Count -gt 0) {
            $element = $windows[0]
        }

        Set-AutomationWindowForeground -Window $windows[0]
        Send-ElementKeys -Element $element
    }
}

Start-Sleep -Milliseconds $AfterDelayMs
exit 0
