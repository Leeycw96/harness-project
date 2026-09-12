# Keel 强模型瘦身设计

> 历史设计记录：当前仅维护 Codex App runtime，部署和验证方式以根目录 README.md 为准。


日期：2026-07-25

## 背景

Keel 当前通过 Skill、Agent 手册、磁盘状态和多阶段 workflow 为模型补充需求澄清、实现、验收、恢复等能力。随着 GPT-5.6 SOL、Kimi K3 等强模型的能力边界扩大，现有大量教程式说明、重复协议和固定 Agent 调度已不再全部必要。

当前仓库同时维护 Codex App 和 Claude Code 两套 runtime。审计结果如下：

- Codex runtime 约 2,818 行，Claude Code runtime 约 2,834 行。
- `keel-dev`、`keel-dev-fast`、`keel-dev-fix` 重复描述初始化、预检、生命周期、进度恢复和 artifact 规则。
- Codex Agent 使用 TOML、角色文档、SOP 三层结构，同一职责存在重复；Claude Code 又维护一份语义等价的合并文档。
- `profile.json` 与 `state.json` 有重复字段，common scripts 中存在没有运行时引用的 helper。
- CallChain 默认 `NOOP`，但 full workflow 当前仍固定调度一个独立 Agent。
- 仓库没有正式测试或 eval，无法直接证明删除阶段后效果不退化。

本设计只保证强模型，不再以较弱模型的独立完成能力为兼容基线。

## 目标

- 在不降低需求边界、实现正确性和独立验收效果的前提下减少 Skill 和 Agent 上下文。
- 删除几乎不使用的独立 post-review fix 能力。
- 保持 full 和 fast workflow 内部的自动修复闭环。
- 建立可重复 eval，为第二期删除或按需执行 workflow 阶段提供证据。
- 保持 Codex App 与 Claude Code 两套 runtime 的行为语义一致。
- 第一阶段保持现有 full/fast 状态机和主要 artifact 契约兼容。

## 非目标

- 不兼容弱模型。
- 第一期不合并 QA 与 CodeReview。
- 第一期不删除 full workflow 的 Scope Review。
- 第一期不修改 XML plan 格式。
- 第一期不合并 `profile.json` 和 `state.json`。
- 本轮不引入 runtime 模板生成系统。
- 不恢复 tmux、pane、CLI 子进程或 Agent 间直接通信。

## 总体方案

采用两期、边界保留式瘦身。

第一期先删除确定无使用价值的独立 fix 能力，再压缩指令、消除重复并建立 eval。第一期不减少 full/fast 的质量门禁和主要 Agent 调用，以便把提示词变化与 workflow 变化分开验证。

第二期基于 eval 数据逐项减少调用和状态协议。每次只改变一个变量，任何质量硬门禁退化都撤销该项。

不采用以下方案：

- 仅压缩文字：风险低，但无法降低 Agent 调度和状态维护成本。
- 一次性合并 QA/CodeReview、删除 Scope Review：节省更大，但失去独立审查视角，无法满足“不影响效果”。

## 第一期架构

### 公开入口

保留：

- `/keel-plan`
- `/keel-dev-fast`
- `/keel-dev`

删除：

- `/keel-dev-fix`

删除的是 full run `DONE` 后再次进入的独立 fix 入口。full/fast workflow 内部由评审失败触发的 `FIX`、`FIX_FAST` 和复审循环继续保留。

### 四层职责

#### 1. 入口 Skill

每个 Skill 只保留：

- 适用条件和硬边界
- 状态转换
- 每个阶段的输入、输出和完成 tag
- 质量门禁和终止条件

删除教程式推理说明、重复示例以及可由强模型从契约直接推导的操作细节。

#### 2. 共享编排契约

将 full/fast 重复的以下内容抽取为共享引用：

- run 初始化
- Preflight
- Agent 调度 prompt 最小字段
- Agent 生命周期
- progress、恢复和重试
- artifact 校验
- git 提交边界
- 完成汇总边界

full 和 fast Skill 只描述各自状态机及差异。

Agent 调度 prompt 统一为：

- 当前阶段
- run 或 profile 绝对路径
- 阶段输入
- 期望输出
- 允许的完成 tag

其余上下文由 Agent 从磁盘契约和项目规范恢复。

#### 3. 单文件 Agent 契约

Codex Agent 的角色文档与 `*-AGENTS.md` 合并为一个 Markdown 文件。TOML 只保留 Agent 注册信息和指向该文档的最小 developer instruction。

每个 Agent 文档只保留：

- 职责及禁止事项
- 通用启动输入
- 各阶段动作
- artifact 最小格式
- 完成 tag
- 质量门禁

Claude Code 已使用单文件 Agent，按相同语义进一步压缩。

#### 4. 项目专用质量规则

保留 `keel-dev-coding-rules.md`。以下要求属于 Keel 的工程政策，不能交给模型自行推断：

- 禁止 stub、fake 和硬编码响应
- 修根因而不是掩盖测试
- TDD 仅覆盖业务域 Service public 方法
- Controller、RPC Provider、MQ Listener、Scheduler 入口层不得承载业务逻辑
- 测试必须有有效断言
- 每个提交保持可构建

## 第一期流程

### Keel Plan

保留流程：

```text
读取项目上下文
  -> 提出会改变 plan 的关键问题
  -> 确认本次范围、依赖和 out-of-scope
  -> 拆分 feature
  -> 定义可测试验收标准
  -> 生成 XML
  -> 校验 XML 和需求一致性
```

强模型不再需要长篇教学、正反例和重复提醒，但以下硬门禁保留：

- 未读上下文不得写 plan。
- 未确认范围不得写 plan。
- 验收标准必须具体可测试。
- XML 必须符合模板结构。
- 需要用户决策的歧义不得自行补全。

### Keel Dev Fast

状态机保持：

```text
PREFLIGHT
  -> BUILD_FAST
  -> CODE_REVIEW_FAST
  -> FIX_FAST（仅阻断时，最多 3 轮）
  -> DONE / PAUSED
```

### Keel Dev Full

状态机保持：

```text
PREFLIGHT
  -> SCOPE_BUILD
  -> SCOPE_REVIEW
  -> BUILD
  -> PARALLEL_REVIEW
  -> FIX（仅阻断时，最多 3 轮）
  -> CALL_CHAIN
  -> DONE / PAUSED
```

### Artifact 职责

- `plan.md`：需求契约。
- `build-scope.md`：需求到当前代码的实现映射。
- `state.json.build.commits`：本轮审查边界。
- `qa-feedback.md`：业务验收证据和业务阻断问题。
- `code-review.md`：正确性、回归、架构、测试和安全问题。
- `fix-brief.md`：Builder 唯一修复输入。
- `call-chain-review.md`：跨迭代业务流程索引的 `UPDATED` 或 `NOOP` 结论。

### DONE 后反馈

删除 post-review fix 后不再恢复历史 run：

- 原需求内问题通过新的 plan/dev run 处理。
- 范围变化或新需求重新运行 `/keel-plan`。
- README 和 full/fast 完成提示不再推荐 `/keel-dev-fix`。

## 删除范围

第一期删除两套 runtime 中的：

- `keel-dev-fix` Skill
- `keel-feedback-triage` Agent
- Codex FeedbackTriage TOML、角色文档和 SOP
- `init_keel_fix_run`
- 仅供 post-review fix 使用的 source-run 查找 helper
- profile/state 中仅供 FeedbackTriage 使用的字段
- README、部署结果和完成提示中的 fix 入口说明

部署 manifest 继续按现有规则删除目标项目中上一版由 Keel 管理、但新版源码已不存在的文件。

## 脚本与状态兼容

第一期保留：

- `profile.json`
- `state.json`
- full/fast artifact 名称
- full/fast phase 名称
- 当前 retry 上限
- `update_progress` 和 `complete_stage`

可以删除没有运行时引用且没有文档化外部契约的 helper。重复 JSON 生成逻辑可以内部重构，但生成的 full/fast profile/state 结构保持兼容。

`profile.json` 和 `state.json` 合并属于第二期实验，不与第一期提示词压缩同时进行。

## Eval 设计

### 方法

使用同一强模型、相同配置、相同任务和相同仓库快照，对改造前后分别运行。考虑模型输出波动，每个场景至少重复 3 次。

结果同时使用：

- 可自动检查的结构、编译、测试和 git diff 指标
- 固定 rubric 的人工或独立模型盲评
- 输入 token、总 token、Agent 调用次数和完成时间

### 场景矩阵

#### Plan

- 需求明确的小型变更
- 存在关键歧义
- 本次范围、交互依赖和 out-of-scope 混杂
- 外部依赖未就绪
- 包含事务、幂等或权限约束

#### Fast

- 小型 bugfix
- 局部输入校验
- 低风险测试补强

#### Full

- 跨模块状态流转
- 事务或幂等
- 数据库 schema 变化
- 外部服务或异步流程

#### Review

在实现中预埋：

- stub 或硬编码响应
- 遗漏关键副作用
- 缺少关键测试
- 入口层业务逻辑
- 事务或并发风险
- 用户无关文件改动

#### CallChain

- 简单查询和同步 CRUD，应为 `NOOP`
- 多入口、异步推进或多阶段状态流转，应为 `UPDATED`

#### Recovery

- Agent 中断
- artifact 缺失或格式错误
- 主代码编译失败
- 测试编译存在允许继续的基线失败

### 不退化硬门禁

- XML 可解析率为 100%。
- Plan 不引入未确认范围。
- 关键验收标准无遗漏，且可执行验证。
- Builder 结果可编译，相关测试通过，不存在 stub。
- 预埋 P0/P1 的发现率不低于改造前。
- QA 和 CodeReview 不审用户已有的无关改动。
- CallChain 正负样本判定不低于改造前。
- 中断后能够从磁盘状态恢复。

### 效率目标

- Skill 输入体积至少降低 40%。
- Agent 必读指令至少降低 30%。
- 每个 runtime 总体规模预计降低 30%–40%。
- 任务成功率和阻断缺陷召回率不降低。

## 错误处理

- Preflight 主代码编译失败继续硬终止。
- 测试编译存在基线失败时继续由用户决定是否允许推进。
- artifact 缺失或格式错误时允许一次定向重做；继续失败则计入阶段恢复次数。
- Scope 最多 3 次。
- full/fast 内部 Fix 最多 3 轮。
- 每阶段每角色最多自动恢复 2 次，超过后进入 `PAUSED`。
- eval 中任一质量硬门禁退化时，撤销对应瘦身项。

## 第二期候选

第二期按以下顺序逐项实验。

### 1. CallChain 按需调度

主会话先判断 Builder diff 是否涉及：

- 外部可触发入口
- MQ、Scheduler、callback 或延迟任务
- 多阶段生命周期状态变化

明显不命中时由主会话记录 `NOOP`；命中时才调度 CallChain Agent。

在 eval shadow 阶段，即使主会话判断 `NOOP`，仍运行旧 CallChain Agent 对比结论。负样本和正样本连续全部一致后才真正跳过调用。

### 2. 合并 profile/state

评估将静态配置合入 `state.json`，删除重复的：

- `output_dir`
- `plan_path`
- Agent 文档路径
- lifecycle 字段
- 没有消费方的 event 或 next-action 字段

保留恢复所需的最小状态：mode、phase、plan、commits、preflight、review、attempts 和 retries。

### 3. 简化进度协议

当 Agent 平台自身状态足够可靠时，只保留一种磁盘心跳，不同时维护每个 Agent 的 progress 文件和 `events.tsv`。

### 4. 后续评估

只有前三项收益不足时，才重新评估其他 Agent 或阶段。QA、CodeReview 和 full Scope Review 不是第二期默认删除对象。

## 双 Runtime 策略

Codex App 与 Claude Code 继续保持独立部署源码，避免本轮同时引入生成系统和瘦身重构。

新增归一化语义检查：

- 忽略 runtime 名称、路径和生命周期 API 差异。
- 比较 plan、full、fast 的阶段、artifact、tag、retry 和质量门禁。
- 比较四个保留 Agent 的职责和阶段覆盖。
- 任一行为差异必须是明确记录的 runtime 适配，而不是维护漂移。

## 实施顺序

1. 建立 eval fixtures、评分 rubric 和当前版本基线。
2. 删除独立 fix Skill、FeedbackTriage Agent 和专用状态。
3. 抽取 full/fast 共享编排契约。
4. 精简 Keel Plan。
5. 合并并精简 Codex Agent 文档。
6. 同步精简 Claude Code Agent 文档。
7. 清理无引用 helper，并保持 full/fast 状态输出兼容。
8. 更新 README、AGENTS.md、CLAUDE.md 和部署预期。
9. 执行脚本语法、双 runtime 部署、manifest、文件拓扑和语义一致性检查。
10. 运行改造后 eval，与基线比较。
11. 第一阶段全部硬门禁通过后，再启动 CallChain 按需调度实验。

## 工程验证

继续执行：

```bash
bash -n bin/keel
find common claude-code/common -type f -name '*.sh' -exec bash -n {} \;
```

部署验证只在临时目录执行：

```bash
tmpdir=$(mktemp -d)
bin/keel dev --codex "$tmpdir"
bin/keel dev --claude-code "$tmpdir"
rm -rf "$tmpdir"
git status --short
```

关键检查：

- 三个公开 Skill 正确部署。
- 两套 runtime 均不再部署 fix Skill 和 FeedbackTriage Agent。
- Codex Agent TOML 指向合并后的单一 Agent 文档。
- manifest 能清理旧 fix/FeedbackTriage 文件。
- full/fast 初始化结果和状态机仍符合兼容契约。
- 两套 runtime 的归一化语义一致。

## 风险与缓解

### 指令过度压缩

风险：删除的重复说明实际承担了模型纠偏作用。

缓解：第一期不改变质量阶段，使用同模型重复 eval；任何硬门禁下降即恢复对应规则。

### 双 Runtime 漂移

风险：人工同步压缩后的文档时出现语义差异。

缓解：增加归一化一致性检查，并在每次 runtime 修改时同时验证两套部署。

### 删除 Fix 后反馈处理变长

风险：极少数 DONE 后缺陷需要重新开始 run。

缓解：这是用户确认的取舍；保留 full/fast 内部修复闭环，并在新 run 中继续使用相同 plan 文件作为输入。

### 第二期误跳过 CallChain

风险：主会话预判遗漏复杂流程变化。

缓解：先 shadow 对比，再启用真实跳过；任何不一致都保留独立 CallChain 调度。

## 已确认决策

- 只保证强模型。
- 采用两期瘦身。
- 第一期保留 Plan、Builder、Scope Review、QA 和 CodeReview 的质量边界。
- 第一期直接删除独立 `/keel-dev-fix` 和 FeedbackTriage。
- 保留 full/fast 内部自动修复循环。
- 第二期优先评估 CallChain 按需调度。
- 暂不合并 QA 与 CodeReview，不删除 full Scope Review。
- 两套 runtime 继续独立部署，本轮不引入模板生成器。
