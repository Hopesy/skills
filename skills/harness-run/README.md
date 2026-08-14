# harness-run 使用说明

`harness-run` 用于长时间、可恢复、可持续推进的 Codex 任务。用户不需要设计完整参数，只需要说清楚目标；范围、执行计划、验证方式和停止条件由 Codex 根据项目证据推断。

## 最简单用法

在 Codex 里直接说：

```text
使用 $harness-run 持续执行：
目标：将这个项目翻译成另一种语言
```

Codex 应该自己完成这些动作：

- 读取当前仓库、`AGENTS.md`、README、源码结构、构建配置和已有计划
- 推导执行范围、阶段计划、验证方式和证据清单
- 启动持久化运行
- 初始化 `.harness-run/docs/` 下的架构快照、运行计划、约束、验证、进度、决策和交接文档
- 每轮只做一个可验证切片
- 将进展写入 `.harness-run/`
- 遇到真实 blocker 时停为 `needs_human`

## 指定项目目录

如果当前 Codex 不在目标项目目录，可以直接写：

```text
使用 $harness-run 在 C:\Users\zhouh\Desktop\CodexPotter 持续执行：
目标：修复 resume 模式和 fresh interactive session 的 live iteration 行为不一致问题
```

等价手动命令：

```powershell
python <skill-root>\scripts\harness_run_ctl.py run-task --repo C:\Users\<you>\Desktop\CodexPotter --goal "修复 resume 模式和 fresh interactive session 的 live iteration 行为不一致问题"
```

## 验证命令可选

多数任务没有一开始就清晰的验证条件，例如“把项目翻译成另一种语言”“迁移架构”“按计划完成重构”。这种情况下只给目标即可：

```text
使用 $harness-run 持续执行：
目标：将当前项目从 Python 翻译成 Rust
```

没有 `verify` 时，`harness-run` 会自动使用：

- `metric`: `planned work checklist`
- `direction`: `complete`
- `stop_condition`: `complete`
- `verify`: `manual evidence and completion checklist`
- `iterations`: 后台模式默认最多 25 轮，避免形式化记录但没有实质进展的空转

含义是：Codex 必须先推导或读取执行计划，再用具体证据证明计划完成。partial 轮次必须用 `refine` / `search` / `pivot` 记录 `incomplete`，只有计划全部满足并写入 completion evidence 时，才能用 `keep` 记录 `complete`。

如果验证命令很明确，可以补上：

```text
使用 $harness-run 持续执行：
目标：修复 TUI snapshot 测试失败
验证命令：cargo test -p codex-tui
```

等价手动命令：

```powershell
python <skill-root>\scripts\harness_run_ctl.py run-task --repo C:\Users\<you>\Desktop\CodexPotter --goal "修复 TUI snapshot 测试失败" --verify "cargo test -p codex-tui"
```

## 按指定计划执行

如果用户明确说按照某个计划文件或目录执行，Codex 必须读取并遵守该计划，不再重新讨论范围或验证条件。

示例：

```text
使用 $harness-run 按 docs/plans/translation 执行：
目标：将当前项目翻译成 Rust
```

Codex 应该：

- 先读取 `docs/plans/translation`
- 将该计划作为权威执行顺序
- 只在计划和真实代码、项目指令、可执行证据冲突时停止说明
- 不再追问“范围是什么”“验证条件是什么”

## 前台模式

前台模式不启动后台 controller，只在当前 Codex 会话中准备持久化状态。适合用户盯着当前会话持续推进。

```text
使用 $harness-run 前台模式执行：
目标：整理项目架构并补齐文档
```

等价手动命令：

```powershell
python <skill-root>\scripts\harness_run_ctl.py run-task --foreground --repo C:\Users\<you>\Desktop\CodexPotter --goal "整理项目架构并补齐文档"
```

## 查看状态

在 Codex 里说：

```text
查看 harness-run 状态
```

等价手动命令：

```powershell
python <skill-root>\scripts\harness_run_ctl.py status --repo C:\Users\<you>\Desktop\CodexPotter
```

状态会显示：

- 当前目标
- scope
- verify 或证据清单模式
- 当前 metric
- 当前轮次
- 最近状态
- runtime/state/log 路径
- `.harness-run/docs/`、运行计划和交接文档路径
- 下一步建议

## 停止运行

在 Codex 里说：

```text
停止 harness-run
```

等价手动命令：

```powershell
python <skill-root>\scripts\harness_run_ctl.py stop --repo C:\Users\<you>\Desktop\CodexPotter
```

停止不会删除 `.harness-run/`。后续仍可查看状态、日志和历史记录。

## 电脑重启后手动继续

`harness-run` 不做开机自启动。电脑重启后，手动打开 Codex，然后说：

```text
使用 $harness-run 继续上次任务
```

或者重新给同一个目标：

```text
使用 $harness-run 持续执行：
目标：将这个项目翻译成另一种语言
```

Codex 应该读取项目里的持久化文件继续：

```text
.harness-run/launch.json
.harness-run/state.json
.harness-run/rounds.tsv
.harness-run/runtime.log
.harness-run/docs/handoff.md
.harness-run/docs/run-plan.md
.harness-run/docs/constraints.md
```

## 持久化文件

运行后目标项目下会出现：

```text
.harness-run/
  launch.json
  state.json
  rounds.tsv
  runtime.json
  runtime.log
  context.json
  docs/
  evidence/
  generated/
  design/
```

用户一般不需要手动编辑这些文件。Codex 用它们恢复上下文、判断下一轮、记录证据和定位 blocker。

## 权限与监督器

默认后台启动使用 `workspace_write` 策略，不会自动给嵌套 `codex exec` 注入 dangerous bypass 参数。只有在用户明确接受无沙箱风险并传入 `--execution-policy danger_full_access` 时，才会使用 `--dangerously-bypass-approvals-and-sandbox`。

每个记录过的轮次都必须更新 `handoff.md`，并至少更新一项 progress、decision、plan、change inventory、completion 或 evidence artifact。后台 controller 会检查这些文件的修改时间；如果 Codex 只写了 `state.json` / `rounds.tsv` 而没有留下可读交接和证据，会停为 `needs_human`。

如果重新运行同一个 goal/scope/verify 但改变了 `iterations`、`guard`、`stop_condition`、`execution_policy` 或 `codex_args` 等行为字段，`harness-run` 不会静默复用旧 launch，而是返回 contract mismatch，要求显式结束旧任务或 `--force` 归档后重开。

## 协作留痕文档

`harness-run` 是独立 skill，不要求目标项目本身已经有 `docs/`。每次运行都会在目标项目本地创建一套轻量协作文档：

```text
.harness-run/docs/
  project-architecture.md
  product-context.md
  run-plan.md
  constraints.md
  change-inventory.md
  validation-pipeline.md
  operability.md
  security-boundary.md
  dependency-and-artifacts.md
  references.md
  generated-index.md
  progress.md
  decisions.md
  design-index.md
  handoff.md
  completion.md
  release-impact.md
  sync-policy.md
  quality-notes.md
  ui-validation.md
```

这些文档的定位：

- `project-architecture.md`：本次运行的证据型架构快照，不替代目标项目正式架构文档。
- `run-plan.md`：本次持续运行的目标、范围、里程碑、验证方式和停止条件。
- `constraints.md`：用户约束、仓库指令、编辑边界、验证要求和安全规则。
- `validation-pipeline.md`：当前项目可用的本地/CI 验证入口。
- `handoff.md`：每轮都要更新的新会话接手入口。
- `completion.md`：任务完成后的结果、验证和剩余风险。
- `sync-policy.md`：哪些内容只留在 `.harness-run/`，哪些可以摘要同步到目标项目自己的 `docs/`。

如果目标项目已经有 `docs/exec-plans`、`docs/histories`、`docs/releases` 等结构，`.harness-run/docs/` 仍然是运行层；完成时只把可评审、脱敏后的摘要同步到目标项目正式文档。

## 持续运行边界

`harness-run` 能保证的是：只要电脑还在、Python controller 没被系统杀掉，它会持续 relaunch Codex 并从 `.harness-run/` 恢复上下文。默认后台运行最多 25 轮；如果达到轮次上限、连续停滞、缺少轮次留痕、controller 进程死亡或 Codex CLI 不可用，会停到可检查的状态，而不是继续无约束空转。

它不会自动处理：

- Windows 重启后的自动恢复
- 用户注销后的自动恢复
- Python 进程被系统或安全软件杀掉后的自动恢复
- Codex CLI 自身不可用

当前设计要求电脑重启后手动继续，不需要安装 Task Scheduler 或系统服务。

## 用户只需要记住

```text
使用 $harness-run 持续执行：
目标：……
```

```text
查看 harness-run 状态
```

```text
停止 harness-run
```
