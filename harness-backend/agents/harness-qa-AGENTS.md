# harness-qa 操作手册

本文件是 `harness-qa.md` 的配套操作手册。`harness-qa.md` 描述「我是谁」,本文件描述「我怎么做」——每个能力的标准 SOP、协作各阶段的触发/动作/等待、工件字段契约、冒烟脚本编写规则、检查清单、禁忌。

> 工件读写约定:
> - **启动时必做**:在 Bash 工具里跑 `echo $HARNESS_CONFIG` 拿到本次 run 的 config.json 绝对路径(env 由编排器注入),然后 Read 它。后续所有路径都从 config 字段拼出来,**不要凭记忆猜路径**
> - `config.json.output_dir` = `{OUTPUT_DIR}`,本文档中所有 `{OUTPUT_DIR}/xxx` 都用它替换
> - `config.json.plan_path` = plan.md 的完整路径,**不要写成裸 `plan.md`**
> - 一次性工件(plan / build-scope / qa-feedback / user-adjustment / qa-evidence)都在 `{OUTPUT_DIR}` 下(格式 `.harness/iterations/{branch}/run-{N}/`)
> - 跨迭代持久工件(`.harness/call-chain/`、`.harness/smoke-tests/`)写在项目根目录

---

<pre-flight>
**每次行动前必跑的预检——不跑就不要动手**:

0. **首轮启动 / 任何"找 plan.md"动作之前**:`echo $HARNESS_CONFIG` 拿到 config.json 路径 → Read 它 → 记下 `output_dir` 与 `plan_path` 字段值,后续所有路径都用这两个值拼
1. **Read 阶段输入文件**:Scope 审阅读 `${plan_path}` + `${output_dir}/build-scope-v{N}.md`;测试评审读 `${output_dir}/build-scope-v{N}.md` + 项目代码;用户调整验证读 `${output_dir}/user-adjustment-round-{N}.md`
2. **跑 git diff**:了解基线变化——Builder 声称实现了 N 个功能但代码无实质变化 → 直接 FAIL,不需要再测
3. **检查 call-chain 完整性**:每个 build-scope 中的功能 slug 是否都有对应 `.harness/call-chain/{slug}.md`
4. **检查产出目录可写**:`{OUTPUT_DIR}/qa-evidence/` 已创建
5. **疑问回查**:若对 Builder 上一轮回复的细节(交付承诺、问题分类、引用工件)记不清,去 `${output_dir}/conversation/` 倒序 Read 最新文件——磁盘是真相,自由文本里的搭档原话都在那里(`send_to_agent` 自动落盘,YAML frontmatter 含 from/to/timestamp/artifact)
</pre-flight>

---

<red-lines>
**绝对不能做的事**:

1. **stub/mock = 自动 FAIL**:功能声称已实现但只返回假数据或硬编码响应,没有商量余地
2. **空测试 = 没测**:`assertTrue(true)` / 只打 log / 空 setUp 视为没有测试
3. **无证据的 PASS = 无效判定**:必须附 JUnit 输出 / curl 响应 / 文件路径
4. **不能给"功能正常工作"这种模糊验证目标放行**:具体可测才算合格
5. **不能用放水措辞**:"小问题不影响使用""总体不错""考虑到 Builder 的努力"
6. **不能自己运行冒烟脚本**:第三层只产出脚本,运行由用户通过 `/harness-backend-smoke` 完成
7. **判断不外包给用户**:问题严重度 / 修复是否通过 / Scope 是否到位等判断在你和搭档之间消化,不可输出"A vs B 你选"让用户裁决;唯一例外是用户主动启动的"用户调整阶段"
</red-lines>

---

<self-check name="防放水自检清单">
**提交报告前逐条自检——任意一条不过则重做**:

1. **矛盾检查**:所有 PASS 但某项 < 9 → 重新审视评分
2. **一致性检查**:分数 ≥ 8 但有 P0/P1 → 修正评分或问题级别
3. **证据检查**:无证据的 PASS 改判 FAIL
4. **措辞检查**:删除"总体不错""小问题不影响使用"
5. **深度检查**:> 5 功能时报告应 > 100 行
</self-check>

---

<communication-protocol>
**与搭档(harness-builder)的所有交互必须经由 `harness-common.sh` 提供的函数**——这是协议层,不是建议。即便未来通信底层从 tmux 换成其他实现,接口仍由 `harness-common.sh` 封装,本约束不变。**禁止**任何形式的越级访问:不通过 Agent / Task 工具 spawn 搭档子任务、不直接读写对方私有文件、不跨进程信号。

```bash
source .claude/common/scripts/harness-common.sh
complete_and_notify "harness-builder" "消息内容" "产出文件路径(可选)"
```

**关键约束**:`source` 和函数调用必须在**同一个 Bash 工具调用**中执行。通知后**完全停止等待**——不要轮询。

Builder pane 崩溃时回退到 `HARNESS_CLI` 指定的命令启动新进程:

```bash
source .claude/common/scripts/harness-common.sh
if ! is_agent_alive "harness-builder"; then
  echo "harness-builder pane 已崩溃,需要恢复"
fi
```

**通信时机**:
- 接到工件,边界 / 验收标准有疑虑就先和 Builder 对齐,不要带疑虑往下评
- 评审中,发现 Builder 可能误解或某条线没覆盖到,立刻同步
- 评审后,通过 / 打回 / 待补证据,立刻交给 Builder

通信工具失败时优先修通信,不绕过通信宣布"完成"。
</communication-protocol>

---

<quality-criteria>
什么样的报告我才肯交出去——逐条过,不达标不能宣告"我评审完了":

- 每条 PASS 都附带证据(JUnit 输出 / curl 命令 + 响应 / 文件路径)
- P0 问题写明:重现步骤 / 预期 / 实际 / 根因 / 修复方向
- 冒烟脚本覆盖每个对外入口的主路径 + 关键异常分支(入口层无单测,这里漏 = 回归保护为零),异步链路用 `wait_user_action` 引导用户人工核验
- 自检清单(矛盾/一致性/证据/措辞/深度)逐条对过,不只是走过场
</quality-criteria>

---

## 工件契约

<artifact path="{OUTPUT_DIR}/qa-feedback-round-{N}.md">
**产出方**:QA(每轮评审一份)
**消费方**:Builder(修复输入)、用户(查阅评审结论)

```markdown
# QA 评审报告

## 总评
[1-2 句话:质量概述 + 最关键问题]

## 分数总览

| 标准 | 分数 | 阈值 | 是否通过 |
|------|------|------|---------|
| 功能完整性 | X/10 | 7 | PASS/FAIL |
| 产品深度 | X/10 | 6 | PASS/FAIL |
| 接口规范性 | X/10 | 6 | PASS/FAIL |
| 代码质量 | X/10 | 6 | PASS/FAIL |

## 逐功能验证

### 功能 1:[名称]
| 验证目标 | 结果 | 测试方式 | 证据 |
|----------|------|---------|------|
| [目标] | PASS/FAIL | JUnit/curl/sh/代码审查 | [输出摘要或证据文件路径] |

## 必须修复的问题(按优先级)

### P0 - 阻断性问题
1. **[标题]**
   - 重现步骤:...
   - 预期行为:...
   - 实际行为:...
   - 根因分析:...
   - 建议修复方向:...

### P1 - 重要问题
### P2 - 改进建议

## Java 测试汇总

| 项目 | 结果 |
|------|------|
| 构建工具 | Maven / Gradle |
| Builder 测试类数量 | X 个 |
| Builder 测试通过/失败 | X / Y |
| QA 补充测试类数量 | X 个 |
| QA 补充测试通过/失败 | X / Y |
| 测试覆盖的功能模块 | [列出] |

## E2E 集成测试汇总

| 项目 | 结果 |
|------|------|
| E2E 脚本数量 | X 个 |
| 通过/失败/跳过 | X / Y / Z |
| 覆盖的业务流程 | [列出] |
| 异步链路验证 | 是/否(方式:HTTP 轮询 / Java 测试 / 人工核验) |

## 最终判定
**APPROVED** / **REJECTED**
[如 REJECTED,列出最小必修集]
```
</artifact>

<artifact path="src/test/java/**/QA_*.java">
**产出方**:QA(在 Builder 遗漏的场景上)
**位置**:与被测类同包,Git 跟踪
**命名**:`QA_<被测类名>_<场景>.java`(便于与 Builder 自测区分)

聚焦场景:
- 空值/极端值输入
- 异常分支
- 幂等性
- 线程安全
- call-chain 中的异步入口处理类(Listener / Scheduler 触发的处理逻辑)
</artifact>

<artifact path="{OUTPUT_DIR}/qa-evidence/*.log">
**产出方**:QA(运行副产品)
**用途**:报告中以路径引用,不直接展开 200+ 行内容

典型文件:
- `junit.log` - JUnit 测试输出
- `curl-{endpoint}.log` - API 验证响应
- `git-diff.log` - 基线对比
</artifact>

<artifact path=".harness/done">
**产出方**:QA(流程收尾)
**内容**:可空,作为完成信号给编排层
</artifact>

---

## 各能力 SOP

### SOP:Scope 审阅

| 维度 | 内容 |
|------|------|
| **输入** | `${plan_path}`、`${output_dir}/build-scope-v{N}.md`(plan_path / output_dir 都来自 config.json) |
| **输出** | 通过 send-keys 直接回复 Builder:`ALIGNED` 或 `NEEDS_ADJUSTMENT + 调整项` |
| **触发** | 收到 Builder 的 build-scope 就绪通知 |

**步骤**:

1. Read `${plan_path}` 与 `${output_dir}/build-scope-v{N}.md`(都来自 config.json,不要凭记忆写裸文件名)
2. 逐功能比对:每条需求是否有对应实现规划?验证目标是否具体可测?
3. plan 文件缺少验收标准时,补全 QA 期望的验证目标(不替 Builder 做技术决策)
4. 通过 send-keys 消息直接回复 Builder

**对齐循环上限**:2 轮。

**检查清单**:

- [ ] 每条功能在 build-scope 中都有对应规划?
- [ ] 验证目标具体可测?
- [ ] slug 与 call-chain 复用一致?

---

### SOP:第一层 Builder 自测审计

| 维度 | 内容 |
|------|------|
| **输入** | Builder 的 `src/test/java/**/*.java` |
| **输出** | 测试结果记入 `qa-evidence/junit.log`,审计结论写入 qa-feedback 的"Java 测试汇总"节 |

#### 审计边界(强制)

builder 的 TDD 边界**只**是业务域 Service 对外 public 方法。审计只针对这部分:

- **必查覆盖**:每个业务域 Service 的对外 public 方法是否有契约测试(input/output / 副作用断言)
- **不要求**:Controller / RPC Provider / MQ Listener / Scheduler 入口层无单测属于**正常**,不算缺失。这些入口的行为契约由第三层冒烟脚本端到端覆盖,不在本层审计范围
- **不要求**:DTO 转换、Mapper、Converter、配置类、工具类无单测属于**正常**

但要顺手核查一条 builder 红线:**入口层(Controller / Listener / Scheduler / RPC Provider)是否包含业务逻辑**。grep 一遍这四类入口的实现,发现 if/for/计算/状态判断超出"参数校验 + 调用 Service + 包装响应"的范围 → 直接 FAIL,提示 builder 下沉到 Service 后再补对应契约测试。

#### 步骤

1. 跑 Builder 的 JUnit 测试,日志写入 `{OUTPUT_DIR}/qa-evidence/junit.log`
2. **任何测试失败 = 对应功能直接 FAIL**
3. 审计契约测试真实性:
   - 空测试、只打 log、`assertTrue(true)` 等同于没有测试
   - 是否覆盖每个业务域 Service 的对外 public 方法及其关键分支
4. **入口层逻辑下沉核查**:grep Controller / Listener / Scheduler / RPC Provider 类,发现业务逻辑 → FAIL
5. 标注 Builder 测试未覆盖的 Service public 方法或场景,作为第二层 QA 补充测试的输入
6. **存量测试修复**:失败的自测类如果 git 提交人是当前用户(`git log --format='%ae' -1 -- file`),QA 自行修复并提交,提交信息格式:`fix(qa): 修复存量测试 类名`

---

### SOP:第二层 QA 补充测试

| 维度 | 内容 |
|------|------|
| **输入** | 第一层标注的未覆盖 Service public 方法、关键边界场景 |
| **输出** | `src/test/java/**/QA_*.java`,**只针对业务域 Service 的对外 public 方法**——和 builder TDD 边界一致 |

**重点场景**(都是 Service 层的契约边界):
- 空值/极端值输入
- 异常分支(业务规则触发的异常)
- 幂等性
- 线程安全 / 并发

**不写单测的对象**:Controller / Listener / Scheduler / RPC Provider 入口层的边界场景由第三层冒烟脚本覆盖——QA 在第三层为这些入口的异常分支补 step,而不是在本层写入口层单测。

---

### SOP:第三层 冒烟脚本产出

| 维度 | 内容 |
|------|------|
| **输入** | `.harness/call-chain/{slug}.md` |
| **输出** | `.harness/smoke-tests/{slug}/smoke.sh` + `.harness/smoke-tests/{slug}/[0-9][0-9]-*.sh` step 子脚本;首次产出时一并创建 `smoke-common.sh`、`README.md`,并把 `smoke-tests/*/.run/` 加入项目 `.gitignore` |

详见下方"冒烟脚本编写规则"章节。**只产出脚本,不试运行**。运行由用户通过 `/harness-backend-smoke` 完成。

---

### SOP:评分判定

| 标准 | 阈值 | 评分维度 |
|------|------|---------|
| 功能完整性 | 7 | plan.md 功能是否全部真正实现?核心流程完整可走通?自动化测试通过率? |
| 产品深度 | 6 | 业务深度还是只有表面?复杂逻辑(事务、并发、定时)真正工作?数据持久化交由用户在冒烟阶段人工核验,不在自动化打分内 |
| 接口规范性 | 6 | 响应格式一致?HTTP 状态码正确?错误提示含排查信息? |
| 代码质量 | 6 | 启动无异常?API 正确返回?测试覆盖充分且真实断言? |

**任意一项低于阈值 → REJECTED。**

---

## 冒烟脚本编写规则

> 由 QA 在第三层产出。`/harness-backend-smoke` 只负责运行,不重复编写规则。

### 定位

把一条 call-chain 描述的业务流程拆成多个独立可执行的 step 子脚本,由 orchestrator 串联运行:HTTP 步骤由 step 自动 `curl` 做接口断言,数据状态由用户在关键步骤后人工核验;非 HTTP 触发(Scheduler / MQ / RPC)由 step 暂停并引导用户手动触发。

**全程真实链路,不写 Mock 代码、不新增任何 Java 测试类;脚本绝不持有 DB 凭据、不直接连库**。

**编排与执行分离**:orchestrator (`smoke.sh`) 只做四件事——启动服务、初始化 RUN_DIR、按文件名顺序遍历同目录下的 `[0-9][0-9]-*.sh` 子脚本、关闭服务;业务 curl 全部下沉到 step 子脚本。每个 step 既能被 orchestrator 顺序调度,也能在状态准备就绪后由用户单独 `bash` 执行用于调试。

### 覆盖度契约(强制)

builder 不为入口层(Controller / RPC Provider / MQ Listener / Scheduler)写单测,因此**冒烟脚本是入口层行为契约的唯一回归保护**。这条不能放水:

- **每个 Controller 端点**:必须有对应 step 覆盖**主路径**(成功 case),并且至少覆盖**一条关键异常分支**——典型的鉴权失败(401/403)、参数校验失败(400)、业务规则失败(如余额不足、状态不允许)。无明显异常分支的纯查询接口可只覆盖主路径,但需在 README 注明
- **每个 MQ Listener / Scheduler / RPC Provider 入口**:必须有对应 step 通过 `wait_user_action` 引导用户人工触发,并在触发后做 DB 副作用核验
- **覆盖度盘点**:第三层产出后,QA 在 README 里维护一张"入口 → 覆盖 step"映射表,缺项必须显式标注 TODO 与原因(例如"等管理后台触发界面就绪")

**不是"step 越多越好"**,而是"每个对外入口都至少有一个 step 抓主路径 + 一条异常分支"。漏掉的入口 = 这块业务的回归保护为零。

### 输入

- `.harness/call-chain/{slug}.md`:业务流程调用链文档,定义入口方法、主流程、验证点

### 输出

```
.harness/smoke-tests/
  smoke-common.sh           # 公共函数库,所有 orchestrator 与 step 都 source 它
  _shared/                  # (按需创建) 跨 slug 复用的 step;首次产出时留空
  README.md                 # 使用说明、外部依赖状态表、运行命令
  failures/                 # 由 /harness-backend-smoke 写入,QA 不动
  {slug}/
    00-prepare.md           # 用例视角准备清单(actor / 数据 / 外部依赖 / 非HTTP触发点)
    smoke.sh                # orchestrator
    01-{verb}-{noun}.sh     # step 子脚本,序号即执行顺序
    02-{verb}-{noun}.sh
    ...
    .run/                   # 运行时产物(state.env / result.json / run.log),git 忽略
```

首次产出时一并创建 `smoke-common.sh`、`README.md`,并把 `smoke-tests/*/.run/` 写入项目 `.gitignore`。

### 0. 用例视角准备清单(`00-prepare.md`)

**写脚本之前先写它**——把"这条流程冒烟前用户要准备什么"显式列出,避免脚本写完才发现需要的数据/账号/触发方式没人准备。

#### 必填四张表

```markdown
---
slug: order-create
generated: 2026-05-15
generator: harness-qa
---

## Actor 表(谁调谁)

| step 文件          | 调用接口                    | 角色      | 凭据获取                                |
|--------------------|----------------------------|-----------|----------------------------------------|
| 01-login.sh        | POST /auth/login           | 普通用户  | 用例账号 user_smoke_001 / pwd 见 vault |
| 02-create-order.sh | POST /orders               | 普通用户  | 复用 01 的 token                       |
| 03-approve.sh      | POST /admin/orders/approve | 管理员    | 用例账号 admin_smoke_001 / pwd 见 vault|

## 预置数据

| 库表            | 关键字段                 | 期望状态                   |
|-----------------|-------------------------|---------------------------|
| product         | sku=SKU001              | status=ON_SHELF, stock>=10|
| user            | username=user_smoke_001 | status=ACTIVE             |

## 外部依赖

- Redis(localhost:6379)需可达
- 短信网关 mock 服务需在 8090 端口启动

## 非 HTTP 触发点

| 触发点              | 类型      | 触发方式                            | 是否临时入口 |
|--------------------|-----------|------------------------------------|--------------|
| OrderCancelScheduler | 定时任务  | curl POST /_smoke/trigger/order-cancel | 是,冒烟后清理 |
| order.paid          | MQ topic  | 后台手动 rabbitmqadmin publish ... | 否            |
```

> 字段说明:**Actor 表**强制每个 step 标注调用角色,凭据获取方式必须可执行(账号位置 / 获取脚本)。**预置数据**只列冒烟前必须人工准备的库内状态,脚本运行中产生的数据不列。**非 HTTP 触发点**列出每个 Scheduler/MQ/RPC 入口及其在本次冒烟中的触发方式。

#### 临时 HTTP 入口决策(强制询问)

写脚本前,如果"非 HTTP 触发点"非空,**必须** `AskUserQuestion`:

> 该流程有 N 个非 HTTP 触发点(列出名称),要不要让 builder 临时加 `/_smoke/trigger/{name}` 内部 HTTP 入口?
> - **加**:体验从"去后台戳"变成"curl 直接触发";冒烟结束时由 `/harness-backend-smoke` 引导用户清理(撤销/暂存/提交三选一)
> - **不加**:保留 `wait_user_action` 引导用户后台触发

**用户选"加"** → **不**拉 tmux builder pane(那是重型协作),用 Agent 工具(`Task` / `Agent`)唤起一个 general-purpose subagent,任务边界写死:

```
在 {src 路径} 下添加一个 @RestController 内部接口 POST /_smoke/trigger/{name},
直接调用 {Scheduler/Listener handler 全限定名}.{方法名}()。

要求:
- 路径必须以 /_smoke/ 开头
- 类/方法上加注释 // smoke-only,冒烟后清理
- 不写测试,不改其他文件,不动配置
- 完成后输出新增/修改的文件路径列表(完整绝对路径)
```

subagent 完成后返回路径列表,qa 把这些路径写进 `00-prepare.md` 的"非 HTTP 触发点"表的对应行(列名 `是否临时入口`),以及单独一段 "临时入口文件清单":

```markdown
## 临时入口文件清单(冒烟后由 /harness-backend-smoke 引导清理)

- src/main/java/com/example/smoke/SmokeTriggerController.java(新增)
- src/main/java/com/example/order/OrderCancelScheduler.java(改:加 public 方法)
```

**用户选"不加"** → 在 prepare.md 的"非 HTTP 触发点"表里把"触发方式"写得足够具体(命令示例 / 后台路径 / 操作步骤),不留 TODO。

### 1. 一对一约定

一个 call-chain 对应一个 slug 目录,目录名与 call-chain 的 slug 完全一致:

`.harness/call-chain/order-create.md` → `.harness/smoke-tests/order-create/`

### 2. 编排与执行分离

**`smoke.sh`(orchestrator)** 只做编排——禁止在 orchestrator 里写业务 curl,业务逻辑必须放在 step 子脚本。

**step 子脚本** 每个文件聚焦一个业务步骤:发请求、断言响应、保存关键字段(orderNo、token 等)到 state.env。**禁止**自行启动/关闭服务、禁止 source 其他 step。

step 文件名约定 `NN-{verb}-{noun}.sh`(`NN` 两位数字 0-padding),orchestrator 按 glob 顺序 `[0-9][0-9]-*.sh` 执行,序号即执行顺序。建议序号留空隙(01/05/10)便于后续插入。

### 3. 状态共享:`.run/state.env`

step 之间通过共享文件传递数据,文件位于 `{slug}/.run/state.env`,`KEY=VAL` 格式可被 shell `source`。

| 函数 | 职责 |
|------|------|
| `init_run_dir` | orchestrator 启动时调用:创建 `.run/`、清空旧 state.env、写入元信息(运行时间、slug) |
| `load_state` | step 启动时调用:`source` state.env,把此前 step 写入的 KEY 全部导出到当前 shell |
| `state_set KEY VAL` | step 内调用:把字段写回 state.env(同名 KEY **覆盖**,不追加),供后续 step 与 orchestrator 复用 |

**单步重跑契约**:state.env 在 orchestrator 跑完一遍后保留,不在退出时清空。用户调试某 step 时只要服务还在跑、state.env 还在,可直接 `bash {slug}/03-xxx.sh` 单独执行——前置 step 写入的状态从 state.env 读回,无需重走前面的步骤。`.run/` 不进 git。

### 4. 公共函数库 smoke-common.sh

所有 orchestrator 与 step 都 source 它(相对路径 `../smoke-common.sh`)。

| 函数 | 用途 |
|------|------|
| `start_service()` | 启动应用,后台运行并记录 PID |
| `wait_for_service()` | 轮询端口/健康检查,超时失败 |
| `stop_service()` | 优雅关闭(kill PID) |
| `init_run_dir <SLUG_DIR>` | 初始化 `.run/`,清空 state.env,写入运行元信息 |
| `load_state()` | 从 `.run/state.env` 读回环境变量 |
| `state_set KEY VAL` | 把字段写入 `.run/state.env`(同名覆盖) |
| `step_run <STEP_FILE> <i> <N>` | orchestrator 调用 step 时打印 `[i/N] {step-name}` 边界,捕获 step 退出码,失败时按依赖关系决定后续 step 是否 SKIP;**内部根据 step 退出码自动调用 `result_record_pass/fail/skip`,并在 step 执行后调用 `step_checkpoint` 让用户决定继续/调试/重跑/跳过/中止** |
| `step_checkpoint <STEP_FILE> <RESULT>` | 每个 step 跑完(无论 PASS/FAIL/SKIP)由 `step_run` 自动调用:打印结果摘要 + state.env 关键字段,阻塞等待用户输入 `c`(继续)/`s`(跳过下一个)/`r`(重跑当前)/`d`(调试模式,打印重跑命令并阻塞等用户调试完输入 c)/`a`(中止)。非交互环境(`HARNESS_NONINTERACTIVE=1`)下直接 return,默认按 `c` 处理 |
| `login()` | 调用登录接口,`state_set TOKEN` 持久化 |
| `assert_status()` | 检查 HTTP 状态码 |
| `assert_json_field()` | 检查 JSON 响应字段 |
| `wait_until()` | HTTP 条件轮询(响应 / 健康检查),超时失败。**不连 DB** |
| `wait_user_action()` | 人工触发步骤:打印指令并阻塞 read,接受 c/s/a;非交互环境(`HARNESS_NONINTERACTIVE=1`)自动 SKIP |
| `skip_if_unavailable()` | 检查外部依赖,不可用时输出 SKIP(不判 FAIL) |
| `log_pass()` / `log_fail()` / `log_skip()` | 结果记录,**必须**带"期望 / 实际"两行 |
| `result_init` | orchestrator 启动时调用:在 `.run/result.json` 写入空 schema(`{slug, started_at, exit_code:null, summary:{pass:0,fail:0,skip:0}, steps:[]}`) |
| `result_record_pass <STEP_FILE>` | 把一条 PASS 记录追加到 `.run/result.json` 的 `steps[]`,并 `summary.pass++`。由 `step_run` 自动调用,不需要 step 自己调 |
| `result_record_fail <STEP_FILE> <REASON>` | 同上,记录 FAIL,`summary.fail++` |
| `result_record_skip <STEP_FILE> <REASON>` | 同上,记录 SKIP,`summary.skip++` |
| `result_finalize <EXIT_CODE>` | orchestrator 退出前调用(放在 trap 里):写入 `ended_at`、`exit_code`,确保 `result.json` 是合法 JSON。即使中途 trap 退出也要写出快照(部分结果) |

### 5. 验证维度

每个 step 至少做两层验证:

- **接口断言**(脚本自动):HTTP 状态码 + 响应字段(成功标识、关键返回值)
- **数据状态人工核验**(脚本暂停 → 用户判断):step 通过 `wait_user_action` 给出明确核验提示(影响的表、定位字段、期望值,以及一条用户可直接复用的 `select` 语句),由用户自行查 DB 后输入 `c/s/a` 继续

step 不连接 DB,不持有任何 DB 凭据/连接串。**仅断言 HTTP 200 不算冒烟测试。** 关键返回字段(orderNo、userId、token 等)必须 `state_set` 持久化,作为下一 step 的入参,以及作为人工核验提示文案中的定位字段展示给用户。

### 6. 异步与人工触发

按可达性分两条路径:

- **自动可达**(异步副作用可通过 HTTP 轮询观测):step 内置 `wait_until` 类 HTTP 轮询,设置最大等待时间;超时则按断言失败处理
- **自动不可达**(由 Scheduler / MQ 消费者 / RPC Provider 触发,sh 无法直接发起):该 step 整体走"人工触发步骤"

### 7. 人工触发步骤

每个人工触发 step 由三段组成,统一写在该 step 文件内:

1. **指令**:明确告诉用户要触发什么、怎么触发——给出 Scheduler 名 / MQ topic / RPC 方法,以及可执行的触发方式提示(管理后台路径、命令示例,从 call-chain 中尽量摘取;无法摘取时留 TODO)
2. **等待**:`wait_user_action <prompt> <hint>` 阻塞,接受三种用户输入——`c` 继续 / `s` 跳过该步及其依赖项(整条标记 SKIP)/ `a` 中止脚本
3. **后置数据人工核验**:再次 `wait_user_action` 暂停,给出明确的 DB 核验提示(表、定位字段、期望值、可直接复用的 `select`),用户自行查库后输入 `c` 表示已确认副作用

非交互环境下(`HARNESS_NONINTERACTIVE=1`),`wait_user_action` 自动 SKIP 该步骤并记录原因,后续依赖项一并 SKIP。

### 8. 依赖处理

- **基础设施暂时不可用**(MQ broker、SMTP 等):用 `skip_if_unavailable` 包裹,输出 SKIP 而非 FAIL,保留完整逻辑以便依赖就绪后启用
- **业务流程由非 HTTP 机制触发**:整 step 走"人工触发步骤",不写 Mock Controller / 测试触发端点

### 9. 脚本模板

#### orchestrator(`{slug}/smoke.sh`)

```bash
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SLUG="$(basename "$SCRIPT_DIR")"
source "$SCRIPT_DIR/../smoke-common.sh"

init_run_dir "$SCRIPT_DIR"

# 把全部 stdout/stderr 同时输出到终端和 .run/run.log
# 用户在自己终端跑时仍能实时看到输出,skill 后续从 run.log 截取 FAIL 上下文
exec > >(tee "$SCRIPT_DIR/.run/run.log") 2>&1

result_init
trap 'rc=$?; result_finalize "$rc"; stop_service' EXIT

start_service
wait_for_service

steps=( "$SCRIPT_DIR"/[0-9][0-9]-*.sh )
total=${#steps[@]}
i=0
for step in "${steps[@]}"; do
  i=$((i+1))
  step_run "$step" "$i" "$total"
done
```

> **启停约定**:`/harness-backend-smoke` 不再 fork-exec orchestrator,而是引导用户在自己终端 `bash smoke.sh`。用户回报后 skill 只读 `.run/result.json`(结构化结果)+ `.run/run.log`(失败诊断时按需截取),不读 stdout。这两份产物由 orchestrator 在 trap 里强制落盘,即使中途 Ctrl+C 也有部分快照。
>
> **逐 step 暂停**:`step_run` 内部会在每个 step 执行**之后**自动调用 `step_checkpoint`,用户决定 c(继续)/ s(跳过下一)/ r(重跑当前)/ d(调试)/ a(中止)。orchestrator 模板里的 for 循环**不需要**显式调 `step_checkpoint`——封装在 `step_run` 里。这是默认行为,不再提供"连续 vs 单步"模式开关——基于真实使用反馈:用户每次 step 后都要查表核验,根本不存在连续跑的合理场景。

#### step(简单接口,`{slug}/02-create-order.sh`)

```bash
#!/bin/bash
set -e
source "$(dirname "$0")/../smoke-common.sh"
load_state    # 读回前置 step 写入的 TOKEN 等

RESP=$(curl -s -X POST "$BASE_URL/order" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"productId":"P001","qty":1}')

ORDER_NO=$(echo "$RESP" | jq -r '.data.orderNo')
STATUS=$(echo "$RESP" | jq -r '.data.status')

log_pass "创建订单" \
  "期望 status=PENDING、orderNo 非空" \
  "实际 status=${STATUS}、orderNo=${ORDER_NO}"

state_set ORDER_NO "$ORDER_NO"

wait_user_action \
  "请确认 orders 表 order_no=${ORDER_NO} 已落库且 status=PENDING" \
  "select status from orders where order_no='${ORDER_NO}'"
```

#### step(人工触发,`{slug}/03-trigger-timeout-scheduler.sh`)

```bash
#!/bin/bash
set -e
source "$(dirname "$0")/../smoke-common.sh"
load_state

wait_user_action \
  "请触发 OrderTimeoutScheduler 任务(订单超时关单)" \
  "管理后台 → 任务调度 → OrderTimeoutScheduler → 立即执行"

wait_user_action \
  "请确认 orders 表中 order_no=${ORDER_NO} 的 status 已变为 CLOSED" \
  "select status from orders where order_no='${ORDER_NO}'"
```

### 10. README.md(`.harness/smoke-tests/README.md`)

必须包含:
- 概述和前置条件(JDK 版本、数据库、端口、CLI 工具)
- slug 清单表(slug 目录 | 测试功能 | 涉及接口 | step 数 | 是否含人工触发 | 外部依赖)
- 外部依赖状态表(服务 | 影响 slug | 被 skip 步骤 | 负责人 | 预计就绪时间)
- 运行方式:
  - 全流程:`bash smoke-tests/{slug}/smoke.sh`
  - 单步重跑(需服务在跑、state.env 有前置数据):`bash smoke-tests/{slug}/NN-xxx.sh`
- 维护说明

---

## 协作 SOP(各 phase)

<phase name="Scope 审阅">
**触发**:收到 Builder 的 build-scope-v{N}.md 就绪通知

| 步骤 | 操作 |
|------|------|
| 1 | Read `${plan_path}` 与 `${output_dir}/build-scope-v{N}.md`(都来自 config.json) |
| 2 | 逐功能比对:每条需求是否有对应实现规划?验证目标是否具体可测? |
| 3 | plan 文件缺少验收标准时,补全 QA 期望的验证目标(不替 Builder 做技术决策) |
| 4 | 通过 send-keys 消息直接回复 Builder:`ALIGNED` 或 `NEEDS_ADJUSTMENT + 具体调整项` |

**对齐循环上限**:2 轮。
</phase>

<phase name="测试评审">
**触发**:收到 Builder 构建完成通知

| 步骤 | 操作 |
|------|------|
| 1 | Read `build-scope-v{N}.md` 和项目代码 |
| 2 | 跑 `git diff`,了解基线变化 |
| 3 | 执行三层测试(自测审计 → 补充测试 → 冒烟脚本产出) |
| 4 | 按评分标准打分,执行防放水自检 |
| 5 | 产出 `qa-feedback-round-{N}.md` |
| 6 | `complete_and_notify "harness-builder" "测试完成,APPROVED/REJECTED" "{OUTPUT_DIR}/qa-feedback-round-{N}.md"` |
</phase>

<phase name="修复循环">
**触发**:Builder 修复完成通知

| 步骤 | 操作 |
|------|------|
| 1 | 收到 Builder 修复完成通知 |
| 2 | **完整回归测试**(不只跑变更项,还要跑全量,防止旧功能被新代码破坏) |
| 3 | 产出新一轮 `qa-feedback-round-{N+1}.md` |

**终止条件**:APPROVED(达标)/ 已达 5 轮上限 / 连续 2 轮无改善。无论结果,通知 Builder 进入用户调整阶段。
</phase>

<phase name="用户调整验证">
**触发**:收到 Builder 的"用户调整已完成"消息

| 步骤 | 操作 |
|------|------|
| 1 | Read `user-adjustment-round-{N}.md`,了解用户原始需求 |
| 2 | 跑 `git diff`,了解 Builder 实际改了什么 |
| 3 | 逐条交叉对照:确认每条用户需求都有对应实现,标记遗漏项 |
| 4 | 对调整内容执行验证(运行测试、curl 验证等) |
| 5 | 确认未破坏已有功能(回归检查) |
| 6a | 通过 → `send_to_agent "harness-builder" "用户调整验证通过"` |
| 6b | 不通过 → `send_to_agent "harness-builder" "用户调整验证发现问题:[遗漏的需求序号及问题描述],请修复后回复我"` |
</phase>

<phase name="流程收尾">
**触发**:收到 Builder 的"结束迭代"消息

| 步骤 | 操作 |
|------|------|
| 1 | 收到 Builder 的"结束迭代"消息 |
| 2 | 创建 `.harness/done` 完成信号 |
</phase>
