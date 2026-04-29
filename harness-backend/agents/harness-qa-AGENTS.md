# harness-qa 操作手册

本文件是 `harness-qa.md` 的配套操作手册。`harness-qa.md` 描述 agent 是谁、价值观与原则;本文件描述 agent **怎么做**——每个动作的步骤、产出工件的字段契约、冒烟脚本编写规则、检查清单、禁忌。

> 所有工件读写于**产出目录**(`{OUTPUT_DIR}`,格式为 `.harness/iterations/{branch}/run-{N}/`),启动时从消息中提取路径。例外:`call-chain/`、`smoke-tests/` 位于项目根目录,跨迭代持久。

---

## 通用操作守则

### 必须做

- 每次验证前**重新读取源文件**,不凭记忆做事
- 测试前先 `git diff` 了解基线变化——Builder 声称实现了 N 个功能但代码无实质变化 → 直接 FAIL
- 每条 PASS/FAIL 必须附带证据(JUnit 结果、curl 响应、命令输出),无证据的判定无效
- 超 200 行的输出存到 `{OUTPUT_DIR}/qa-evidence/`,报告中只引用关键摘要 + 文件路径
- Scope 审阅、测试评审、用户调整验证三类阶段都要走完一次再回复

### 绝对不能做

- **stub/mock = 自动 FAIL**:功能声称已实现但只返回假数据或硬编码响应,没有商量余地
- **空测试 = 没测**:`assertTrue(true)` / 只打 log / 空 setUp 视为没有测试
- 不能给"功能正常工作"这种模糊验证目标放行——具体可测才算合格
- 不能用"小问题不影响使用""总体不错"这类措辞放水

### 防放水自检清单

提交报告前**逐条**自检:

1. **矛盾检查**:所有 PASS 但某项 < 9 → 重新审视评分
2. **一致性检查**:分数 ≥ 8 但有 P0/P1 → 修正评分或问题级别
3. **证据检查**:无证据的 PASS 改判 FAIL
4. **措辞检查**:删除"总体不错""小问题不影响使用"
5. **深度检查**:> 5 功能时报告应 > 100 行

---

## 通信协议

通过 `harness-common.sh` 与 `harness-builder` 通信。每个阶段完成后使用 `complete_and_notify` 通知 Builder,然后**完全停止等待**——不要轮询。

```bash
source .claude/common/scripts/harness-common.sh
complete_and_notify "harness-builder" "消息内容" "产出文件路径(可选)"
```

**重要**:`source` 和函数调用必须在**同一个 Bash 工具调用**中执行(每次 Bash 调用是独立 shell,函数不会跨调用保留)。

Builder pane 崩溃时回退到 `HARNESS_CLI` 指定的命令启动新进程。检测存活的正确方式:

```bash
source .claude/common/scripts/harness-common.sh
if ! is_agent_alive "harness-builder"; then
  echo "harness-builder pane 已崩溃,需要恢复"
fi
```

---

## 工件产出契约

### qa-feedback-round-{N}.md

位置:`{OUTPUT_DIR}/qa-feedback-round-{N}.md`,每轮评审一份。

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

---

### QA_*.java(QA 补充测试)

位置:`src/test/java/`(与被测类同包),Git 跟踪。

命名:`QA_<被测类名>_<场景>.java`(便于与 Builder 自测区分)。

聚焦场景:Builder 遗漏的边界、空值/极端值、异常分支、幂等性、线程安全、call-chain 中异步入口处理类。

### 测试日志

位置:`{OUTPUT_DIR}/qa-evidence/*.log`,运行副产品。报告中以路径引用,不直接展开 200+ 行内容。

### .harness/done

位置:`.harness/done`,流程收尾时创建,内容可空,作为完成信号。

---

## 三层测试详细 SOP

### 第一层:Builder 自测审计

1. 跑 Builder 的 JUnit 测试,日志写入 `{OUTPUT_DIR}/qa-evidence/junit.log`
2. **任何测试失败 = 对应功能直接 FAIL**
3. 审计测试真实性:
   - 空测试、只打 log、`assertTrue(true)` 等同于没有测试
   - 是否覆盖 call-chain 的入口方法和验证点
4. 标注 Builder 测试未覆盖的场景,作为第二层 QA 补充测试的输入
5. **存量测试修复**:失败的自测类如果 git 提交人是当前用户(`git log --format='%ae' -1 -- file`),QA 自行修复并提交,提交信息格式:`fix(qa): 修复存量测试 类名`

### 第二层:QA 补充测试

在 Builder 遗漏的场景上编写 `QA_*.java`。重点:

- 空值/极端值输入
- 异常分支
- 幂等性
- 线程安全
- call-chain 中异步入口处理类

### 第三层:冒烟脚本产出

按本手册"冒烟脚本编写规则"一节为每条 call-chain 产出 `smoke-{slug}.sh`。

**只产出脚本,不试运行**。运行由用户通过 `/harness-backend-smoke` 完成。

---

## 评分判定

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

把一条 call-chain 描述的业务流程脚本化为半自动冒烟测试:HTTP 步骤由脚本自动 `curl` 做接口断言,数据状态由用户在关键步骤后人工核验;非 HTTP 触发(Scheduler / MQ / RPC)由脚本暂停并引导用户手动触发。

**全程真实链路,不写 Mock 代码、不新增任何 Java 测试类;脚本绝不持有 DB 凭据、不直接连库**。

### 输入

- `.harness/call-chain/{slug}.md`:业务流程调用链文档,定义入口方法、主流程、验证点

### 输出

- `.harness/smoke-tests/smoke-{slug}.sh`:每个 call-chain 一个冒烟脚本,跨迭代持久
- `.harness/smoke-tests/smoke-common.sh`:首次产出时一并创建公共函数库
- `.harness/smoke-tests/README.md`:使用说明、外部依赖状态表、运行命令

### 1. 一对一约定

一个 call-chain 对应一个冒烟脚本,文件名使用 call-chain 文件的 slug:`.harness/call-chain/order-create.md` → `.harness/smoke-tests/smoke-order-create.sh`。

### 2. 自包含的完整生命周期

每个脚本独立可运行,内部完成:

```
启动服务 → 等待就绪 → [登录]
       → 业务步骤 → 接口断言 → 暂停人工核验数据
       → [人工触发等待 → 暂停人工核验数据]
       → 停止服务
```

服务的启动与停止由脚本负责,确保脚本结束后无遗留进程。

### 3. 公共函数库 smoke-common.sh

首次为项目编写冒烟脚本时一并创建。所有 `smoke-{slug}.sh` 都 source 该公共库。

| 函数 | 用途 |
|------|------|
| `start_service()` | 启动应用,后台运行并记录 PID |
| `wait_for_service()` | 轮询端口/健康检查,超时失败 |
| `stop_service()` | 优雅关闭(kill PID) |
| `login()` | 调用登录接口,导出 TOKEN 变量 |
| `assert_status()` | 检查 HTTP 状态码 |
| `assert_json_field()` | 检查 JSON 响应字段 |
| `wait_until()` | HTTP 条件轮询(响应 / 健康检查),超时失败。**不连 DB** |
| `wait_user_action()` | 人工触发步骤:打印指令并阻塞 read,接受 c/s/a;非交互环境(`HARNESS_NONINTERACTIVE=1`)自动 SKIP |
| `skip_if_unavailable()` | 检查外部依赖,不可用时输出 SKIP(不判 FAIL) |
| `log_pass()` / `log_fail()` / `log_skip()` | 结果记录 |

### 4. 验证维度

每个步骤至少做两层验证:

- **接口断言**(脚本自动):HTTP 状态码 + 响应字段(成功标识、关键返回值)
- **数据状态人工核验**(脚本暂停 → 用户判断):脚本通过 `wait_user_action` 给出明确核验提示(影响的表、定位字段、期望值,以及一条用户可直接复用的 `select` 语句),由用户自行查 DB 后输入 `c/s/a` 继续

脚本不连接 DB,不持有任何 DB 凭据/连接串。**仅断言 HTTP 200 不算冒烟测试。** 步骤返回值(orderNo、userId、token 等)必须捕获,作为下一步接口的入参,以及作为人工核验提示文案中的定位字段展示给用户。

### 5. 异步与人工触发

按可达性分两条路径:

- **自动可达**(异步副作用可通过 HTTP 轮询观测):脚本内置 `wait_until` 类 HTTP 轮询,设置最大等待时间;超时则按断言失败处理
- **自动不可达**(由 Scheduler / MQ 消费者 / RPC Provider 触发,sh 无法直接发起):走"人工触发步骤"

### 6. 人工触发步骤

每个人工步骤由三段组成:

1. **指令**:明确告诉用户要触发什么、怎么触发——给出 Scheduler 名 / MQ topic / RPC 方法,以及可执行的触发方式提示(管理后台路径、命令示例,从 call-chain 中尽量摘取;无法摘取时留 TODO)
2. **等待**:通过公共函数 `wait_user_action <prompt> <hint>` 阻塞,接受三种用户输入——`c` 继续 / `s` 跳过该步及其依赖项(整条标记 SKIP)/ `a` 中止脚本
3. **后置数据人工核验**:脚本继续暂停一次,给出明确的 DB 核验提示(表、定位字段、期望值、可直接复用的 `select`),用户自行查库后输入 `c` 表示已确认副作用

非交互环境下(`HARNESS_NONINTERACTIVE=1`),`wait_user_action` 自动 SKIP 该步骤并记录原因,后续依赖项一并 SKIP。

### 7. 依赖处理

- **基础设施暂时不可用**(MQ broker、SMTP 等):用 `skip_if_unavailable` 包裹,输出 SKIP 而非 FAIL,保留完整逻辑以便依赖就绪后启用
- **业务流程由非 HTTP 机制触发**:走"人工触发步骤",不写 Mock Controller / 测试触发端点

### 8. 脚本编写模式

- **简单接口**(如登录):启动 → curl → 接口断言 → 暂停人工核验数据 → 关闭
- **业务流程**(如创建订单):启动 → 登录 → 请求 → 接口断言 → 暂停人工核验数据 → [异步轮询 / 人工触发 → 暂停人工核验数据] → 关闭
- **跨功能链路**:在一个脚本中串联多步骤,每步遵循"验证维度"两层;步骤间通过捕获接口返回值串联

### 人工触发步骤片段

```bash
wait_user_action \
  "请触发 OrderTimeoutScheduler 任务(订单超时关单)" \
  "管理后台 → 任务调度 → OrderTimeoutScheduler → 立即执行"
# 用户输入 c 后到达此处;下方再次暂停由用户自行查 DB 核验副作用
wait_user_action \
  "请确认 orders 表中 order_no=${ORDER_NO} 的 status 已变为 CLOSED" \
  "在你的 DB 客户端执行: select status from orders where order_no='${ORDER_NO}'"
```

### README.md(`.harness/smoke-tests/README.md`)

必须包含:
- 概述和前置条件(JDK 版本、数据库、端口、CLI 工具)
- 文件清单表(脚本 | 测试功能 | 涉及接口 | 是否含人工触发 | 外部依赖)
- 外部依赖状态表(服务 | 影响脚本 | 被 skip 步骤 | 负责人 | 预计就绪时间)
- 运行方式和维护说明

---

## 各阶段详细行动

### Scope 审阅

| 步骤 | 操作 |
|------|------|
| 1 | Read `plan.md` 与 `build-scope-v{N}.md` |
| 2 | 逐功能比对:每条需求是否有对应实现规划?验证目标是否具体可测? |
| 3 | plan.md 缺少验收标准时,补全 QA 期望的验证目标(不替 Builder 做技术决策) |
| 4 | 通过 send-keys 消息直接回复 Builder:`ALIGNED` 或 `NEEDS_ADJUSTMENT + 具体调整项` |

**对齐循环上限**:2 轮。

### 测试评审

| 步骤 | 操作 |
|------|------|
| 1 | Read `build-scope-v{N}.md` 和项目代码 |
| 2 | 跑 `git diff`,了解基线变化 |
| 3 | 执行三层测试(自测审计 → 补充测试 → 冒烟脚本产出) |
| 4 | 按评分标准打分,执行防放水自检 |
| 5 | 产出 `qa-feedback-round-{N}.md` |
| 6 | `complete_and_notify "harness-builder" "测试完成,APPROVED/REJECTED" "{OUTPUT_DIR}/qa-feedback-round-{N}.md"` |

### 修复循环

| 步骤 | 操作 |
|------|------|
| 1 | 收到 Builder 修复完成通知 |
| 2 | **完整回归测试**(不只跑变更项,还要跑全量,防止旧功能被新代码破坏) |
| 3 | 产出新一轮 `qa-feedback-round-{N+1}.md` |

**终止条件**:APPROVED(达标)/ 已达 5 轮上限 / 连续 2 轮无改善。无论结果,通知 Builder 进入用户调整阶段。

### 用户调整验证

| 步骤 | 操作 |
|------|------|
| 1 | Read `user-adjustment-round-{N}.md`,了解用户原始需求 |
| 2 | 跑 `git diff`,了解 Builder 实际改了什么 |
| 3 | 逐条交叉对照:确认每条用户需求都有对应实现,标记遗漏项 |
| 4 | 对调整内容执行验证(运行测试、curl 验证等) |
| 5 | 确认未破坏已有功能(回归检查) |
| 6a | 通过 → `send_to_agent "harness-builder" "用户调整验证通过"` |
| 6b | 不通过 → `send_to_agent "harness-builder" "用户调整验证发现问题:[遗漏的需求序号及问题描述],请修复后回复我"` |

### 流程收尾

| 步骤 | 操作 |
|------|------|
| 1 | 收到 Builder 的"结束迭代"消息 |
| 2 | 创建 `.harness/done` 完成信号 |
