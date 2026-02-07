# Revit 2026 API - 核心开发模式

Revit 插件开发中最常用的 API 模式速查。所有代码基于 Revit 2026 API (RevitAPI.dll v26.0.4.0)。

## 1. ExternalCommand 入口

最基本的插件入口点，每次按钮点击触发一次。

```csharp
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

[Transaction(TransactionMode.Manual)]
public class MyCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        UIApplication uiApp = commandData.Application;
        UIDocument uiDoc = uiApp.ActiveUIDocument;
        Document doc = uiDoc.Document;

        // 业务逻辑...

        return Result.Succeeded;
    }
}
```

**关键点**:
- `TransactionMode.Manual` → 需要手动管理事务
- `TransactionMode.ReadOnly` → 只读操作，无需事务
- 返回 `Result.Failed` 时设置 `message` 参数用于错误提示

## 2. ExternalApplication 入口

应用级入口，Revit 启动时加载一次，用于注册 Ribbon UI。

```csharp
public class MyApp : IExternalApplication
{
    public Result OnStartup(UIControlledApplication application)
    {
        // 创建 Ribbon Tab 和按钮
        application.CreateRibbonTab("MyTab");
        var panel = application.CreateRibbonPanel("MyTab", "MyPanel");

        var buttonData = new PushButtonData("cmdId", "按钮名",
            Assembly.GetExecutingAssembly().Location,
            "Namespace.MyCommand");  // IExternalCommand 的全限定名

        panel.AddItem(buttonData);
        return Result.Succeeded;
    }

    public Result OnShutdown(UIControlledApplication application)
    {
        return Result.Succeeded;
    }
}
```

## 3. Transaction 事务管理

所有修改 Revit 模型的操作必须在事务内执行。

```csharp
// 基本事务
using (Transaction tx = new Transaction(doc, "操作描述"))
{
    tx.Start();
    // 修改操作...
    tx.Commit();
}

// 事务组（多步撤销合并为一步）
using (TransactionGroup tg = new TransactionGroup(doc, "组描述"))
{
    tg.Start();

    using (Transaction tx1 = new Transaction(doc, "步骤1"))
    {
        tx1.Start();
        // ...
        tx1.Commit();
    }

    using (Transaction tx2 = new Transaction(doc, "步骤2"))
    {
        tx2.Start();
        // ...
        tx2.Commit();
    }

    tg.Assimilate(); // 合并为单次撤销
}

// SubTransaction（不创建撤销记录）
using (Transaction tx = new Transaction(doc, "主事务"))
{
    tx.Start();

    using (SubTransaction st = new SubTransaction(doc))
    {
        st.Start();
        // 临时修改...
        st.RollBack(); // 或 st.Commit()
    }

    tx.Commit();
}
```

## 4. FilteredElementCollector 元素查询

查询模型中元素的核心 API，支持链式过滤。

```csharp
// 查询所有墙
var walls = new FilteredElementCollector(doc)
    .OfClass(typeof(Wall))
    .ToElements();

// 查询特定类别的族实例
var doors = new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Doors)
    .OfClass(typeof(FamilyInstance))
    .ToElements();

// 在指定视图中查询
var viewElements = new FilteredElementCollector(doc, viewId)
    .OfCategory(BuiltInCategory.OST_Walls)
    .WhereElementIsNotElementType()
    .ToElements();

// 查询类型（非实例）
var wallTypes = new FilteredElementCollector(doc)
    .OfClass(typeof(WallType))
    .Cast<WallType>()
    .ToList();

// 组合过滤器（AND）
var filter = new LogicalAndFilter(
    new ElementCategoryFilter(BuiltInCategory.OST_Walls),
    new ElementIsElementTypeFilter(true) // true = 非类型
);
var result = new FilteredElementCollector(doc)
    .WherePasses(filter)
    .ToElements();

// 参数过滤
var paramFilter = new ElementParameterFilter(
    ParameterFilterRuleFactory.CreateEqualsRule(
        new ElementId(BuiltInParameter.WALL_BASE_CONSTRAINT),
        levelId));
var filteredWalls = new FilteredElementCollector(doc)
    .OfClass(typeof(Wall))
    .WherePasses(paramFilter)
    .ToElements();
```

**性能要点**:
- `OfClass` 和 `OfCategory` 是快速过滤器，优先使用
- `WhereElementIsNotElementType()` 排除类型定义
- 尽量用 `FirstElement()` 或 `FirstElementId()` 避免全量遍历
- 使用 `ElementQuickFilter`（如 `BoundingBoxIntersectsFilter`）优于 `ElementSlowFilter`

## 5. Parameter 参数读写

```csharp
// 按 BuiltInParameter 读取
Parameter p = wall.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET);
double offset = p.AsDouble(); // 内部单位（英尺）

// 按名称读取（共享参数或项目参数）
Parameter nameParam = element.LookupParameter("参数名");

// 按 GUID 读取共享参数
Parameter sharedParam = element.get_Parameter(new Guid("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"));

// 写入参数（需在事务内）
p.Set(1.5); // 设置为 1.5 英尺

// 类型参数 vs 实例参数
ElementId typeId = element.GetTypeId();
ElementType elemType = doc.GetElement(typeId) as ElementType;
Parameter typeParam = elemType.get_Parameter(BuiltInParameter.ALL_MODEL_DESCRIPTION);

// 单位转换（Revit 2026 使用 ForgeTypeId）
double meters = UnitUtils.ConvertFromInternalUnits(feetValue, UnitTypeId.Meters);
double feet = UnitUtils.ConvertToInternalUnits(meterValue, UnitTypeId.Meters);
```

## 6. Element 创建

```csharp
// 创建墙
Wall wall = Wall.Create(doc, curve, wallTypeId, levelId, height, offset, false, false);

// 创建楼板（通过 CurveLoop）
var curveLoop = new CurveLoop();
curveLoop.Append(Line.CreateBound(p1, p2));
curveLoop.Append(Line.CreateBound(p2, p3));
curveLoop.Append(Line.CreateBound(p3, p4));
curveLoop.Append(Line.CreateBound(p4, p1));
Floor floor = Floor.Create(doc, new List<CurveLoop> { curveLoop }, floorTypeId, levelId);

// 放置族实例
FamilyInstance inst = doc.Create.NewFamilyInstance(
    location,          // XYZ 点
    familySymbol,      // FamilySymbol（需先 Activate）
    level,             // Level
    StructuralType.NonStructural);

// 激活 FamilySymbol（首次放置前必须）
if (!familySymbol.IsActive)
    familySymbol.Activate();
```

## 7. Selection 用户交互

```csharp
UIDocument uiDoc = commandData.Application.ActiveUIDocument;

// 选择单个元素
Reference picked = uiDoc.Selection.PickObject(ObjectType.Element, "请选择元素");
Element elem = doc.GetElement(picked);

// 选择多个元素
IList<Reference> refs = uiDoc.Selection.PickObjects(ObjectType.Element, "请选择多个元素");

// 带过滤的选择
IList<Reference> wallRefs = uiDoc.Selection.PickObjects(
    ObjectType.Element,
    new WallSelectionFilter(),  // 自定义 ISelectionFilter
    "请选择墙");

// 选择点
XYZ point = uiDoc.Selection.PickPoint("请选择一个点");

// 获取当前选择集
ICollection<ElementId> selectedIds = uiDoc.Selection.GetElementIds();

// ISelectionFilter 实现
public class WallSelectionFilter : ISelectionFilter
{
    public bool AllowElement(Element elem) => elem is Wall;
    public bool AllowReference(Reference reference, XYZ position) => false;
}
```

## 8. Events 事件订阅

```csharp
// 在 IExternalApplication.OnStartup 中注册
public Result OnStartup(UIControlledApplication app)
{
    // DB 级事件
    app.ControlledApplication.DocumentOpened += OnDocumentOpened;
    app.ControlledApplication.DocumentChanged += OnDocumentChanged;

    // UI 级事件
    app.ViewActivated += OnViewActivated;
    app.Idling += OnIdling;

    return Result.Succeeded;
}

private void OnDocumentChanged(object sender, DocumentChangedEventArgs e)
{
    Document doc = e.GetDocument();
    ICollection<ElementId> added = e.GetAddedElementIds();
    ICollection<ElementId> deleted = e.GetDeletedElementIds();
    ICollection<ElementId> modified = e.GetModifiedElementIds();
}

// 在 OnShutdown 中取消注册
public Result OnShutdown(UIControlledApplication app)
{
    app.ControlledApplication.DocumentOpened -= OnDocumentOpened;
    return Result.Succeeded;
}
```

## 9. Geometry 几何操作

```csharp
// 获取元素几何
Options geoOptions = new Options
{
    ComputeReferences = true,
    DetailLevel = ViewDetailLevel.Fine,
    IncludeNonVisibleObjects = false
};
GeometryElement geoElem = element.get_Geometry(geoOptions);

// 遍历几何
foreach (GeometryObject geoObj in geoElem)
{
    if (geoObj is Solid solid && solid.Volume > 0)
    {
        foreach (Face face in solid.Faces)
        {
            // 处理面...
            double area = face.Area;
        }
        foreach (Edge edge in solid.Edges)
        {
            Curve curve = edge.AsCurve();
        }
    }
    else if (geoObj is GeometryInstance geoInst)
    {
        // 族实例 → 需要递归获取
        GeometryElement instGeo = geoInst.GetInstanceGeometry();
    }
}

// 创建几何
XYZ p1 = new XYZ(0, 0, 0);
XYZ p2 = new XYZ(10, 0, 0);
Line line = Line.CreateBound(p1, p2);
Arc arc = Arc.Create(p1, p2, midPoint);

// BoundingBox
BoundingBoxXYZ bb = element.get_BoundingBox(null);
XYZ min = bb.Min;
XYZ max = bb.Max;
```

## 10. ExtensibleStorage 扩展存储

在元素上存储自定义数据（不影响模型）。

```csharp
// 定义 Schema
Guid schemaGuid = new Guid("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx");
SchemaBuilder sb = new SchemaBuilder(schemaGuid);
sb.SetSchemaName("MyData");
sb.SetReadAccessLevel(AccessLevel.Public);
sb.SetWriteAccessLevel(AccessLevel.Vendor);
sb.SetVendorId("YOUR_VENDOR_ID");

FieldBuilder fb = sb.AddSimpleField("Value", typeof(string));
fb.SetDocumentation("存储的数据");

Schema schema = sb.Finish();

// 写入
Entity entity = new Entity(schema);
entity.Set<string>("Value", "hello");
element.SetEntity(entity);

// 读取
Entity readEntity = element.GetEntity(schema);
if (readEntity.IsValid())
{
    string value = readEntity.Get<string>("Value");
}
```

## 11. .addin 注册文件

```xml
<?xml version="1.0" encoding="utf-8"?>
<RevitAddIns>
  <!-- ExternalCommand -->
  <AddIn Type="Command">
    <Assembly>path\to\MyPlugin.dll</Assembly>
    <FullClassName>Namespace.MyCommand</FullClassName>
    <ClientId>GUID-HERE</ClientId>
    <Text>命令名称</Text>
    <VendorId>YOUR_VENDOR</VendorId>
  </AddIn>

  <!-- ExternalApplication -->
  <AddIn Type="Application">
    <Assembly>path\to\MyPlugin.dll</Assembly>
    <FullClassName>Namespace.MyApp</FullClassName>
    <ClientId>GUID-HERE</ClientId>
    <Name>应用名称</Name>
    <VendorId>YOUR_VENDOR</VendorId>
  </AddIn>
</RevitAddIns>
```

**Addins 目录**: `C:\ProgramData\Autodesk\Revit\Addins\2026\`
