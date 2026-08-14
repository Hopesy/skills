---
name: harness-init
description: Agent-first 项目模板初始化与协作引导。仅当用户明确要使用 harness-init 模板创建新项目、初始化项目骨架、搭建仓库模板、从零开始一个 harness-init 项目时，使用此 skill 的初始化模式；当 Agent 进入一个已有 harness-init 结构的仓库，需要遵循协作约定、记录变更历史、创建执行计划、做代码改动时，使用此 skill 的协作模式。覆盖场景包括但不限于：harness-init 新建项目、harness-init 项目脚手架、仓库模板、Agent 协作流程、文档同步、执行计划、变更记录。不要因为用户泛泛地说「帮我建个项目」「开始一个新东西」就触发；普通项目、普通脚手架、与 harness-init 无关的仓库都不要使用此 skill。
license: MIT
metadata:
  author: hopesy
  version: "1.0.0"
---

# harness-init

面向 Agent 协作开发的极简仓库模板。人定方向，Agent 执行。规则、知识、变更记录全部版本化。

模板本身不带脚本和 Makefile —— 这是 AI 协作模板，所有文件由 Agent 按指引创建。

## 两种模式

- 用户明确提到 `harness-init`、`harness` 模板，或要求按这个模板创建项目 → **初始化模式**
- 当前仓库已经是 `harness-init` 结构 → **协作模式**
- 普通"创建项目""初始化仓库""搭骨架"，不要触发；按普通项目处理

---

## 初始化模式

从零创建 Agent-first 项目骨架。

### 第一步：确认基本信息

向用户确认：

1. 项目名称（必须）
2. 项目类型（必须，例如：Web/API、前后端分离、桌面端、CLI/工具、库/SDK）
3. 是否需要前端界面或其他专项约束

### 第二步：创建目录结构

```text
<project>/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── CODEOWNERS
├── LICENSE
├── .editorconfig
├── .gitattributes
├── .gitignore
├── .markdownlint.json
└── docs/
    ├── ARCHITECTURE.md
    ├── HISTORY_GUIDE.md
    ├── PLANS_GUIDE.md
    ├── REPO_COLLAB_GUIDE.md
    ├── exec-plans/
    │   ├── README.md
    │   ├── tech-debt-tracker.md
    │   ├── active/        # 空目录，放 .gitkeep
    │   ├── completed/     # 空目录，放 .gitkeep
    │   └── templates/
    │       └── execution-plan.md
    └── histories/
        └── template.md
```

仅 4 份"灵魂"文档 + ARCHITECTURE 守架构。其他专题文档（SECURITY、RELIABILITY、CICD、FRONTEND 等）等真实项目落地后再按需新增，不在初始化时铺占位。

### 第三步：按项目类型实例化关键文档

不要只做模板名替换。必须把这些文档改成项目专属内容：

- `README.md`：真实项目简介、启动方式、目录结构
- `AGENTS.md`：保留导航角色，明确本项目最关键的 plan / history 约束
- `docs/ARCHITECTURE.md`：真实模块边界、运行拓扑、数据流

按需新增（不在默认骨架里，落地后再加）：

- **Web / API / 后端服务** → `docs/RELIABILITY.md`、`docs/SECURITY.md`、`docs/CICD.md`
- **前后端分离 / 含前端** → `docs/FRONTEND.md`、`docs/RELIABILITY.md`、`docs/CICD.md`
- **桌面端 / 客户端** → `docs/DESIGN.md`、`docs/RELIABILITY.md`、`docs/SECURITY.md`
- **CLI / SDK / 库** → `docs/DESIGN.md`、`docs/CICD.md`

如果项目类型还不明确，不要假装初始化完成；先把项目类型补齐，再决定要不要加这些文档。

### 第四步：生成文件内容

读取 `references/init-files.md` 获取每个文件的完整内容。生成时注意：

- 将 `{{PROJECT}}` 替换为项目名
- 所有文档使用中文
- 换行符 LF
- `.editorconfig`：UTF-8、2 空格缩进
- 第三步判定要实例化的文档，必须写成项目专属内容，不留模板占位
- `references/init-files.md` 只提供默认瘦身骨架的完整内容；按项目类型新增的可选专题文档需要基于真实项目事实新写，不要假装模板里已经有完整内容

### 第五步：手工核对骨架

对照第二步的结构清单，确认：

- 4 份灵魂文档（AGENTS.md + REPO_COLLAB_GUIDE.md + HISTORY_GUIDE.md + PLANS_GUIDE.md）齐全
- ARCHITECTURE.md 已实例化为项目内容
- `docs/exec-plans/` 下 3 个子目录就位
- `docs/histories/template.md` 存在
- 基础设施文件（.gitignore、.editorconfig 等）齐全

### 第六步：提示用户下一步

1. 确认 README、AGENTS、ARCHITECTURE 三份已实例化
2. 替换 `CODEOWNERS` 中的占位团队名
3. 按需创建 `apps/`、`packages/`、`infra/` 放真实代码
4. 真实业务接入后，再按项目类型补 `docs/SECURITY.md` 等专题文档

---

## 协作模式

在已有 harness-init 结构的仓库中工作时遵循的约定。

### 每轮任务开始必读

按顺序阅读，建立上下文：

1. `AGENTS.md` — 导航入口（只做路由，不含规则）
2. `docs/REPO_COLLAB_GUIDE.md` — 协作约定
3. `docs/ARCHITECTURE.md` — 架构总览

### 代码改完前必读

`docs/HISTORY_GUIDE.md` — 什么时候记 history、怎么命名、怎么脱敏

### 按任务需要选读

| 场景 | 文档 |
| --- | --- |
| 复杂多步任务 | `docs/PLANS_GUIDE.md` |
| 项目自身扩展的专题文档 | 看 `docs/` 下当时存在的文件 |

### 核心工作规则

1. **知识落仓库**：重要信息只存在聊天记录和脑子里等于不存在
2. **文档同步更新**：行为变化时，代码、文档、history 在同一轮更新
3. **优先简单方案**：选择简单、清晰、可观测的方案，不堆复杂度
4. **Agent 反复失败时**：优先修环境、修指引、修规范，不要只靠 prompt
5. **AGENTS.md 只做路由**：不堆规则，docs/ 才是知识来源
6. **不依赖脚本**：模板不带 Makefile/scripts，所有文件由 Agent 按指引创建

### 复杂任务：创建执行计划

触发条件（满足任一）：

- 任务跨多个 commit 或工作轮次
- 涉及架构、协议、数据迁移等高风险变更
- 需要分阶段验证、回滚策略或决策审计
- 多人或多 Agent 协作

操作流程：

1. 复制 `docs/exec-plans/templates/execution-plan.md`
2. 命名为 `docs/exec-plans/active/YYYY-MM-DD-<slug>.md`
3. 完成后移到 `docs/exec-plans/completed/`

读取 `references/conventions.md` 了解执行计划详细格式。

### 仓库改完：记录变更历史

每次完成有实质性仓库变更的任务都要记录：

1. 复制 `docs/histories/template.md`
2. 创建目录 `docs/histories/YYYY-MM/`（如不存在）
3. 命名为 `YYYYMMDD-HHmm-<task-slug>.md`

内容包括：用户请求（脱敏后）、主要代码/文档变更、设计意图、关键受影响文件。

**不需要记录**的场景：纯问答/研究任务（仓库内容没有实际变化）。

### 提交前确认

- [ ] 文档已同步更新
- [ ] 变更历史已记录
- [ ] 示例和说明文档与当前实现一致

---

## 参考文件

- `references/init-files.md` — 初始化模式所需的全部文件内容
- `references/conventions.md` — 协作模式的详细约定、模板和工作流程
