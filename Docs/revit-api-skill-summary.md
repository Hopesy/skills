# RevitAPI Skill 创建总结

## 起点

- **源数据**：Revit 2026 API 的 CHM 解压文件夹，337MB，28,796 个 HTML 文件，30 个命名空间，2,724 个类型
- **目标**：转换为 Claude Code 的渐进式披露 skill，让 Claude 在开发 Revit 插件时能按需检索精确的 API 文档

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 索引粒度 | 类级别（2724 条） | 平衡搜索精度与索引大小 |
| 数据存放 | skill 目录内自包含 | 无外部路径依赖 |
| 披露层级 | 三层 L1/L2/L3 | 匹配 skill 的元数据→正文→资源加载模型 |
| 数据格式 | 按命名空间的 JSON | 替代 29K 个 HTML，压缩 89% |

## 实施过程

### Phase 1：规划

- 探索 .hhc 目录树格式和 HTML 页面结构
- 研究现有 skill（saury-revit、pdf、skill-creator）的格式规范
- 设计三层披露架构 + 脚本分工

### Phase 2：搭建骨架（Step 1-4）

- 创建 `~/.claude/skills/revit-api/` 目录结构
- 复制 RevitAPI 数据到 `data/` 目录
- 编写三个 Python 脚本：
  - `build_index.py` — 解析 .hhc + HTML 元数据，构建 JSON 索引
  - `search_api.py` — 四种搜索模式（关键词/命名空间/类/成员）
  - `extract_page.py` — HTML → Markdown 提取

### Phase 3：构建索引 + 内容（Step 5-7）

- 运行 `build_index.py`：2724 类型，30 命名空间，7.3MB 索引
- 自动生成 `namespace-overview.md`（662 行）
- 手写 `core-patterns.md`（11 个核心开发模式 + C# 代码）
- 编写 `SKILL.md`（触发条件 + 查询路径 + 核心速查表）

### Phase 4：瘦身优化

- 删除 CHM 残留文件（#系统文件、$索引、CSS/JS/图标）：-37MB
- 编写 `compact_html.py`，将 29K HTML 预提取为 32 个命名空间 JSON：289MB → 25MB
- 更新 `extract_page.py` 改为从 JSON 读取
- 删除 `html/` 目录和 `RevitAPI.hhc`
- 删除不再需要的构建脚本（`build_index.py`、`compact_html.py`）

## 最终产物

```
~/.claude/skills/revit-api/     37MB（原 337MB，压缩 89%）
├── SKILL.md                    L1: 触发 + 导航 + 速查
├── scripts/
│   ├── search_api.py           L3: 搜索引擎
│   └── extract_page.py         L3: 文档提取
├── references/
│   ├── namespace-overview.md   L2: 命名空间总览
│   └── core-patterns.md        L2: 开发模式速查
└── data/
    ├── api_index.json          类级索引（2724 类型）
    └── pages/                  预提取 JSON（28796 页）
```

## 三层渐进式披露

| 层级 | 内容 | 加载时机 | 载体 |
|------|------|----------|------|
| L1 | 命名空间概览、核心类速查表、使用指引 | skill 触发即显示 | SKILL.md (~100行) |
| L2 | 命名空间详细类列表、开发模式代码 | Claude 按需 Read | references/*.md |
| L3 | 具体类的完整 API（签名、参数、Remarks） | Claude 按需执行脚本 | scripts/ → JSON 解析 |

## 覆盖率验证

- 30/30 命名空间、2724/2724 类型、28796/28796 页面 — **100% 覆盖**
- 五种类型全覆盖：Class(1955)、Enumeration(699)、Interface(67)、Structure(2)、Delegate(1)
- 成员级查询支持：属性(P:13100)、方法(M:8494)、事件(E:116)、字段(F:4) 全部可检索
- `quick_validate.py` 验证通过
