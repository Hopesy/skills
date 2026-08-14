# 协作约定参考

本文件是协作模式的详细参考，包含模板、工作流程和约定的完整内容。

模板不带脚本和 Makefile —— 所有文件由 Agent 按指引创建。

---

## 执行计划模板

当复杂任务需要创建执行计划时，使用以下模板（也存放在 `docs/exec-plans/templates/execution-plan.md`）：

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

### 执行计划生命周期

1. **创建**：复制 `docs/exec-plans/templates/execution-plan.md` 到 `docs/exec-plans/active/YYYY-MM-DD-<slug>.md`
2. **推进**：在计划中更新进度和决策记录
3. **完成**：将文件从 `active/` 移到 `completed/`
4. **遗留债务**：记到 `docs/exec-plans/tech-debt-tracker.md`

### 什么时候需要执行计划

- 任务跨多个 commit 或多轮工作
- 涉及架构、协议、数据迁移等高风险变更
- 需要分阶段验证、回滚策略或决策审计
- 多人或多 Agent 协作

---

## 变更历史模板

每次完成有实质性代码变更的任务，使用以下模板（也存放在 `docs/histories/template.md`）：

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

### 变更历史规则

- 目录：`docs/histories/YYYY-MM/`（按月分目录，月目录不存在就直接 mkdir）
- 文件名：`YYYYMMDD-HHmm-task-slug.md`
- 创建方式：直接复制 `docs/histories/template.md` 改名，不依赖任何脚本
- 同一个任务跨多轮推进时，继续维护同一个 history
- 脱敏：不含敏感信息、本地路径、密钥、原始日志
- 纯问答/研究不需要记，除非改了仓库内容

---

## PR / 提交检查清单

提交前确认：

1. 文档已同步更新（行为变了对应文档就要改）
2. 如有代码或流程变更，history 已记录
3. 示例和说明文档与当前实现一致
4. 复杂或高风险改动，对应的 execution plan 已更新

### PR 描述建议

```markdown
## 变更摘要

- 改了什么？
- 为什么现在做？

## 验证情况

- [ ] 已完成相关测试或手工验证
- [ ] 行为变化时，文档已经同步更新
- [ ] 代码或流程变更时，history 已补齐或更新

## 关联上下文

- Execution plan：
- History entry：
- 后续技术债：
```

---

## 技术债追踪

文件：`docs/exec-plans/tech-debt-tracker.md`

```markdown
| 日期 | 区域 | 债务描述 | 为什么会存在 | 计划中的后续动作 |
| --- | --- | --- | --- | --- |
```

记录那些暂时不阻塞当前任务但值得留档的技术债。

---

## 文件创建工作流（无脚本版）

模板瘦身后没有自动化脚本。每次需要新建文件，都按以下流程：

### 新建 execution plan

1. 读 `docs/exec-plans/templates/execution-plan.md` 拿到模板
2. 写到 `docs/exec-plans/active/YYYY-MM-DD-<plan-slug>.md`
3. 把目标、范围、风险等字段按当前任务填好
4. plan 完成后，把文件从 `active/` 移到 `completed/`

### 新建 history

1. 读 `docs/histories/template.md` 拿到模板
2. 检查 `docs/histories/YYYY-MM/` 是否存在；不存在就创建
3. 写到 `docs/histories/YYYY-MM/YYYYMMDD-HHmm-<task-slug>.md`
4. 按模板填用户请求、变更概览、设计意图、受影响文件

### 新建项目（初始化模式）

1. 读 `references/init-files.md` 拿全部模板内容
2. 按目录结构逐个创建文件
3. 把 `{{PROJECT}}`、`{{YEAR}}`、`{{AUTHOR}}` 等占位替换成真实值
4. 关键文档（README、AGENTS、ARCHITECTURE）按项目类型实例化，不留占位语句

---

## 核心理念速查

1. 人定方向，Agent 执行
2. 仓库可追溯知识 > 私有上下文
3. Agent 反复失败 → 修指引、修规范，不是加 prompt 压力
4. 短稳定入口文档 > 越来越长的大 prompt
5. 速度重要，但持续整理和收口更重要
6. 这是 AI 协作模板，不依赖脚手架脚本——所有文件由 Agent 按指引创建
