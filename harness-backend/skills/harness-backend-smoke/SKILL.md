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

### 3. 解析脚本并呈现执行计划(开跑前必做)

**目的**:在开跑前让用户清楚"这次冒烟一共多少步、哪些自动跑、哪些要我参与",避免开跑后才发现自己被抓壮丁、或 AI 默默循环执行多个脚本。

对每个被选 slug 的 `smoke-{slug}.sh` 做静态扫描:

| 计数项 | 扫描方式 | 含义 |
|--------|----------|------|
| 自动断言 | `grep -cE '^[[:space:]]*(log_pass\|log_fail)\b' smoke-{slug}.sh` | 脚本自动 `curl` 后断言响应的步骤 |
| 人工交互 | `grep -cE '^[[:space:]]*wait_user_action\b' smoke-{slug}.sh` | 需要用户在终端输入 c/s/a 的暂停点(含人工触发 + DB 核验) |
| 异步轮询 | `grep -cE '^[[:space:]]*wait_until\b' smoke-{slug}.sh` | 脚本内 HTTP 轮询点,自动等待但耗时较长 |

把所有被选 slug 汇总成一张表呈给用户,**必须用 markdown 表格直出,不要塞进折叠块**:

```
本次冒烟总览
| slug          | 自动断言 | 人工交互 | 异步轮询 |
|---------------|----------|----------|----------|
| order-create  | 5        | 4        | 1        |
| order-cancel  | 3        | 2        | 0        |
合计:用户需在 6 个时刻参与
```

> 计数仅按文本扫描,if/case 内的分支会被一并计入,实际可能少跑——预估值,不是契约值。如脚本里的关键字被花式包装(如别名)导致计数明显偏离,在表下加一行说明,不要伪造数字。

随后用 `AskUserQuestion` 让用户决定:
- 「确认开跑」(默认)
- 「重新选择 slug」(回到第 2 步)
- 「中止」

### 4. 启动并运行脚本

```bash
bash .harness/smoke-tests/smoke-{slug}.sh
```

脚本内部已包含完整生命周期(启动服务 → 业务步骤 → 停止服务),本 skill 只是 fork-exec 它。

### 5. 与用户的交互(运行时)

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

### 6. 单 slug 完成后的 checkpoint(多 slug 顺序运行时必做)

**只有用户在第 2 步选了 ≥2 个 slug 时才走这步**;单 slug 直接跳到第 7 步。

每个 slug 的脚本退出后,**立刻**向用户回播 mini-summary,**禁止**默默接续下一个 slug:

```
[1/3] smoke-order-create.sh 完成
  PASS=4 / FAIL=1 / SKIP=0
  失败步骤:
    - 创建订单后查询订单详情:期望 status=PENDING,实际 status=null
  剩余待跑:order-cancel, order-pay
```

随后用 `AskUserQuestion` 决定下一步:
- 「继续下一个({next-slug})」(默认,本 slug 全 PASS 时强烈推荐)
- 「先停下来诊断本次失败」(仅当本 slug 有 FAIL 时呈现)
- 「跳过下一个 slug,继续往后」
- 「中止整批,直接进入汇总」

> checkpoint **不**单独落盘失败记录——失败记录在第 7.1 步统一写。但 checkpoint 必须如实呈现 PASS/FAIL/SKIP 数,禁止"看起来都过了"这种模糊措辞。

### 7. 汇总并报告

脚本结束后,**先落盘再报告**,顺序不能颠倒:

1. 收集 `log_pass` / `log_fail` / `log_skip` 输出
2. **立刻**写入失败记录文件(下文 7.1 规定),不允许跳过
3. 向用户报告:本次冒烟覆盖的步骤数、PASS / FAIL / SKIP 数、每条 FAIL 的具体原因
4. 多 slug 顺序运行时,逐个汇总,最后给出总览
5. 报告末尾给出失败记录文件路径,提示用户「即使会话中断,该文件可独立用于后续修复」

### 7.1 失败记录文件(必写)

**目的**:让失败信息独立于本 skill 的上下文存在。会话压缩、用户切走、跨次启动后,后续步骤(尤其是修复模式)仍能从磁盘恢复完整信息,不依赖 AI 记忆。

**写入时机**:脚本结束后**立刻**写入,**先于**向用户报告。

**路径**:

```
.harness/smoke-tests/failures/run-$(date +%Y%m%d-%H%M%S).md
```

目录不存在则先 `mkdir -p`。

**结构**:

- **顶部元信息**:运行时间、本次执行的 slug 列表、PASS / FAIL / SKIP 总数
- **每条 FAIL 一节**(`## {slug} / {step-name}`),节内字段固定:
  - **失败时间**(脚本输出中的时间戳)
  - **诊断分类**(失败诊断表四行之一,必须准确填写——决定后续是否进入修复模式)
  - **失败现象**:从脚本 stdout **原样截取**的 FAIL 行
  - **关键日志片段**:FAIL 前后若干行原文
  - **call-chain**:`.harness/call-chain/{slug}.md`(只填路径,不复制内容)
  - **smoke 脚本**:`.harness/smoke-tests/smoke-{slug}.sh`

只引用证据,不臆测原因。原因分析是 builder 的职责,不是 smoke 的。

**唯一性约定**:此后所有读取(是否有真 bug、生成修复 plan)**只从这份文件读**,严禁从 skill 上下文复述。

## 失败诊断

脚本失败时,先诊断再判定:

| 现象 | 处理 |
|------|------|
| **脚本与 call-chain 不一致**(call-chain 改了脚本没跟) | 不自行修脚本。提示用户:「脚本 `smoke-{slug}.sh` 与 `.harness/call-chain/{slug}.md` 不一致,请通知 harness-qa 更新冒烟脚本后重跑」 |
| **两者一致但 call-chain 可能过期**(实现已变,call-chain 落后) | 提示用户人工核对,确认后通知 builder 更新 call-chain,再由 qa 更新冒烟脚本 |
| **环境问题**(端口占用、依赖服务未启动、JDK 版本错) | 给出修复建议,标记为环境错误,允许用户修复后重试 |
| **以上都排除后仍失败** | 判定 FAIL,记录失败原因 + 关键日志片段。报告完成后进入下文「修复模式」 |

## 修复模式(可选)

仅当本次冒烟出现至少一条被判定为「真 bug」的 FAIL 时触发。
**前三类失败(脚本与 call-chain 不一致 / call-chain 过期 / 环境)绝不进入修复模式**——那是 qa 或用户的责任,不该拉 builder。

设计原则:**修问题、验证修复是 builder 和 qa 本职行为,smoke 只负责把任务扔给它们 + 等回信 + 重跑**。不为冒烟修复给 builder/qa 增加任何"流式修复模式 SOP"——它们的灵魂里"接任务→实现→通知 qa→验证"已经够用,差异通过启动消息说明即可。

### 询问用户

读取「7.1 失败记录文件」,统计其中诊断分类为「真 bug」的小节数量:

- 0 条 → 不进入修复模式,直接结束
- ≥ 1 条 → 使用 `AskUserQuestion`:
  - 选项一:「进入修复模式,启动 builder + qa 在线协同修复」
  - 选项二:「仅生成报告,我自己处理」(默认,维持现状)

### 启动 builder + qa

用户选择进入修复模式时:

1. **初始化 tmux 编排环境**:

   ```bash
   source .claude/common/scripts/harness-init.sh
   ```

2. **约定本批次的 ack 文件路径**(完成信号,不复用 `.harness/done`——那是 harness-backend 的):

   ```
   .harness/smoke-tests/fix-ack-$(date +%Y%m%d-%H%M%S)
   ```

3. **启动两个 Agent 的 pane,然后写 config,再发初始 prompt**(三步必须按顺序):

   ```bash
   launch_agent_pane "harness-builder" "harness-builder"
   launch_agent_pane "harness-qa"      "harness-qa"
   write_config ""    # 修复模式没有迭代目录,output_dir 传空字符串
   ```

   随后向两个 agent 发 prompt——内容必须明确以下三点,避免 agent 惯性进入完整迭代流程:

   - **任务文件**:本次「失败记录文件」的绝对路径,只处理诊断分类为「真 bug」的小节
   - **跳过的阶段**:scope 对齐、`build-scope-v{N}` 产出、用户调整、`.harness/done` 写入——**全部跳过**;本批次按"修复阶段"语义直接处理
   - **完成信号**:全部真 bug 修完且 qa 验证通过后,由 qa `touch` ack 文件(内容可空);**不要写 `.harness/done`**;ack 后保持 pane 在线等下一批

   ```bash
   dispatch_initial_prompt "harness-builder" "你的配置文件在 ${PROJECT_DIR}/.harness/config.json,先读它。本次是冒烟回流的修复任务(不是完整迭代)——任务文件:{失败记录路径};跳过 scope 对齐 / build-scope / 用户调整 / .harness/done;qa 验完一批后写 {ack 路径},pane 保持在线等下一批。"
   dispatch_initial_prompt "harness-qa"      "你的配置文件在 ${PROJECT_DIR}/.harness/config.json,先读它。本次是冒烟回流的修复验证(不是完整迭代)——任务文件:{失败记录路径};跳过 Scope 审阅 / 评分 / 用户调整 / .harness/done;builder 通知后做修复验证,全部真 bug 通过时由你 touch {ack 路径},pane 保持在线等下一批。"
   ```

   builder/qa 之间的协作仍按它们灵魂里的常规模式——builder 改完通知 qa,qa 验证通过 / 打回循环。smoke skill 不介入这条循环。

### 等待 ack

```bash
wait_for_file "{ack 路径}" 14400
```

超时 4 小时(冒烟修复一般小于完整迭代,4h 足够)。超时后向用户报告并提示去对应 pane 查看实时状态,**不自动 cleanup**。

### 重跑该 slug(用户负责数据准备)

ack 出现后**不要直接重跑**——前面已成功步骤的 DB 副作用(已下单订单、已写入记录)还在,会污染重跑结果。

使用 `AskUserQuestion`:

- 选项一:「已确认 DB 状态可重跑」→ 回到「3. 启动并运行脚本」重跑该 slug 的 smoke 脚本
- 选项二:「需要先清数据,稍后回来」→ 暂停,等用户回来后再问
- 选项三:「跳过该 slug,继续下一个」→ 标记 SKIP,继续后续 slug

### 再次失败时复用 pane

重跑后:

- **通过** → 继续下一个 slug
- **再次出现真 bug** → 不再 `launch_agent`,**复用现有 pane**:
  1. 落盘新一份失败记录(回到「7.1」)
  2. 约定新的 ack 路径
  3. `send_to_agent "harness-builder" "新一批修复任务,失败记录:{新文件路径},完成后请 qa touch {新 ack 路径}"`
  4. 回到「等待 ack」
- **再次失败但落入前三类**(脚本不一致 / call-chain 过期 / 环境)→ 异常报告:修复后诊断分类发生了变化,可能是新引入问题或环境变化,提示用户人工排查,**不再继续修复循环**

### Cleanup

所有 slug 跑通(或用户主动退出修复模式)后:

```bash
cleanup_panes
```

提示用户:「修复模式结束,builder/qa pane 已关闭。ack 文件保留在 `.harness/smoke-tests/` 下作为审计凭证。」
