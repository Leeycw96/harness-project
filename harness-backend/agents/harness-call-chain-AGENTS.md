# harness-call-chain 操作手册

本手册描述 CallChain 阶段怎么做。你不直接联系 Builder、QA 或 CodeReview,只维护跨迭代业务流程入口索引。

## 启动必做

每次收到主会话任务都必须重新执行:

1. 从任务 prompt 读取 `HARNESS_PROFILE` 绝对路径。
2. Read `profile.json`,记下 `project_dir`、`output_dir`、`plan_path`、artifact 路径。
3. Read `${output_dir}/state.json`,尤其是 `build.commits`。
4. Read `.codex/agents/harness-call-chain.md` 和本手册。
5. Read 项目根 `AGENTS.md`;没有则读 `CLAUDE.md`。
6. Read `${output_dir}/plan.md`、`${output_dir}/build-scope.md` 和现有 `.harness/call-chain/`。
7. 只审 `state.json.build.commits` 对应的 Builder diff,不要审用户无关未提交改动。

初始化进度:

```bash
export HARNESS_PROFILE="<绝对路径>"
source .codex/common/scripts/harness-common.sh
update_progress "harness-call-chain" "CALL_CHAIN" "开始审查业务流程入口索引" "${output_dir}/call-chain-review.md"
```

## 通信规则

- 不给 Builder、QA 或 CodeReview 发消息。
- 不读取 `conversation/`、`signals/` 或 round 历史文件。
- 阶段完成时执行:

```bash
complete_stage "harness-call-chain" "<TAG>" "<一句话结论 + 1-3 个关键点>" "${output_dir}/call-chain-review.md"
```

然后最终回复只写 tag、artifact、可选 commit sha 和关键结论。

## Call-chain 文件定义

一个 `.harness/call-chain/<business-flow>.md` 文件对应一个**业务流程**,不是业务域、接口、feature slug。

业务流程定义:

- 围绕一个明确业务目标从开始推进到终态。
- 由一个或多个外部可触发入口驱动。
- 文件名使用 `<业务域>-<业务流程>.md`,例如 `order-purchase.md`、`order-refund.md`、`settlement-payout.md`。

外部可触发入口包括:

- HTTP Controller / Route
- 对外 RPC Provider / Facade
- MQ Listener
- Scheduler / Job / 延迟任务
- 外部 callback / webhook

内部同步调用不算入口,包括 Service 内部调用、DAO/Repository、DTO/Converter、同步调用其他 RPC 客户端。

## 创建或更新门禁

默认 `NOOP`。只有本轮 Builder diff 出现业务流程可见变化,才允许创建或更新 call-chain。

业务流程可见变化包括:

- 外部可触发入口新增、删除、重命名或语义变化
- MQ、Scheduler、外部 callback、延迟任务等异步推进点新增、删除或语义变化
- 已有 call-chain 对应业务对象的生命周期状态或状态流转变化

创建新 call-chain 必须满足以下任一条件:

1. **多入口参与同一业务目标**: 同一个业务目标需要两个及以上外部入口推进,例如 HTTP 下单 + MQ 支付回调。
2. **存在异步推进边界**: 初始请求同步返回后,业务还会被 MQ、Scheduler、外部 callback 或延迟任务继续推进。
3. **存在多阶段状态流转**: 业务对象存在明确生命周期状态,例如 `CREATED -> PAID -> SHIPPED -> DONE`,且这些状态不是一次同步调用内全部完成。

更新已有 call-chain 必须满足:

- 本轮变化属于现有 call-chain 描述的业务流程;并且
- 入口目录、异步推进步骤、业务流程步骤或多阶段状态流转需要同步修正。

反向门禁:

- 简单查询、列表、详情、统计、导出: `NOOP`
- 单步同步 CRUD: `NOOP`
- 只有一个 Controller/RPC 入口且同步完成整个业务目标: `NOOP`,除非它属于已有复杂流程的一个入口
- Service 内部同步调用其他 RPC: 不记录
- DAO / Repository / DTO / Converter / 参数校验: 不记录
- 不确定是否达到创建标准: `NOOP`,并在 `call-chain-review.md` 写明原因

判断顺序:

```text
1. 本轮 diff 是否有业务流程可见变化?
   否 -> NOOP

2. 这个变化是否属于已有 call-chain 文件?
   是 -> 更新已有文件

3. 是否满足多入口、异步推进、多阶段状态流转之一?
   是 -> 新建 <domain>-<flow>.md
   否 -> NOOP
```

## Call-chain 文件格式

文件必须简洁,只做业务流程入口索引:

```markdown
# 业务流程名称

## 业务说明
一句话说明这个流程完成什么业务闭环。

## 入口目录
| 步骤 | 触发类型 | 入口类 | 入口方法 | 说明 |
|------|----------|--------|----------|------|

## 流程
1. ...
2. ...

## 不记录
- Service 内部同步调用
- DAO / Repository 调用链
- DTO 转换
- 单纯查询接口
- 单步同步 CRUD
```

禁止:

- 记录完整方法级调用链
- 为每个接口创建一个文件
- 使用 feature slug 直接命名文件
- 记录内部同步 RPC 客户端调用
- 把业务域写成一个大文件,例如 `order.md`

## Artifact 契约

写 `${output_dir}/call-chain-review.md`:

```markdown
# CallChain Review

## 最终判定
UPDATED 或 NOOP

## 审查范围
- base: <sha>
- head: <sha>
- commits:
  - <sha> <title>

## 判定过程
- 是否修改外部可触发入口: 是/否
- 是否命中已有 call-chain: 是/否, <file>
- 是否满足创建/更新门禁: 是/否, <原因>

## 变更
- updated files: ...
- commit: <sha 或 none>

## NOOP 原因
- ...
```

## Stage SOP

### CALL_CHAIN

输入: `plan.md`、`build-scope.md`、`state.json.build.commits`、现有 `.harness/call-chain/`。

步骤:

1. 写 progress,说明审查范围。
2. 获取 Builder commit diff。如果有多个 Builder commit,审从第一个 commit 的 parent 到最后一个 commit 的 diff。
3. 识别 diff 中新增、删除或修改的外部可触发入口、异步推进点和已有流程状态流转。
4. 按“创建或更新门禁”判断 `UPDATED` 或 `NOOP`。
5. `NOOP` 时只写 `call-chain-review.md`,执行:

```bash
complete_stage "harness-call-chain" "CALL_CHAIN_NOOP" "无需更新 call-chain: <原因>" "${output_dir}/call-chain-review.md"
```

6. `UPDATED` 时:
   - 只创建或更新 `.harness/call-chain/<business-flow>.md`
   - 只 stage 你本轮更新的 `.harness/call-chain/*.md`
   - 创建单独 docs commit,提交信息使用 `call-chain: 更新<业务流程>流程索引` 或 `call-chain: 更新业务流程索引`
   - 写 `call-chain-review.md`,记录更新文件和 commit sha
   - 执行:

```bash
complete_stage "harness-call-chain" "CALL_CHAIN_UPDATED" "call-chain 已更新: <file>" "${output_dir}/call-chain-review.md"
```

## 禁忌

- 不改业务代码或测试。
- 不修改 Builder commit。
- 不 stage run 目录 artifact。
- 不为简单接口、查询接口或单步 CRUD 创建 call-chain。
- 不把内部调用链写进 call-chain。
- 不因为 plan feature 存在就创建同名 call-chain。
