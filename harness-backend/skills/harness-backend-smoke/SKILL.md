---
name: harness-backend-smoke
description: 运行 .harness/smoke-tests/ 中的冒烟测试脚本,引导用户半自动验证业务流程。脚本由 harness-qa 在第三层产出,本 skill 只负责运行与引导。
user-invocable: true
---

# harness-backend-smoke:冒烟测试运行

## 定位

按用户主动触发的 SOP 运行 harness-qa 已产出的冒烟脚本——HTTP 步骤由脚本自动 `curl` 做接口断言,数据状态由用户在关键步骤后人工核验,非 HTTP 触发(Scheduler / MQ / RPC)由脚本暂停并引导用户手动触发,完成后由用户自行查 DB 核验副作用。

**本 skill 不编写脚本**。脚本编写归 harness-qa 第三层职责。脚本缺失或与 call-chain 不一致时,本 skill 只报告并提示用户回流到 qa,不自行补写。

## 输入

- `.harness/call-chain/{slug}.md`:业务流程调用链文档(只读,用于诊断脚本与流程是否一致)
- `.harness/smoke-tests/smoke-{slug}.sh`:待运行的冒烟脚本
- `.harness/smoke-tests/smoke-common.sh`:公共函数库

## 执行 SOP

### 1. 前置检查

依次检查并对缺失项给出明确提示,不自行补写:

| 检查项 | 缺失时的处理 |
|--------|------------|
| `.harness/call-chain/` 存在且非空 | 提示用户:「无可用 call-chain,请先让 harness-builder 在迭代中生成」,中止 |
| `.harness/smoke-tests/smoke-common.sh` 存在 | 提示用户:「公共函数库缺失,请通知 harness-qa 补产」,中止 |
| `.harness/smoke-tests/` 下有 `smoke-*.sh` | 提示用户:「未找到冒烟脚本,请通知 harness-qa 在第三层补产」,中止 |
| 服务监听端口空闲(由脚本启动应用) | 端口被占用时提示用户先停掉占用进程 |

### 2. 选择要运行的 call-chain

使用 `AskUserQuestion` 让用户从 `.harness/smoke-tests/smoke-*.sh` 列出的 slug 中选择一条(可多选,顺序运行)。

若被选 slug 在 `.harness/call-chain/` 中无对应文件,提示「该 slug 没有 call-chain 描述,可能是孤儿脚本,请通知 qa 核对」,允许用户决定是否仍要运行。

### 3. 启动并运行脚本

```bash
bash .harness/smoke-tests/smoke-{slug}.sh
```

脚本内部已包含完整生命周期(启动服务 → 业务步骤 → 停止服务),本 skill 只是 fork-exec 它。

### 4. 与用户的交互(运行时)

脚本执行过程中遇到 `wait_user_action`,会打印两类提示并阻塞等待用户输入 `c`/`s`/`a`:

#### 人工触发步骤(三段式)

1. **指令**:脚本明确告诉用户要触发什么——给出 Scheduler 名 / MQ topic / RPC 方法,以及可执行的触发方式提示(管理后台路径、命令示例)
2. **等待**:用户在终端输入
   - `c` → 继续
   - `s` → 跳过该步及其依赖项(整条标记 SKIP)
   - `a` → 中止脚本
3. **后置数据人工核验**:用户输入 `c` 后,脚本继续暂停一次,给出明确的 DB 核验提示(表、定位字段、期望值、可直接复用的 `select`)。用户在自己的 DB 客户端查库后输入 `c` 表示已确认副作用

#### 简单数据核验

业务步骤完成后,脚本可能直接给出一段 DB 核验提示并阻塞,等待用户查库后输入 `c` 继续。

> 非交互环境(`HARNESS_NONINTERACTIVE=1`)下,`wait_user_action` 自动 SKIP 当前步骤并记录原因,后续依赖项一并 SKIP。

### 5. 汇总并报告

脚本结束后:

- 收集 `log_pass` / `log_fail` / `log_skip` 输出
- 报告给用户:本次冒烟覆盖的步骤数、PASS / FAIL / SKIP 数、每条 FAIL 的具体原因
- 多 slug 顺序运行时,逐个汇总,最后给出总览

## 失败诊断

脚本失败时,先诊断再判定:

| 现象 | 处理 |
|------|------|
| **脚本与 call-chain 不一致**(call-chain 改了脚本没跟) | 不自行修脚本。提示用户:「脚本 `smoke-{slug}.sh` 与 `.harness/call-chain/{slug}.md` 不一致,请通知 harness-qa 更新冒烟脚本后重跑」 |
| **两者一致但 call-chain 可能过期**(实现已变,call-chain 落后) | 提示用户人工核对,确认后通知 builder 更新 call-chain,再由 qa 更新冒烟脚本 |
| **环境问题**(端口占用、依赖服务未启动、JDK 版本错) | 给出修复建议,标记为环境错误,允许用户修复后重试 |
| **以上都排除后仍失败** | 判定 FAIL,输出失败原因 + 关键日志片段(必要时引用脚本输出文件路径) |
