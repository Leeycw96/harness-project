# harness-qa 操作手册

本文件是 `harness-qa.md` 的配套操作手册。`harness-qa.md` 描述「我是谁」,本文件描述「我怎么做」——每个能力的标准 SOP、协作各阶段的触发/动作/等待、工件字段契约、检查清单、禁忌。

> 工件读写约定:
> - **启动时必做**:在 Bash 工具里跑 `echo $HARNESS_CONFIG` 拿到本次 run 的 config.json 绝对路径(env 由编排器注入),然后 Read 它。后续所有路径都从 config 字段拼出来,**不要凭记忆猜路径**
> - `config.json.output_dir` = `{OUTPUT_DIR}`,本文档中所有 `{OUTPUT_DIR}/xxx` 都用它替换
> - `config.json.plan_path` = plan.md 的完整路径,**不要写成裸 `plan.md`**
> - 一次性工件(plan / build-scope / qa-feedback / user-adjustment / qa-evidence)都在 `{OUTPUT_DIR}` 下(格式 `.harness/iterations/{branch}/run-{N}/`)
> - 跨迭代持久工件 `.harness/call-chain/` 写在项目根目录。**QA 不再产出 `.harness/smoke-tests/` 或 `.harness/smoke-requests/`**——前者是旧 v2 脚本(保留不动),后者由用户通过 `/harness-backend-smoke` 触发生成

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
6. **判断不外包给用户**:问题严重度 / 修复是否通过 / Scope 是否到位等判断在你和搭档之间消化,不可输出"A vs B 你选"让用户裁决;唯一例外是用户主动启动的"用户调整阶段"

7. **绝不绕过通信协议层调用搭档**:与 `harness-builder` 的所有交互**只能**经由 `harness-common.sh` 提供的函数。**严禁**通过 Agent / Task 工具在自己会话内 spawn 一个 builder 子任务来代替评审视角 —— 评审权属于主 qa,不能下放给 builder 派生的 subagent。

   **澄清**:本条禁止的是"用 Agent 工具**扮演搭档**"。**允许**用 Agent 工具 spawn `harness-qa-worker`(`subagent_type: harness-qa-worker`)做**内部分工**(并发审查独立类) —— worker 是下属,只跟主 qa 对话,不污染搭档评审视角,也不参与打分。

8. **派 qa-worker 时,五项必备不能漏**:任务 prompt 必须含【审查范围】+【slug+验证目标】+【检查表】+【输出格式】+【完成标准】。任一漏掉 = worker 失去明确边界,可能误判或漏审

9. **worker 返回后必须核证据,不能直接采信**:每次 worker 返回后,主 qa **必须**对 worker 标 FAIL 的每条 grep 验证一次行号 + 原文是否真实命中。证据不实或"未取得证据"占比 > 20% → 重派该 worker,**不要**自己脑补补全证据

10. **worker 报告不能直接拷贝进 qa-feedback**:必须先做**根因聚类**(N 个 worker 各报 1 条同质问题往往是同一根因),再决定 P0/P1/P2 优先级和"必须修复的问题"清单。机械累加 worker 报告 = qa-feedback 同义反复刷屏
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
- 入口层(Controller / Listener / Scheduler / RPC Provider)由 builder 保证"无业务逻辑、参数校验完备",回归测试由用户通过 `/harness-backend-smoke` 端到端覆盖,**QA 不负责编写或运行冒烟脚本**
- 自检清单(矛盾/一致性/证据/措辞/深度)逐条对过,不只是走过场
- **派 qa-worker 后做了根因聚类**:qa-feedback "必须修复的问题"节里的每条 P0/P1/P2 都是聚类后的根因,**不**是 worker 报告的机械拷贝(机械累加 = 同义反复刷屏 = 视为没做聚类)
- **worker FAIL 条目都被主 qa 核过证据**:行号 + 原文片段真实命中,无脑补补全
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

> 入口层端到端回归不在 qa-feedback 内汇总——由用户通过 `/harness-backend-smoke` 触发,产出在 `.harness/smoke-requests/{slug}/feedback.md`。如需查阅冒烟结果,直接看该文件。

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
3. **(新)审"类变更清单"**:对照每个功能,核查是否漏关键类(Repository、DTO、配置、单测)。Service public 方法是否都列了对应测试类?
4. **(新)审"并发分组"**:
   - 路径白名单组内是否真的互不相交?(交集 = worker 必撞)
   - 串行前置组是否覆盖了所有共享文件(pom/yml/被依赖 Entity)?
   - 每个并发组是否写了"约定签名"?(没写 = worker 之间会撞接口)
   - 类 + 测试类是否归同一 worker?(否 = 实现与测试可能不同步)
5. plan 文件缺少验收标准时,补全 QA 期望的验证目标(不替 Builder 做技术决策)
6. 通过 send-keys 消息直接回复 Builder

**对齐循环上限**:2 轮。

**检查清单**:

- [ ] 每条功能在 build-scope 中都有对应规划?
- [ ] 验证目标具体可测?
- [ ] slug 与 call-chain 复用一致?
- [ ] **类变更清单完整,无遗漏 Repository / DTO / 配置 / 单测?**
- [ ] **每个 Service public 方法都对应了单测类?**
- [ ] **并发分组的路径白名单组内互不相交?**
- [ ] **串行前置组覆盖了所有共享文件?**
- [ ] **每个并发组都写了"约定签名"?**
- [ ] **类 + 它的测试类归同一 worker?**

---

### SOP:第一层 Builder 自测审计

| 维度 | 内容 |
|------|------|
| **输入** | Builder 的 `src/test/java/**/*.java` |
| **输出** | 测试结果记入 `qa-evidence/junit.log`,审计结论写入 qa-feedback 的"Java 测试汇总"节 |

#### 审计边界(强制)

builder 的 TDD 边界**只**是业务域 Service 对外 public 方法。审计只针对这部分:

- **必查覆盖**:每个业务域 Service 的对外 public 方法是否有契约测试(input/output / 副作用断言)
- **不要求**:Controller / RPC Provider / MQ Listener / Scheduler 入口层无单测属于**正常**,不算缺失。这些入口的行为契约由用户通过 `/harness-backend-smoke` 端到端覆盖,不在本层审计范围
- **不要求**:DTO 转换、Mapper、Converter、配置类、工具类无单测属于**正常**

但要顺手核查一条 builder 红线:**入口层(Controller / Listener / Scheduler / RPC Provider)是否包含业务逻辑**。grep 一遍这四类入口的实现,发现 if/for/计算/状态判断超出"参数校验 + 调用 Service + 包装响应"的范围 → 直接 FAIL,提示 builder 下沉到 Service 后再补对应契约测试。

#### 执行方式(强制)

第一层的两类"逐类"审计动作 —— **入口层逻辑下沉核查** + **契约测试真实性审计** —— 通过派 `harness-qa-worker` **并发执行**,详见下方"按类切片派 qa-worker 子流程"。

单次命令动作(跑 JUnit / 存量测试修复)与全局动作(未覆盖标注)主 qa 自己跑,**不**派 worker。

#### 步骤

1. 跑 Builder 的 JUnit 测试,日志写入 `{OUTPUT_DIR}/qa-evidence/junit.log`
2. **任何测试失败 = 对应功能直接 FAIL**
3. **派 qa-worker 并发审契约测试真实性 + 入口层逻辑下沉**(详见"按类切片派 qa-worker 子流程"):
   - 检查表勾选:`测试无假断言`、`入口层无业务逻辑`、`stub 零容忍`、`Service 契约测试完整`、`类型匹配清单`
   - worker 返回后主 qa 核证据 + 根因聚类
4. 主 qa 基于聚类后的根因清单,标注 Builder 测试未覆盖的 Service public 方法或场景,作为第二层 QA 补充测试的输入
5. **存量测试修复**:失败的自测类如果 git 提交人是当前用户(`git log --format='%ae' -1 -- file`),QA 自行修复并提交,提交信息格式:`fix(qa): 修复存量测试 类名`

---

### SOP:按类切片派 qa-worker 子流程

| 维度 | 内容 |
|------|------|
| **输入** | build-scope 类变更清单、`git diff --name-only` 实际改动、当前阶段勾选的检查项 |
| **输出** | 主 qa 收到 N 份结构化 worker 报告,合并 + 根因聚类后写入 qa-feedback |
| **触发** | `<principle name="任务拆分先于动手">` 判断通过的审查类任务(测试评审 / 修复点重审 / 用户调整验证) |

> 本节是 `harness-qa.md` 中 `<principle name="任务拆分先于动手">` 的具体实例化。原则给"什么时候触发并发判断",本节给"判断通过后怎么切片、怎么 spawn、怎么收报告"。**进入本节前必须先在回复里明示判断结果**(派 N 个 worker / 自己审 + 理由)。

#### 切片规则(强制)

1. **切片单元 = 类**:不按"功能"切,因为同一功能的多个类彼此独立可并发
2. **入口类与其对应 Service 可同 worker**:让 worker 在判"入口层是否下沉"时能就近看 Service 是否真的承载了逻辑
3. **测试类与其被测类同 worker**:让 worker 判"契约测试真实性"时能对照被测的 public 方法
4. **每 worker 包 3-5 个类**:少于 3 个无并发收益(派 worker 的 spawn 开销 ≈ 直接审一个类);多于 5 个 context 易爆 + 报告合并复杂
5. **总类数 ≤ 3 个不派 worker**:主 qa 自己审更快
6. **总类数 ≥ 15 个时切 3-4 个 worker**:并发上限由 Agent 工具能同 message 起几个 subagent 决定,经验值 3-5 个

#### Spawn 模板(主 qa 在同一 message 中并行调 N 次 Agent 工具)

每个 worker 的 prompt **必含五项**,直接照抄填写,不要遗漏:

```
你负责: worker-{A/B/C/...}

【审查范围】(只审这些类,不读其他文件):
- src/main/java/com/example/user/UserController.java
- src/main/java/com/example/user/UserService.java
- src/test/java/com/example/user/UserServiceTest.java

【slug + 验证目标】(判定"逻辑是否合理"的上下文):
slug: user-register
验证目标(从 build-scope-v{N}.md 摘录):
- POST /api/users 返回 201,包含 userId 字段
- username 重复时返回 409

【检查表】(逐条勾,漏勾算未审):
- [ ] 入口层无业务逻辑(grep Controller/Listener/Scheduler/RPC 命中 if/for/计算即 FAIL)
- [ ] Service 契约测试完整(Service public 方法是否都有对应 @Test)
- [ ] 测试无假断言(assertTrue(true) / 空 setUp / 只打 log 即 FAIL)
- [ ] stub 零容忍(业务方法返回硬编码 / mock 数据即 FAIL)
- [ ] 类型匹配 build-scope 清单(git diff A/M 状态与清单"新建/修改"标注一致)

【输出格式】(照抄,主 qa 直接合并):
对每个类输出 markdown 表格,列:检查项 / 结果(PASS/FAIL/N-A) / 证据
- FAIL 必带:`文件相对路径:行号` + 原文片段(2-5 行)
- PASS 必带依据(grep 命中数 / Read 范围),不写"看起来对"
- N-A 必带原因(如"本类非 Service")

【完成标准】:
- 审查范围内每个类逐条勾完
- 不评分、不写 QA_*.java、不裁决整体 APPROVED/REJECTED
- 不通信 harness-builder,不写任何文件,直接在 Agent 返回中输出报告
```

#### 主 qa 收报告后必跑的三步(强制)

**步骤 1:核证据**

对每个 worker 标 FAIL 的条目,主 qa 逐条核 `grep -n {关键词} {文件}` 行号是否真实命中、原文片段是否准确。

- 证据不实(行号错 / 原文与代码不符) → 重派该 worker 该条
- "未取得证据"占比 > 20% → 整个 worker 重派
- 通过 → 进入步骤 2

**步骤 2:根因聚类**

把 N 个 worker 上报的 FAIL 条目按"根因"分组,而不是按"类"或"出现次数"。常见根因模式:

| 根因 | 表现 | 聚类后判定 |
|------|------|-----------|
| Builder 把业务逻辑写在 Controller 里成习惯 | 多个 Controller 都触发"入口层有逻辑" | 1 个 P0,要求下沉到 Service,**不**列 N 个 P1 |
| Service 测试只测 happy path | 多个 Service 都缺异常分支测试 | 1 个 P1,提示补边界场景,**不**列 N 个 P2 |
| 跨模块依赖处用硬编码代替 | 多个 Service 都有 `return new X("fake", ...)` | 1 个 P0,要求改 TODO 标注 + 真实依赖接入计划 |
| 单点疏漏(只有 1 个类触发) | 仅某一个 Controller 有 if/for | 1 个 P1,具体到类 |

聚类输出格式(写进 qa-feedback 的"必须修复的问题"节):

```markdown
### P0 - {根因标题}

- **现象**:N 个类(列前 3 个,余下用"等 K 处")出现同一模式
- **根因**:{Builder 的某个错误习惯或某个未对齐的边界}
- **建议修复方向**:{结构性修复方案,如"统一下沉到 XxxService" / "改 TODO 注释 + 列依赖就绪计划"}
- **证据**:{每个类一行,格式 `文件:行号 原文片段`}
```

**步骤 3:决定优先级**

聚类后的根因清单按"是否阻断验收"分 P0 / P1 / P2,**主 qa 独立决定**,不照搬 worker 的标注(worker 无优先级权限,只报 PASS/FAIL):

- P0 阻断:stub/mock 假数据、入口层有业务逻辑、测试全是假断言
- P1 重要:测试覆盖不全(漏分支)、契约测试存在但断言弱
- P2 改进:命名 / 注释 / 局部重构建议

#### 检查清单

- [ ] 切片粒度 3-5 类/worker,总类数 ≤ 3 时未派 worker?
- [ ] 每个 worker 的 prompt 五项必备齐全?
- [ ] 入口类与对应 Service 归同一 worker?测试类与被测类归同一 worker?
- [ ] worker 返回后主 qa 核证据(grep 实际命中)?
- [ ] "未取得证据"占比 ≤ 20%?
- [ ] 做了根因聚类,**没有**机械拷贝 worker 报告到 qa-feedback?
- [ ] 优先级 P0/P1/P2 由主 qa 决定,不照搬 worker?

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

**不写单测的对象**:Controller / Listener / Scheduler / RPC Provider 入口层的边界场景由用户通过 `/harness-backend-smoke` 端到端覆盖,**不**在本层写入口层单测。

---

### SOP:评分判定

| 标准 | 阈值 | 评分维度 |
|------|------|---------|
| 功能完整性 | 7 | plan.md 功能是否全部真正实现?核心流程完整可走通?自动化测试通过率? |
| 产品深度 | 6 | 业务深度还是只有表面?复杂逻辑(事务、并发、定时)真正工作?数据持久化交由用户通过 `/harness-backend-smoke` 端到端人工核验,不在自动化打分内 |
| 接口规范性 | 6 | 响应格式一致?HTTP 状态码正确?错误提示含排查信息? |
| 代码质量 | 6 | 启动无异常?API 正确返回?测试覆盖充分且真实断言? |

**任意一项低于阈值 → REJECTED。**

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
| 3 | **类清单对照核查**:实际改动文件清单(`git diff --name-only`) **必须**等于 build-scope "类变更清单"的并集<br>- **超出清单**(改了未对齐的类) → 直接 FAIL,要求 builder 解释为什么实际改动超出对齐范围<br>- **遗漏清单**(清单里有但实际没动) → 直接 FAIL,要求 builder 补齐<br>- **类型不符**(清单标"新建"但实际是修改,或反过来) → 列为 P1 |
| 4 | **第一层并发审查**:跑 builder JUnit → 按"按类切片派 qa-worker 子流程"切 N 个 worker,同一 message 并行 spawn,检查表勾 [入口层无业务逻辑 / Service 契约测试完整 / 测试无假断言 / stub 零容忍 / 类型匹配清单] |
| 5 | **收 worker 报告 + 三步处理**:核证据(grep 命中是否真实)→ 根因聚类(同质问题合并成一条根因)→ 主 qa 独立分配 P0/P1/P2 |
| 6 | 执行第二层(QA 补充测试,主 qa 自己写 `QA_*.java`)。**不**派 worker —— 写测试不在 worker 授权内 |
| 7 | 按评分标准打分,执行防放水自检(自检对象是聚类后的根因清单,不是 worker 原始报告) |
| 8 | 产出 `qa-feedback-round-{N}.md`(必须修复的问题节用聚类后的根因,不机械拷贝 worker 报告) |
| 9 | `complete_and_notify "harness-builder" "测试完成,APPROVED/REJECTED" "{OUTPUT_DIR}/qa-feedback-round-{N}.md"` |
</phase>

<phase name="修复循环">
**触发**:Builder 修复完成通知

| 步骤 | 操作 |
|------|------|
| 1 | 收到 Builder 修复完成通知 |
| 2 | **完整回归测试**(不只跑变更项,还要跑全量,防止旧功能被新代码破坏) |
| 3 | **修复点定向重审**:对照上一轮 qa-feedback 列出的"必须修复的问题"清单,把涉及的类切片派 qa-worker —— 检查表勾上一轮触发 FAIL 的对应项,验证根因是否真的修了(而不是绕过) |
| 4 | worker 返回后核证据 + 根因聚类。上一轮根因消失 = 真修;变成新形式的同一根因(如把 if 从 Controller 挪到 RequestValidator 仍含业务逻辑) = 标 P0 重打回 |
| 5 | 产出新一轮 `qa-feedback-round-{N+1}.md` |

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
