---
name: harness-solidity-smoke
description: 运行 script/smoke/ 中的冒烟测试 forge script，引导用户在本地链或 fork 上半自动验证合约真实链路。脚本由 harness-sol-qa 在第三层产出，本 skill 只负责运行与引导。
user-invocable: true
---

# harness-solidity-smoke：合约冒烟测试运行

## 定位

按用户主动触发的 SOP 运行 harness-sol-qa 已产出的冒烟脚本——external 调用由脚本自动发起 + 链上状态/事件双层断言;automation / oracle / 跨链消息等链下触发由脚本暂停并引导用户手动触发,完成后继续执行后置断言。

**本 skill 不编写脚本**。脚本编写归 harness-sol-qa 第三层职责。脚本缺失或与 contract-graph 不一致时,本 skill 只报告并提示用户回流到 sol-qa,不自行补写。

## 输入

- `.harness/contract-graph/{slug}.md`:合约业务流程图(只读,用于诊断脚本与流程是否一致)
- `script/smoke/Smoke_{slug}.s.sol`:待运行的冒烟脚本
- `script/smoke/SmokeCommon.s.sol`:公共函数库
- `script/smoke/README.md`:运行说明、依赖状态表

## 执行 SOP

### 1. 前置检查

依次检查并对缺失项给出明确提示,不自行补写:

| 检查项 | 缺失时的处理 |
|--------|------------|
| `.harness/contract-graph/` 存在且非空 | 提示用户:「无可用 contract-graph,请先让 harness-sol-builder 在迭代中生成」,中止 |
| `script/smoke/SmokeCommon.s.sol` 存在 | 提示用户:「公共函数库缺失,请通知 harness-sol-qa 补产」,中止 |
| `script/smoke/` 下有 `Smoke_*.s.sol` | 提示用户:「未找到冒烟脚本,请通知 harness-sol-qa 在第三层补产」,中止 |
| `foundry.toml` 启用 `ffi = true` | 未启用先帮用户加上(`pauseForUserAction` 依赖 ffi);若用户拒绝,标记为环境受限并退出 |

### 2. 选择运行模式

使用 `AskUserQuestion` 让用户从两种模式中选择:

| 模式 | 说明 | 检查 |
|------|------|------|
| 本地链(anvil) | 连接到用户已启动的 anvil(默认 `http://localhost:8545`) | 用 `cast block-number --rpc-url http://localhost:8545` 探测;未运行则提示用户在新终端跑 `anvil` |
| Fork 主网 | 通过 `vm.createSelectFork` 在 setUp 内 fork | 要求用户提供 RPC URL(`MAINNET_RPC` 环境变量或现场输入)与目标区块号 |

### 3. 选择要运行的 contract-graph

使用 `AskUserQuestion` 让用户从 `script/smoke/Smoke_*.s.sol` 列出的 slug 中选择一条(可多选,顺序运行)。

若被选 slug 在 `.harness/contract-graph/` 中无对应文件,提示「该 slug 没有 contract-graph 描述,可能是孤儿脚本,请通知 sol-qa 核对」,允许用户决定是否仍要运行。

### 4. 运行脚本

```bash
forge script script/smoke/Smoke_{slug}.s.sol \
  --rpc-url $RPC \
  --ffi \
  -vvv 2>&1 | tee script/smoke/.runs/$(date +%s).log
```

`--broadcast` 标志按需开启:**本地链推荐 broadcast,fork 通常不开**。

### 5. 与用户的交互(运行时)

脚本执行过程中遇到 `pauseForUserAction(prompt, hint)`(背后用 `vm.ffi` 调 bash `read`),会打印两类提示并阻塞等待用户输入 `c`/`s`/`a`:

#### 人工触发步骤(三段式)

1. **指令**:脚本明确告诉用户要触发什么——给出合约名 / 函数 / 角色,以及可执行的触发方式提示(Tenderly UI 路径、`cast send` 命令示例)
2. **等待**:用户在终端输入
   - `c` → 继续
   - `s` → 跳过该步及其依赖项(整条标记 SKIP)
   - `a` → 中止脚本
3. **后置状态断言**:用户输入 `c` 后,脚本立刻执行链上读取,验证人工触发的副作用是否落到 storage / 是否 emit 了预期事件

> 非交互环境(`HARNESS_NONINTERACTIVE=1`)下,`pauseForUserAction` 自动 SKIP 当前步骤并记录原因,后续依赖项一并 SKIP。

### 6. 汇总并报告

脚本结束后:

- 收集 `logPass` / `logFail` / `logSkip` 输出(写入 `script/smoke/.runs/<timestamp>.log`)
- 报告给用户:本次冒烟覆盖的步骤数、PASS / FAIL / SKIP 数、每条 FAIL 的具体原因 + 关键 trace 摘要
- 多 slug 顺序运行时,逐个汇总,最后给出总览

## 失败诊断

脚本失败时,先诊断再判定:

| 现象 | 处理 |
|------|------|
| **脚本与 contract-graph 不一致**(contract-graph 改了脚本没跟) | 不自行修脚本。提示用户:「脚本 `Smoke_{slug}.s.sol` 与 `.harness/contract-graph/{slug}.md` 不一致,请通知 harness-sol-qa 更新冒烟脚本后重跑」 |
| **两者一致但 contract-graph 可能过期**(实现已变,contract-graph 落后) | 提示用户人工核对,确认后通知 sol-builder 更新 contract-graph,再由 sol-qa 更新冒烟脚本 |
| **环境问题**(fork RPC 限速、anvil 未启动、`ffi` 未启用、私钥/account 未配置) | 给出修复建议,不判 FAIL,标记为环境错误重试 |
| **以上都排除后仍失败** | 判定 FAIL,输出失败原因 + `forge script` 完整 trace 文件路径 |
