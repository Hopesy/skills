# 初始化文件内容参考

本文件包含瘦身版 harness-init 模板所有文件的完整内容。初始化时按此生成，将 `{{PROJECT}}` 替换为用户的项目名称、`{{YEAR}}` 替换为当前年份、`{{AUTHOR}}` 替换为版权持有者。

模板不再包含 `Makefile`、`scripts/`、`CONTRIBUTING.md`、根目录 `SECURITY.md` —— 这是 AI 协作模板，所有文件由 Agent 按指引创建。

---

## 根目录文件

### AGENTS.md

```markdown
# {{PROJECT}}

面向 Agent 协作开发的基础模板。`AGENTS.md` 只做导航，`docs/` 是知识的正式来源。

如果一次变更会让某份文档过期，就在同一轮任务里顺手改掉。

## 两条铁律

- **复杂任务先落 execution plan**：跨轮次、跨提交、风险偏高或需要阶段性验证 → 先读 `docs/PLANS_GUIDE.md`，把 plan 落到 `docs/exec-plans/`。
- **实质变更必须补 history**：仓库内容发生真实修改 → 同一轮写进 `docs/histories/`。

## 每轮开始先读

- `docs/REPO_COLLAB_GUIDE.md`：协作、提交、文档同步约定。
- `docs/ARCHITECTURE.md`：仓库整体结构和预期边界。

## 代码改完前要读

- `docs/HISTORY_GUIDE.md`：什么时候记 history、怎么命名、怎么脱敏。

## 按需选读

- `docs/PLANS_GUIDE.md`：什么时候要写 execution plan，怎么维护。

## 工作规则

- 优先选择小而清晰、对 Agent 友好的抽象。
- 规则、架构约束版本化落在仓库里。
- 复杂任务先落 execution plan 再推进。
- 完成的代码变更要记到 `docs/histories/`，不要事后补票。
```

### CLAUDE.md

```markdown
<system-reminder>必须先阅读 AGENTS.md。</system-reminder>
```

### README.md

````markdown
# {{PROJECT}}

## 简介

一个面向 Agent 协作开发的项目。

人来定方向，Agent 负责执行和推进——仓库内的规则、知识、变更记录全部版本化，Agent 能直接读懂并遵循。

## 快速开始

```bash
# 补齐真实项目信息
#    - docs/ARCHITECTURE.md  → 填入架构、分层、数据流
#    - 按需新增 apps/、packages/、infra/ 放真实代码
```

## 项目结构

```text
AGENTS.md              # Agent 协作导航入口
CLAUDE.md              # Claude Code 专用指令
docs/
├── ARCHITECTURE.md    # 架构总览
├── REPO_COLLAB_GUIDE.md # 协作约定
├── HISTORY_GUIDE.md   # 变更记录规范
├── PLANS_GUIDE.md     # 执行计划规范
├── exec-plans/        # 执行计划
└── histories/         # 变更历史
```

搭建产品后，预期还会新增：

- `apps/` — 可部署的应用 / 服务
- `packages/` — 跨应用复用的库
- `infra/` — 部署和基础设施定义

## Agent 协作模式

当使用 Claude Code 或其他 Agent 在此仓库工作时：

1. **Agent 先读 `AGENTS.md`** — 导航入口，指向该读哪些文档
2. **按任务类型分层阅读** — 不需要一次读完所有文档
3. **知识落仓库** — 决策、规范、变更记录版本化，不依赖聊天记录
4. **复杂任务先写 plan** — 放 `docs/exec-plans/active/`，完成后挪到 `completed/`
5. **代码改完记 history** — 放 `docs/histories/YYYY-MM/`

## 许可证

[MIT](LICENSE)
````

### CODEOWNERS

```text
* @example-org/example-team
```

### LICENSE

```text
MIT License

Copyright (c) {{YEAR}} {{AUTHOR}}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### .editorconfig

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false
```

### .gitattributes

```text
* text=auto eol=lf

*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.webp binary
*.pdf binary
```

### .gitignore

```text
# OS / Editor
.DS_Store
Thumbs.db
*.swp
*.swo
*~
.idea/
.vscode/
*.code-workspace

# Logs / temp
*.log
tmp/
temp/

# Env
.env
.env.*
!.env.example

# Node
node_modules/
.pnpm-store/
.yarn/
.turbo/
.next/
dist/
build/
coverage/

# Rust / Go / .NET
target/
bin/
obj/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Terraform
.terraform/
*.tfstate
*.tfstate.*

# Cache
.cache/
```

### .markdownlint.json

```json
{
  "default": true,
  "MD013": false,
  "MD033": false,
  "MD041": false
}
```

---

## docs/ 文件

### docs/REPO_COLLAB_GUIDE.md

```markdown
# 仓库协作约定

这份文档定义 Agent-first 仓库的默认协作方式。技术栈相关约束按需新增专题文档，不要往这里堆。

## 开发原则

- 优先选择简单、清晰、可观测的方案，不堆复杂度。
- 以 Agent 可读、可执行为目标组织仓库；重要信息只存在聊天记录和脑子里等于不存在。
- 代码、文档、配置同源更新。
- Agent 在同一类问题上反复失败时，优先修环境、修指引、修规范，不要靠"多试几次 prompt"。
- 修 bug 时顺手检查文档是否该补强，让同类问题只修一次。

## 文档纪律

- `AGENTS.md` 只做路由，不堆规则。
- `docs/` 是仓库级知识的正式来源。
- 行为一旦变化，对应文档在同一次改动里同步更新。
- 与其往大文档里塞内容，不如新增一份边界清楚的小文档。

## Git 与评审

- commit 范围清晰、描述准确。
- 提交前确认文档和 history 已反映最终状态。
- 复杂或高风险改动，先落一份 execution plan 到 `docs/exec-plans/`。
- 评审里引用仓库内文件，不要依赖少数人知道的上下文。

## 验证

- 这是 AI 协作模板，仓库本身没有自动化脚本——验证手段由真实项目落地后再补。
- 实质代码变更要让验证能力比改之前更强；具体怎么验，由当时的项目栈决定。

## 配置卫生

- 示例配置和实际默认值保持一致。
- 启动所需的环境变量和外部依赖写清楚。
- 关键初始化步骤不要只存在 README 的角落里。
```

### docs/ARCHITECTURE.md

```markdown
# 架构总览

这份文档用于描述仓库的顶层结构。下面这些内容是模板占位，等新项目真正落地后，应该尽快替换成真实架构。

## 预期的仓库结构

- `apps/`：可部署的应用、服务或入口。
- `packages/`：跨应用复用的库、契约和共享能力。
- `infra/`：部署、基础设施和环境定义。
- `docs/`：仓库知识库，也是本地规则和上下文的正式来源。

## 边界建议

- 业务逻辑优先沉淀到可复用包里，不要一开始就散落在各个 app 中。
- 基础设施和运行编排要显式版本化，不要藏在手工操作里。
- 避免隐式跨包耦合；一旦仓库成形，就把允许的依赖方向写清楚。
- 只要架构有变化，就同步更新这份文档。

## 新项目需要补齐的内容

- 核心产品面和运行拓扑。
- 包分层与依赖边界。
- 数据流与存储模型。
- 可观测性方案和本地开发模式。
```

### docs/HISTORY_GUIDE.md

```markdown
# 代码变更历史记录规范

`docs/histories/` 用来记录已经完成的代码变更任务。纯问答、调研、分析类任务默认不需要记 history，除非最后确实改了仓库内容。

## 基本要求

- 每个完成的代码变更任务，都应该对应一份 history 文件，或补充到同一任务既有的 history 文件里。
- 用户原始诉求可以适当压缩，但要保留关键信息。
- 不要把敏感信息、本地路径、密钥或原始日志细节直接写进去。
- 同一个任务跨多轮推进时，继续维护同一个 history，不要重复建文件。

## 目录与命名

- 目录：`docs/histories/YYYY-MM/`
- 文件名：`YYYYMMDD-HHmm-task-slug.md`
- 模板：`docs/histories/template.md`

## 应该写什么

- 用户诉求原文，或者压缩后的脱敏版本。
- 本次主要代码与文档改动。
- 设计动机，以及为什么这么做。
- 最关键的受影响文件。
```

### docs/PLANS_GUIDE.md

```markdown
# Execution Plan 使用说明

execution plan 适合用在那些超出单轮聊天上下文、需要多次推进或风险较高的任务上。

## 什么时候该建 plan

- 任务会跨多个 commit 或多轮工作推进。
- 这次改动会影响架构、协议、数据迁移或其他高风险区域。
- 完成任务依赖阶段性验证、回滚策略或关键决策留痕。
- 可能会有多个人或多个 Agent 在一段时间内共同推进。

## 存放位置

- 进行中的 plan 放在 `docs/exec-plans/active/`
- 已完成的 plan 移到 `docs/exec-plans/completed/`
- 复用模板在 `docs/exec-plans/templates/execution-plan.md`
- 暂不处理但值得保留的债务放到 `docs/exec-plans/tech-debt-tracker.md`

## 维护要求

- 写清目标、范围、约束、风险和验证方式。
- 推进过程和关键决定要落在仓库里，不要只存在聊天记录里。
- 状态变化要同步更新。
- 过期 plan 要及时关闭、归档或清理，保证 active 目录可信。
```

### docs/exec-plans/README.md

```markdown
# Execution Plans

这个目录用于存放长期任务的执行计划。

- 进行中的计划放在 `active/`
- 已完成的计划移到 `completed/`
- 新计划从 `templates/execution-plan.md` 开始
- 暂时不做但需要持续跟踪的问题放到 `tech-debt-tracker.md`
```

### docs/exec-plans/tech-debt-tracker.md

```markdown
# 技术债追踪

这里记录那些暂时不阻塞当前任务、但已经值得留档的技术债。

| 日期 | 区域 | 债务描述 | 为什么会存在 | 计划中的后续动作 |
| --- | --- | --- | --- | --- |
```

### docs/exec-plans/templates/execution-plan.md

```markdown
# <执行计划标题>

## 目标

用一段话说明最终想达到的状态。

## 范围

- 包含：
- 不包含：

## 背景

- 相关文档：
- 相关代码路径：
- 已知约束：

## 风险

- 风险：
- 缓解方式：

## 里程碑

1. 调研与方案收敛。
2. 分阶段实现。
3. 验证、交付与收尾。

## 验证方式

- 命令：
- 手工检查：
- 观测检查：

## 进度记录

- [ ] 里程碑 1
- [ ] 里程碑 2
- [ ] 里程碑 3

## 决策记录

- YYYY-MM-DD：做了什么决定，为什么这么做，会带来什么影响。
```

### docs/histories/template.md

```markdown
## [YYYY-MM-DD HH:mm] | Task: <简短的任务动词>

### Execution Context

* **Agent ID**: `如实填写`
* **Base Model**: `如实填写`
* **Runtime**: `如实填写`

### User Query

> {用户Query原文，或者压缩后的脱敏版本}

### Changes Overview

**Scope:** (标注受影响的包)

**Key Actions:**

* **[Action 1]**: 简洁说明改动点
* **[Action 2]**: 简洁说明改动点

### Design Intent (Why)

*简洁直击要点的说明为什么要这么改？*

### Files Modified

* `path/to/file1`
* `path/to/file2`
```

### docs/exec-plans/active/.gitkeep 和 docs/exec-plans/completed/.gitkeep

空文件，仅用于让 git 跟踪空目录。

---

## 按项目类型新增的专题文档

以下文档不在默认骨架里。当真实项目类型确定后，按需新增。

### docs/SECURITY.md（Web/API/桌面端项目可选）

```markdown
# 安全默认约束

把安全默认值讲清楚，避免实现逐步演进时越走越散。

建议维护的内容：

- 认证与授权约束。
- 密钥和环境变量管理方式。
- 依赖治理与供应链安全要求。
- 数据分级、脱敏与保留策略。
- 对外 API、Webhook、文件上传和沙箱执行的规则。
```

### docs/RELIABILITY.md（Web/API/前后端/桌面端项目可选）

```markdown
# 稳定性与可运维性

定义项目的运行质量底线。

建议维护的内容：

- 启动、健康检查和基本可用性要求。
- 日志、指标、链路的采集和访问约定。
- timeout、retry、backoff 的默认策略。
- 本地和 CI 的关键路径验证方式。
- 常见故障、排查路径和恢复步骤。
```

### docs/CICD.md（Web/API/前后端/CLI/SDK 项目可选）

```markdown
# CI/CD 说明

定义本项目的构建、测试、发布流程。

建议维护的内容：

- 构建命令和产物。
- 测试分层（unit / integration / e2e）以及怎么跑。
- 发布渠道、版本策略、回滚路径。
- 远端 CI 的 job 列表和触发条件。
```

### docs/FRONTEND.md（前后端分离/含前端项目可选）

```markdown
# 前端协作说明

仓库里有前端界面时，把这份文档补完整。

建议在这里维护：

- 本地启动、构建和联调方式。
- 浏览器驱动的验收流程。
- 共享组件边界。
- 设计系统、样式变量和 CSS 规范。
- 前端测试策略。
```

### docs/DESIGN.md（桌面端/CLI/SDK 项目可选）

```markdown
# 设计原则

沉淀产品层面相对稳定的设计原则。

建议维护：

- 整体交互目标、命令面或公共 API 边界。
- 关键用户路径或主流程。
- 复用与例外的判定标准。
```

如果项目还需要 product-specs、design-docs、references 等子目录，再按需新建并补 README。不要一上来就铺满空文件夹。
