---
name: revit-api
description: "Revit 2026 API 文档查询与参考。当用户询问 Revit API 类、方法、属性、枚举用法，查找 Revit 开发相关 API，或需要确认 API 签名和参数时触发。覆盖场景：(1) 查询特定类/接口的成员和用法 (2) 搜索实现某功能需要的 API (3) 查看方法签名和参数说明 (4) 了解命名空间结构和继承关系 (5) 确认 Revit API 的正确调用方式。关键词：RevitAPI, Autodesk.Revit, Element, Document, Transaction, FilteredElementCollector, ExternalCommand, ExternalApplication, Wall, Floor, FamilyInstance, FamilySymbol, Parameter, BuiltInParameter, BuiltInCategory, Selection, GeometryElement, Solid, Face, CurveLoop, Level, View, ViewSheet, XYZ, Line, Arc, IExternalCommand, IExternalApplication, UIApplication, UIDocument, Ribbon, PushButton, ExtensibleStorage, SubTransaction, TransactionGroup, ElementId, Reference, TaskDialog。"
license: MIT
metadata:
  author: hopesy
  version: "1.0.0"
---

# Revit 2026 API 参考

基于 RevitAPI.dll v26.0.4.0 的完整 API 文档，覆盖 **30 个命名空间**、**2724 个类型**。

## 查询流程

根据用户问题类型，选择对应的查询路径：

### 路径 A：搜索特定 API（最常用）

用户问"XX 类怎么用"、"如何实现 XX 功能"、"XX 方法的参数"时：

```bash
# 1. 先搜索定位
python scripts/search_api.py search "关键词"

# 2. 查看类的成员概览
python scripts/search_api.py class "Autodesk.Revit.DB.ClassName"

# 3. 需要完整文档时（签名、Remarks、继承链）
python scripts/extract_page.py --type "Autodesk.Revit.DB.ClassName"

# 4. 查看成员级详情（属性/方法签名）
python scripts/extract_page.py --id "P:Autodesk.Revit.DB.Wall.Flipped"
python scripts/extract_page.py --id "M:Autodesk.Revit.DB.Wall.Flip"
```

### 路径 B：浏览命名空间

用户问"XX 命名空间有什么"、"XX 模块的类"时：

```bash
# 列出所有命名空间
python scripts/search_api.py namespaces

# 查看特定命名空间的类型列表
python scripts/search_api.py namespace "Autodesk.Revit.DB"
```

或直接读取 [references/namespace-overview.md](references/namespace-overview.md)。

### 路径 C：查找成员

用户问"哪个类有 XX 方法"、"XX 属性在哪里"时：

```bash
python scripts/search_api.py member "GetParameters"
```

### 路径 D：开发模式速查

用户问"怎么创建墙"、"事务怎么用"、"如何查询元素"等通用开发问题时：

直接读取 [references/core-patterns.md](references/core-patterns.md)，包含 11 个核心模式的 C# 代码示例。

## 核心类速查

| 类 | 命名空间 | 用途 |
|---|---|---|
| `Document` | DB | 当前 Revit 文档，所有操作的入口 |
| `Element` | DB | 所有模型元素的基类 |
| `ElementId` | DB | 元素的唯一标识符 |
| `FilteredElementCollector` | DB | 元素查询/过滤器（必学） |
| `Transaction` | DB | 模型修改的事务管理 |
| `Wall` | DB | 墙体元素 |
| `Floor` | DB | 楼板元素 |
| `FamilyInstance` | DB | 族实例（门窗等） |
| `FamilySymbol` | DB | 族类型定义 |
| `Parameter` | DB | 元素参数读写 |
| `XYZ` | DB | 三维坐标点 |
| `Line` / `Arc` / `CurveLoop` | DB | 几何曲线 |
| `Solid` / `Face` / `Edge` | DB | 几何实体 |
| `Level` | DB | 标高 |
| `View` / `ViewPlan` / `View3D` | DB | 视图 |
| `UIApplication` | UI | UI 层应用对象 |
| `UIDocument` | UI | UI 层文档（选择交互） |
| `ExternalCommandData` | UI | Command 执行上下文 |
| `TaskDialog` | UI | 消息对话框 |
| `Selection` | UI.Selection | 用户选择交互 |

## 命名空间导航

**核心（每天用）**:
- `Autodesk.Revit.DB` — 数据库核心：元素、几何、参数、事务
- `Autodesk.Revit.UI` — 用户界面：Ribbon、对话框、选择
- `Autodesk.Revit.ApplicationServices` — 应用服务：Application、ControlledApplication
- `Autodesk.Revit.Creation` — 工厂方法：创建文档、几何对象
- `Autodesk.Revit.Attributes` — 特性标记：Transaction、Regeneration

**专业领域**:
- `DB.Architecture` — 建筑：房间、楼梯、栏杆
- `DB.Structure` — 结构：梁、柱、基础
- `DB.Mechanical` — 暖通：风管、设备
- `DB.Electrical` — 电气：线路、配电盘
- `DB.Plumbing` — 给排水：管道、卫浴

**高级**:
- `DB.ExtensibleStorage` — 自定义数据存储
- `DB.ExternalService` — 外部服务框架
- `DB.Events` / `UI.Events` — 事件系统
- `DB.DirectContext3D` — 自定义 3D 渲染
- `DB.Visual` — 材质与渲染外观
- `Autodesk.Revit.Exceptions` — 异常类型

## 注意事项

- 所有脚本基于 Python 标准库，无需额外安装依赖
- 脚本路径相对于此 skill 目录，使用 `scripts/` 前缀
- 数据已预提取为按命名空间的 JSON 文件（`data/pages/*.json`），无需原始 HTML
- 索引文件 `data/api_index.json` 由 `build_index.py` 生成
- `extract_page.py` 支持 `--id` 参数直接查询成员级文档（前缀：T=类型, P=属性, M=方法, E=事件）
