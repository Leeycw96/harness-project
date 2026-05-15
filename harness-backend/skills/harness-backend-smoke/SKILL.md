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
- `.harness/smoke-tests/{slug}/smoke.sh`:orchestrator,启停服务并按序遍历 step
- `.harness/smoke-tests/{slug}/[0-9][0-9]-*.sh`:step 子脚本,序号即执行顺序
- `.harness/smoke-tests/smoke-common.sh`:公共函数库

## 执行 SOP

### 1. 前置检查

依次检查并对缺失项给出明确提示,不自行补写:

| 检查项 | 缺失时的处理 |
|--------|------------|
| `.harness/call-chain/` 存在且非空 | 提示用户:「无可用 call-chain,请先让 harness-builder 在迭代中生成」,中止 |
| `.harness/smoke-tests/smoke-common.sh` 存在 | 提示用户:「公共函数库缺失,请通知 harness-qa 补产」,中止 |
| `.harness/smoke-tests/` 下有至少一个 `{slug}/smoke.sh` | 提示用户:「未找到任何 slug 目录,请通知 harness-qa 在第三层补产」,中止 |
| 选定 slug 目录下有 `[0-9][0-9]-*.sh` step | 缺 step 时提示「{slug} 仅有 orchestrator 无 step,请通知 qa 补产」,中止该 slug |
| 服务监听端口空闲(由脚本启动应用) | 端口被占用时提示用户先停掉占用进程 |

### 2. 选择要运行的 call-chain

使用 `AskUserQuestion` 让用户从 `.harness/smoke-tests/*/smoke.sh` 列出的 slug 目录中选择一条(可多选,顺序运行)。

若被选 slug 在 `.harness/call-chain/` 中无对应文件,提示「该 slug 没有 call-chain 描述,可能是孤儿脚本,请通知 qa 核对」,允许用户决定是否仍要运行。

### 3. 解析脚本并呈现执行计划(开跑前必做)

**目的**:在开跑前让用户清楚"这次冒烟一共多少步、哪些自动跑、哪些要我参与",避免开跑后才发现自己被抓壮丁、或 AI 默默循环执行多个脚本。

对每个被选 slug 目录做静态扫描:

| 计数项 | 扫描方式 | 含义 |
|--------|----------|------|
| 步骤总数 | `ls .harness/smoke-tests/{slug}/[0-9][0-9]-*.sh \| wc -l` | step 子脚本数,即执行的业务步骤数 |
| 人工交互 | `grep -cE '^[[:space:]]*wait_user_action\b' .harness/smoke-tests/{slug}/[0-9][0-9]-*.sh \| awk -F: '{s+=$2}END{print s}'` | 需要用户在终端输入 c/s/a 的暂停点(含人工触发 + DB 核验) |
| 异步轮询 | `grep -cE '^[[:space:]]*wait_until\b' .harness/smoke-tests/{slug}/[0-9][0-9]-*.sh \| awk -F: '{s+=$2}END{print s}'` | step 内 HTTP 轮询点,自动等待但耗时较长 |

把所有被选 slug 汇总成一张表呈给用户,**必须用 markdown 表格直出,不要塞进折叠块**:

```
本次冒烟总览
| slug          | 步骤总数 | 人工交互 | 异步轮询 |
|---------------|----------|----------|----------|
| order-create  | 5        | 4        | 1        |
| order-cancel  | 3        | 2        | 0        |
合计:用户需在 6 个时刻参与
```

> 计数按文本扫描,if/case 内的分支会被一并计入,实际可能少跑——预估值,不是契约值。如 step 内 `wait_user_action` 被花式包装(如循环、别名)导致计数明显偏离,在表下加一行说明,不要伪造数字。

#### 3.1 渲染 prepare.md 并确认就绪

每个被选 slug 必有 `00-prepare.md`(由 harness-qa 在第三层产出)。**不存在则提示「该 slug 缺 prepare.md,请通知 qa 补产」并中止**——不再走"允许用户绕过"的旁门,因为缺 prepare.md 意味着 actor / 数据 / 触发方式没人对齐过,跑下去多半中途出事。

读取 `00-prepare.md` 并把四张表逐段渲染给用户:

```
[order-create] 冒烟前准备清单(来自 00-prepare.md)

## Actor 表(谁调谁)
  01-login.sh        → 普通用户(账号 user_smoke_001,凭据见 vault)
  02-create-order.sh → 普通用户(复用 01 token)
  03-approve.sh      → 管理员(账号 admin_smoke_001,凭据见 vault)

## 预置数据
  - product 表:sku=SKU001 status=ON_SHELF stock>=10
  - user    表:username=user_smoke_001 status=ACTIVE

## 外部依赖
  - Redis(localhost:6379)需可达
  - 短信网关 mock(8090 端口)

## 非 HTTP 触发点
  - OrderCancelScheduler  → 临时入口 POST /_smoke/trigger/order-cancel
  - order.paid (MQ topic) → 后台手动 rabbitmqadmin publish ...

## 临时入口文件清单(冒烟后将由 skill 引导清理)
  - src/main/java/com/example/smoke/SmokeTriggerController.java(新增)
```

随后用 `AskUserQuestion` 让用户决定:
- 「全部就绪,开跑」(默认)
- 「未就绪 / 需调整,先暂停」(中止本次,用户准备完后再来)
- 「prepare.md 已过期,请通知 qa 更新」(中止,提示用户回流到 qa)
- 「重新选择 slug」(回到第 2 步)

> 多 slug 顺序运行时,第 3.1 步对每个 slug 都做一次,不要批量合并——每条流程的准备项独立,合并展示用户容易遗漏。

#### 3.2 加载复利经验 `lessons.xml`(条件触发)

每个 slug 可能有一份经验文件 `.harness/smoke-tests/{slug}/lessons.xml`,记录历次冒烟沉淀的"触发要点 / 数据准备 / 已知坑"等参考性提示。**首次冒烟时该文件不存在,正常**——直接跳过本步。

文件存在时,解析并把所有 `<category>` 渲染给用户:

```
[order-create] 累积复利经验(共 3 条,来自 lessons.xml)
  [触发要点]
    - auth-token: 创建订单需先调 /auth/login,token 30min 过期
  [数据准备]
    - product-stock: product_stock 需预置 sku=SKU001 库存 ≥ 10,否则 step 03 必失败
  [已知坑]
    - mq-delay: order.paid MQ 消费 5s 延迟,wait_until 至少 10s
```

随后 `AskUserQuestion`:
- 「全部仍适用」(默认)
- 「部分已过期,我手动改 lessons.xml 后重启」(中止当前流程,等用户改完再来)
- 「全部跳过,本次不参考」(不删除文件,只是本次不应用)

**lessons.xml schema**:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<lessons slug="order-create" updated="2026-05-15" version="3">
  <category name="trigger-essentials" label="触发要点">
    <item id="auth-token">创建订单需先调 /auth/login,token 30min 过期</item>
  </category>
  <category name="data-prep" label="数据准备">
    <item id="product-stock">product_stock 需预置 sku=SKU001 库存 ≥ 10</item>
  </category>
  <category name="known-pitfalls" label="已知坑">
    <item id="mq-delay">order.paid MQ 消费 5s 延迟,wait_until 至少 10s</item>
  </category>
</lessons>
```

约定:`<lessons>` 必须有 `slug`/`updated`/`version` 属性;`<category>` 的 `name` 是 slug-friendly 标识符(用于去重),`label` 是中文展示名;`<item>` 必须有 `id`(slug-friendly,用于"更新而不是新增")。推荐(非强制)category:`trigger-essentials` / `data-prep` / `known-pitfalls` / `account-matrix` / `perf-baseline`。

### 4. 引导用户在自己终端启动脚本

**本 skill 不再 fork-exec smoke.sh**——交还启停权给用户,方便随时 Ctrl+C、加 `bash -x`、改 env 重跑。

打印命令并阻塞等待用户回报:

```
请在你自己的终端执行(支持 Ctrl+C / bash -x / 改 env):

  cd <repo-root>
  bash .harness/smoke-tests/{slug}/smoke.sh

跑完后回到本会话告诉我「跑完了」(或贴一句话也行),我从 .run/result.json 读结构化结果。
```

orchestrator 内部已包含完整生命周期(启动服务 → 初始化 RUN_DIR → result_init → 顺序遍历 `[0-9][0-9]-*.sh` step → result_finalize → 停止服务),并把结果落盘到 `.harness/smoke-tests/{slug}/.run/result.json`。step 之间通过 `{slug}/.run/state.env` 共享 token / orderNo 等状态。

用户回报后,**只读 result.json**,不读 stdout——结构化输入比截取 stdout 稳。读不到 result.json 时(orchestrator 异常退出 / 用户中途 Ctrl+C 没等到 finalize)提示用户:

> 没找到 `.run/result.json`,可能 orchestrator 中途退出了。请贴最后 20 行 stdout 给我,我尽量诊断。

### 5. 与用户的交互(运行时)

脚本运行时有两类阻塞点:**step 内部的 `wait_user_action`**(脚本作者写死的业务核验)+ **step 外部的 `step_checkpoint`**(每个 step 跑完后的统一暂停)。本 skill 不在循环里——脚本是用户在自己终端跑——但需要让用户理解两类暂停的语义,因为发生在他们自己的终端里。

#### 5.1 step 外部:`step_checkpoint`(每个 step 跑完都暂停)

由 `step_run` 自动在每个 step 执行后触发,**默认行为,无需脚本作者写**。打印结果摘要 + state.env 关键字段(token / orderNo 等),阻塞等待用户输入:

| 输入 | 行为 |
|------|------|
| `c`  | 继续下一 step(默认) |
| `s`  | 跳过下一 step(标记 SKIP,继续后续) |
| `r`  | 重跑当前 step(状态保留) |
| `d`  | 调试模式:打印 `state.env` 路径 + 在另一个终端的重跑命令(`bash {slug}/{step-file}`),阻塞等用户调试完输入 `c` |
| `a`  | 中止整个冒烟 |

> 设计动因:用户每次 step 后都要去 DB 客户端查表核验,根本不存在"连续跑"的合理场景,所以默认就是逐 step 暂停,不再提供"连续 vs 单步"模式开关。

#### 5.2 step 内部:`wait_user_action`(脚本作者写死的业务核验)

step 内部出现 `wait_user_action` 时,有两类形态:

##### 5.2.1 人工触发步骤(三段式)

1. **指令**:脚本明确告诉用户要触发什么——给出 Scheduler 名 / MQ topic / RPC 方法,以及可执行的触发方式提示(管理后台路径、命令示例)
2. **等待**:用户在终端输入
   - `c` → 继续
   - `s` → 跳过该步及其依赖项(整条标记 SKIP)
   - `a` → 中止脚本
3. **后置数据人工核验**:用户输入 `c` 后,脚本继续暂停一次,给出明确的 DB 核验提示(表、定位字段、期望值、可直接复用的 `select`)。用户在自己的 DB 客户端查库后输入 `c` 表示已确认副作用

##### 5.2.2 简单数据核验

业务步骤完成后,脚本可能直接给出一段 DB 核验提示并阻塞,等待用户查库后输入 `c` 继续。

> 非交互环境(`HARNESS_NONINTERACTIVE=1`)下,`wait_user_action` 自动 SKIP 当前步骤并记录原因,后续依赖项一并 SKIP;`step_checkpoint` 默认按 `c` 处理(直接 return)。

> 5.1 和 5.2 的关系:某些 step 既有 `wait_user_action`(业务核验)又被 `step_checkpoint` 包裹(技术性确认),用户体验上是"step 内核验一次 → step 结束再确认一次"。这是合理的——前者由脚本作者写死必须发生,后者是 step 之间统一的"是否进入下一个"。

### 6. 单 slug 完成后的 checkpoint(多 slug 顺序运行时必做)

**只有用户在第 2 步选了 ≥2 个 slug 时才走这步**;单 slug 直接跳到第 7 步。

每个 slug 的脚本退出后,**立刻**向用户回播 mini-summary,**禁止**默默接续下一个 slug:

```
[1/3] order-create/smoke.sh 完成
  PASS=4 / FAIL=1 / SKIP=0
  失败步骤:
    - 02-create-order:期望 status=PENDING,实际 status=null
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

1. 读 `.harness/smoke-tests/{slug}/.run/result.json` 拿结构化结果(PASS/FAIL/SKIP 计数 + 失败 step 列表 + 每条 FAIL 的 reason)。**不要从 stdout 截取**——result.json 是单一事实源
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
- **每条 FAIL 一节**(`## {slug} / {step-file}`,step-file 取失败 step 的文件名如 `02-create-order.sh`),节内字段固定:
  - **失败时间**(脚本输出中的时间戳)
  - **诊断分类**(失败诊断表四行之一,必须准确填写——决定后续是否进入修复模式)
  - **失败现象**:从 `.harness/smoke-tests/{slug}/.run/run.log` **原样截取**的 FAIL 行
  - **关键日志片段**:`.run/run.log` 中 FAIL 前后各 20 行原文
  - **call-chain**:`.harness/call-chain/{slug}.md`(只填路径,不复制内容)
  - **失败 step**:`.harness/smoke-tests/{slug}/{step-file}`(具体到失败 step,不是 orchestrator)
  - **state.env 快照**:`.harness/smoke-tests/{slug}/.run/state.env`(失败时上下文,builder 修复时可参照)
  - **run.log 快照**:`.harness/smoke-tests/{slug}/.run/run.log`(完整 stdout 落盘,用户中断会话或下次启动后仍可独立查阅)

只引用证据,不臆测原因。原因分析是 builder 的职责,不是 smoke 的。

**唯一性约定**:此后所有读取(是否有真 bug、生成修复 plan)**只从这份文件读**,严禁从 skill 上下文复述。

### 7.2 临时入口清理(条件触发)

**触发条件**:本次冒烟覆盖的任一 slug,其 `00-prepare.md` 含"临时入口文件清单"小节(非空)。

把所有 slug 的临时入口文件路径聚合成一份清单(去重),用 `AskUserQuestion` 让用户三选一:

> 本次冒烟使用了 N 个临时入口(列出文件路径),如何处理?
>
> - **撤销改动(默认)**:对每个文件:
>   - 已被 git tracked → `git checkout HEAD -- {file}` 还原
>   - 新增的未 tracked 文件 → **不自动 `rm`**,而是列出来提示用户手动删除(避免误删用户其他工作)
> - **暂不处理**:文件保留在工作区,由用户自行决定后续(stash / 留到下次冒烟 / 手动整理)
> - **直接提交**:`git add {files} && git commit`(commit message 由用户提供或采用默认 `chore: smoke trigger endpoints for {slug}`)。**默认不 push**——push 是显著动作,需要用户在另一条 `AskUserQuestion` 里再次确认目标 branch

执行完毕后,把清理结果(还原了哪些 / 保留了哪些 / 提交到了哪个 commit)简短回播给用户,作为本次冒烟的尾声。

> 不靠 CI、不靠纪律——临时入口的去留由用户在每次冒烟结束时显式拍板,不留隐患。

### 7.3 复利经验提议(每次冒烟都做)

**触发条件**:每次冒烟结束都做(无论 PASS / FAIL),不依赖修复模式是否触发。

skill 基于本次冒烟现场,**主动提议** 0-3 条候选经验。提议来源:

- 用户在 `wait_user_action` 时输入的**自由文本提示**(口头注意事项、临时补充的步骤说明)
- prepare.md 之外用户**临时补的资源**(如"我额外起了一个 mock 服务"——说明 prepare.md 不全)
- 修复模式触发的**真 bug 类型**(说明该流程对某类问题敏感)
- step_checkpoint 中用户**多次重跑同一 step**(说明该 step 易踩)

每条候选必须给出三要素:`category`(下推荐 5 类之一或新建)、候选 `id`(slug-friendly)、`item` 正文。用 `AskUserQuestion`:

- 「采纳并写入 lessons.xml」
- 「修改后采纳」(进入二次输入,采纳用户改写后的版本)
- 「拒绝」(不写)

**采纳后的合并逻辑**:

- 若 lessons.xml 已存在同 `id` 的 item → 再问一次「**覆盖既有内容** / **追加为新 id**(如 `auth-token-2`) / **拒绝**」
- 写入后更新根节点 `<lessons updated="今日" version="N+1">`
- 文件不存在则先创建,带完整 XML 声明和根节点

**禁止 skill 静默写入**——任何写入必须经用户 `AskUserQuestion` 明确同意。**禁止 skill 自行决定 category/id**——必须先呈现给用户审阅。

> 没有候选可提议时(本次冒烟平淡如水)直接说「本次没有发现值得沉淀的经验,跳过」,不要硬凑。

## 失败诊断

脚本失败时,先诊断再判定。

### 诊断预算(硬约束)

避免 agent 在证据模糊时反复回读上下文空转——这一步本质是判断题,做不到的决策不该被无限延展。每条 FAIL 步骤的诊断必须遵守:

- **证据范围固定**:只读以下 4 份材料,**各读一次,不重复回读**:
  1. 失败 step 脚本本体(`.harness/smoke-tests/{slug}/{step-file}`)
  2. 对应 call-chain(`.harness/call-chain/{slug}.md`)
  3. `state.env` 快照(`.harness/smoke-tests/{slug}/.run/state.env`)
  4. `run.log`(`.harness/smoke-tests/{slug}/.run/run.log`)中 FAIL 行前后各 20 行
- **一轮即决**:读完上述 4 份后必须给出分类结论。**禁止**为"再看一眼"重复 Read/Grep 同一文件、扩大范围读其他 step、回头查 builder/qa 历史。如果发现自己想第二次打开同一份证据,这就是要走"逃生口"的信号
- **判不出来的逃生口**:若一轮读完仍不能稳妥归到下表四类中任意一类,**立即** `AskUserQuestion` 把四个分类做成选项让用户拍板,**禁止继续自行分析**。把已读到的关键证据(2-3 句话)随问题一起给用户,便于用户决策

### 分类表

| 现象 | 处理 |
|------|------|
| **脚本与 call-chain 不一致**(call-chain 改了脚本没跟) | 不自行修脚本。提示用户:「`smoke-tests/{slug}/` 下的 step 与 `.harness/call-chain/{slug}.md` 不一致,请通知 harness-qa 更新冒烟脚本后重跑」 |
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

3. **建立 smoke run 目录**(config.json 必须落在某个 run 目录下,与 harness-backend 规则一致):

   ```bash
   SMOKE_RUN_DIR=".harness/smoke-runs/$(date +%Y%m%d-%H%M%S)"
   mkdir -p "$SMOKE_RUN_DIR"
   ```

4. **启动两个 Agent 的 pane,然后写 config,再发初始 prompt**(三步必须按顺序):

   ```bash
   launch_agent_pane "harness-builder" "harness-builder" "$SMOKE_RUN_DIR/config.json"
   launch_agent_pane "harness-qa"      "harness-qa"      "$SMOKE_RUN_DIR/config.json"
   write_config "$SMOKE_RUN_DIR" ""    # smoke 模式无 plan.md,plan_path 传空字符串
   ```

   随后向两个 agent 发 prompt——内容必须明确以下三点,避免 agent 惯性进入完整迭代流程:

   - **任务文件**:本次「失败记录文件」的绝对路径,只处理诊断分类为「真 bug」的小节
   - **跳过的阶段**:scope 对齐、`build-scope-v{N}` 产出、用户调整、`.harness/done` 写入——**全部跳过**;本批次按"修复阶段"语义直接处理
   - **完成信号**:全部真 bug 修完且 qa 验证通过后,由 qa `touch` ack 文件(内容可空);**不要写 `.harness/done`**;ack 后保持 pane 在线等下一批

   ```bash
   dispatch_initial_prompt "harness-builder" "先在 Bash 工具里跑 \`echo \$HARNESS_CONFIG\` 拿到本次 smoke run 的 config.json 路径并 Read 它(plan_path 为空,本轮没有 plan.md)。本次是冒烟回流的修复任务(不是完整迭代)——任务文件:{失败记录路径};跳过 scope 对齐 / build-scope / 用户调整 / .harness/done;qa 验完一批后写 {ack 路径},pane 保持在线等下一批。"
   dispatch_initial_prompt "harness-qa"      "先在 Bash 工具里跑 \`echo \$HARNESS_CONFIG\` 拿到本次 smoke run 的 config.json 路径并 Read 它(plan_path 为空,本轮没有 plan.md)。本次是冒烟回流的修复验证(不是完整迭代)——任务文件:{失败记录路径};跳过 Scope 审阅 / 评分 / 用户调整 / .harness/done;builder 通知后做修复验证,全部真 bug 通过时由你 touch {ack 路径},pane 保持在线等下一批。"
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
