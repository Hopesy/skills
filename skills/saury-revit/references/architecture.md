# 架构参考

## 技术栈

| 技术 | 版本 | 用途 |
|---|---|---|
| .NET | 8.0 (net8.0-windows, x64) | 运行时 |
| WPF | 内置 | UI 框架 |
| CommunityToolkit.Mvvm | 8.4.0 | MVVM 源码生成器 |
| Microsoft.Extensions.Hosting | 9.0.4 | 依赖注入 + 生命周期管理 |
| Serilog | 9.0.0 | 文件日志 |
| Tuna.Revit.Extensions | 2026.0.20 | Revit API 辅助库 |

## 添加新功能完整流程

以「墙体分析器」为例，严格按 A→F 顺序执行。

### A. 创建 Model

文件：`Models/WallAnalysisResult.cs`

```csharp
namespace <项目名称>.Models;

public class WallAnalysisResult
{
    public string WallType { get; set; } = string.Empty;
    public double TotalArea { get; set; }
}
```

### B. 创建 ViewModel

文件：`ViewModels/WallAnalyzerViewModel.cs`

```csharp
using Autodesk.Revit.UI;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace <项目名称>.ViewModels;

public partial class WallAnalyzerViewModel : ObservableObject
{
    private readonly UIApplication? _uiApp;

    public WallAnalyzerViewModel(UIApplication? uiApp = null)
    {
        _uiApp = uiApp;
    }

    [ObservableProperty]
    private string result = string.Empty;

    [RelayCommand]
    private void Analyze()
    {
        // 业务逻辑
    }
}
```

**规则：**
- 类必须 `partial`（源码生成器要求）
- `[ObservableProperty]` 标注私有字段 → 自动生成公开属性
- `[RelayCommand]` 标注方法 → 自动生成 `ICommand`
- 构造函数注入 `UIApplication` 访问 Revit API
- 严禁在 ViewModel 中放 UI 代码（MessageBox、Window）

### C. 创建 View

文件：`Views/WallAnalyzerView.xaml`

```xml
<Window x:Class="<项目名称>.Views.WallAnalyzerView"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        xmlns:d="http://schemas.microsoft.com/expression/blend/2008"
        xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
        xmlns:vm="clr-namespace:<项目名称>.ViewModels"
        d:DataContext="{d:DesignInstance Type=vm:WallAnalyzerViewModel}"
        Title="墙体分析器" Width="400" Height="300"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize"
        mc:Ignorable="d">
    <Grid Margin="20">
        <TextBlock Text="{Binding Result}" />
    </Grid>
</Window>
```

文件：`Views/WallAnalyzerView.xaml.cs`

```csharp
using System.Windows;

namespace <项目名称>.Views;

public partial class WallAnalyzerView : Window
{
    public WallAnalyzerView(ViewModels.WallAnalyzerViewModel viewModel)
    {
        InitializeComponent();
        DataContext = viewModel;
    }
}
```

**规则：**
- 构造函数注入 ViewModel，设置 `DataContext = viewModel`
- 使用 `d:DesignInstance` 提供设计器类型提示
- 严禁 code-behind 中写业务逻辑
- 样式放 `Resources/Styles/`，严禁内联

### D. 创建 Command

文件：`Commands/WallAnalyzerCommand.cs`

```csharp
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace <项目名称>.Commands;

[Transaction(TransactionMode.Manual)]
public class WallAnalyzerCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        var view = Host.GetService<Views.WallAnalyzerView>();
        view.ShowDialog();
        return Result.Succeeded;
    }
}
```

**规则：**
- 必须 `[Transaction(TransactionMode.Manual)]`
- 通过 `Host.GetService<T>()` 从 DI 获取 View
- `ShowDialog()` 显示模态窗口

### E. 注册到 DI 容器

在 `Host.cs` 的注释 `【4】` 处添加：

```csharp
//【4】添加服务如View,ViewModel,Service
builder.Services.AddTransient<ViewModels.WallAnalyzerViewModel>();
builder.Services.AddTransient<Views.WallAnalyzerView>();
```

**规则：**
- View / ViewModel 用 `AddTransient`（每次新实例）
- 有状态服务用 `AddSingleton`
- `UIApplication` 已注册为 Singleton

### F. 添加 Ribbon 按钮

在 `Application.cs` 的 `CreateRibbon` 方法中添加：

```csharp
panel.AddPushButton<WallAnalyzerCommand>(button =>
{
    button.LargeImage = new BitmapImage(
        new Uri("pack://application:,,,/<项目名称>;component/Resources/Icons/wall-analyzer.png"));
    button.ToolTip = "墙体分析器";
    button.Title = "墙体分析";
});
```

**规则：**
- 图标放 `Resources/Icons/`，Build Action = `Resource`
- Pack URI：`pack://application:,,,/<程序集名>;component/<路径>`
- 使用 `Tuna.Revit.Extensions` API

## 日志

```csharp
var logger = Host.GetService<ILogger<YourClass>>();
logger.LogInformation("消息 {Parameter}", value);
```

日志位置：`<插件DLL目录>/Logs/<项目名称>.log`（按天滚动）。

## 文件修改速查表

| 需要做什么 | 修改哪些文件 |
|---|---|
| 添加新功能 | Model + ViewModel + View + Command + `Host.cs` + `Application.cs` |
| 添加服务 | `Services/` + `Services/Interfaces/` + `Host.cs` |
| 添加样式 | `Resources/Styles/` + View 引用或合并资源字典 |
| 添加图标 | `Resources/Icons/`（Build Action = Resource） |
| 修改日志 | `appsettings.json` + `Host.cs` |
| 添加 NuGet 包 | `<项目名称>.csproj` |
| 添加配置项 | `appsettings.json` + Options 类 + `Host.cs` 注册 |

## 构建问题排查

- **找不到属性** → `dotnet clean && dotnet build --configuration Debug_R26`（源码生成器缓存问题）
- **构建配置错误** → 只能用 `Debug_R26` / `Release_R26`
- **平台错误** → 必须 x64，Revit 为 64 位进程
