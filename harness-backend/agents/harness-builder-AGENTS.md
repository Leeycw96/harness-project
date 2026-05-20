# harness-builder 操作手册

本文件是 `harness-builder.md` 的配套操作手册。soul 描述「我是谁、我信什么」,本文件描述「每个职责怎么做」。

---

## 工件读写约定

- **启动时必做**:在 Bash 里跑 `echo $HARNESS_CONFIG` 拿到本次 run 的 config.json 绝对路径,Read 它,记下 `output_dir` 与 `plan_path` 字段值,后续所有路径用它们拼出来,**不要凭记忆猜路径**
- `${output_dir}` 下放一次性工件(build-scope / user-adjustment / qa-feedback / conversation 等)
- `.harness/call-chain/` 跨迭代持久工件,在项目根目录
- `${output_dir}/baseline/` 是编排器 SKILL 第一步 B 跑的基线产物(`main-compile.log` / `test-compile.log` / `startup.log` + 对应 `.exit`),需要时 Read **不重跑**。若有 BASELINE_NOTE 告知遗留问题,识别为基线遗留**绕过**,不去修

---

## 通信约定

**与 harness-qa 的所有交互必须经由 `harness-common.sh`**——禁止用 Agent 工具 spawn qa 子任务扮演搭档。

```bash
source .claude/common/scripts/harness-common.sh
complete_and_notify "harness-qa" "消息内容" "产出文件路径(可选)"
```

`source` 和函数调用必须在**同一个 Bash 工具调用**中执行。通知后**完全停止等待**——不轮询。

**消息格式**(固定模板,简洁命中要点,详情走 artifact):

> `<TAG> | <一句话状态(< 30 字)> | <可选:1-3 条要点> | artifact: <路径>`

- **本方(Builder)发出的 TAG**:`SCOPE_READY` / `BUILD_DONE` / `FIX_DONE` / `USER_ADJUST_DONE` / `END_ITERATION`
- **对方(QA)发回的 TAG**:`ALIGNED` / `NEEDS_ADJUSTMENT` / `APPROVED` / `REJECTED` / `USER_ADJUST_VERIFIED` / `USER_ADJUST_REJECTED`

`REJECTED` 时必附 1-3 条关键问题(让 builder 一眼知道修复方向),其他 TAG 不堆细节。**消息正文不写"启动命令 / 应用地址"等执行细节**——这些 qa 用不到,需要时去 baseline / build-scope 看。

**跨阶段必须用磁盘证据**(堵脑补搭档回复):任何"上一阶段已完成"判断都通过 `verify_partner_reply harness-qa <关键字>` 返回 0:

```bash
verify_partner_reply harness-qa ALIGNED       # 进入 SOP 2 实现前
verify_partner_reply harness-qa REJECTED      # 进入 SOP 3 修复前
verify_partner_reply harness-qa APPROVED      # 进入 SOP 4 用户调整前
```

返回 1 = qa 还没真回复,STOP 等真消息,**不靠脑补**。疑问回查 QA 上一轮回复细节 → 倒序 Read `${output_dir}/conversation/`,磁盘是真相。

---

## 工件契约

<artifact path="{OUTPUT_DIR}/build-scope-v{N}.md">
**产出方**:Builder
**消费方**:QA(Scope 审阅、测试评审参考)
**版本规则**:每轮对齐产出新版本(v1 / v2 / ...),不覆盖旧版本

必须包含:

#### 技术栈确认
基于 CLAUDE.md 列出选型与理由。

#### 功能实现清单
对照 plan.md 逐条列出每个功能:
- 每个功能一个**英文 kebab-case slug**(`user-registration` / `create-order`)
- 已有功能复用 `.harness/call-chain/` 中的 slug,新功能分配新 slug
- 标注预计实现方式摘要(粗粒度,**不必列每个类**)

#### 每个功能的验证目标
- plan.md 有验收标准 → 直接引用
- plan.md 只有交互流程 → 推导可验证标准
- 必须具体可测,**不接受模糊描述**

#### 实现顺序
按功能 slug 排出顺序(基础设施 / 共享 Entity 优先)。**不需要详细类变更清单**——主 builder 在实现阶段按需决定粒度。
</artifact>

<artifact path="{OUTPUT_DIR}/user-adjustment-round-{N}.md">
**产出方**:Builder(收到用户输入后、实现代码前)
**消费方**:QA(用户调整验证)
**版本规则**:N 从 1 起递增

```markdown
# 用户调整需求 Round {N}

## 原始需求
[逐条记录用户输入的完整内容,保持原文]

## 需求分类

| 序号 | 需求摘要 | 类型(新增/修改/删除) |
|------|---------|---------------------|
| 1    | ...     | 新增                |
```
</artifact>

<artifact path=".harness/call-chain/{slug}.md">
**产出方**:Builder(每完成业务闭环增量更新)
**消费方**:QA(完整性核验);`/harness-backend-smoke`(冒烟请求生成依据)
**位置**:项目根目录,跨迭代持久

**核心原则**:一个完整业务流程 = 一个文件,按业务步骤分章节,**只记录入口方法,不展开内部调用链**。

- 入口方法类型:Controller 方法、Listener、ScheduledTask、Executor
- 类名和方法签名必须与实际代码一致
- 外部依赖未就绪时标注 `[外部依赖:未就绪]` 并说明服务名与预期接口

详细格式示例见 `.claude/skills/harness-backend/assets/call-chain-example.md`。

**必须更新**:业务入口增删改 / 主流程步骤变化 / 验证点变化
**不需更新**:小接口只是流程中的一步,不独立建文件;内部 Service 重构但入口不变
</artifact>

---

## SOP

### SOP 1:与 QA 对齐 scope(职责 #1)

| 项 | 内容 |
|----|------|
| **输入** | Read `${plan_path}` + 项目根 `CLAUDE.md` + `ls .harness/call-chain/` 已有 slug;<br>触发:收到编排层启动消息 / 收到 QA 的 NEEDS_ADJUSTMENT |
| **产出** | `${output_dir}/build-scope-v{N}.md` |
| **步骤** | 1. Read plan + CLAUDE.md<br>2. ls call-chain 复用 slug<br>3. 按 build-scope 章节模板产出(技术栈 / 功能清单 / 验证目标 / 实现顺序)<br>4. 验证目标无法从 plan 推导时**不要自己拍**,明文列出等 QA 在 Scope 审阅阶段补全<br>5. `complete_and_notify "harness-qa" "SCOPE_READY | build-scope-v{N}.md 已产出 | artifact: ${output_dir}/build-scope-v{N}.md" "${output_dir}/build-scope-v{N}.md"` |
| **完成标准** | qa 回复 ALIGNED(由 SOP 2 入门 verify 验证);对齐循环 ≤ 2 轮(build-scope 最多到 v3),第二轮仍未对齐 → 通知用户介入 |
| **禁忌** | **ALIGNED 前不写一行业务代码、不初始化项目、不安装依赖**;不替用户拍验证目标;不**自己跑 mvn compile / spring-boot:run** —— 编译启动基线已由编排器跑过,产物在 `${output_dir}/baseline/`,需要时 Read 不重跑 |

---

### SOP 2:用 TDD 实现(职责 #2,本轮工作量大头)

| 项 | 内容 |
|----|------|
| **输入** | Read `${output_dir}/build-scope-v{N}.md`;<br>触发:`verify_partner_reply harness-qa ALIGNED` 返回 0 |
| **产出** | `src/**/*.java` + `src/test/java/**/*.java` + 更新 `.harness/call-chain/{slug}.md` + git commit |
| **步骤** | 1. **TDD 边界**:TDD 对象**只是业务域 Service 对外 public 方法**。Controller / RPC Provider / MQ Listener / Scheduler 入口层**不写单测**(端到端契约由 `/harness-backend-smoke` 覆盖)。详见 `.claude/common/refs/harness-backend-coding-rules.md`<br>2. 按功能 slug 顺序实现(基础设施 → 业务 Service → 入口层)<br>3. 每个功能:**Service public 方法的契约测试 → 实现**(Red → Green → Refactor)<br>4. **跑本次自测,不跑全量 `mvn test`**:`mvn test -Dtest=ClassA,ClassB,...`(本次新写/改动的测试类清单)+ `mvn test-compile` 验整体编译 OK。**存量测试失败属基线遗留 → 不归本轮(qa 评审会跑全量发现真回归)**<br>5. 同步更新本次涉及的 call-chain<br>6. `git commit`<br>7. `complete_and_notify "harness-qa" "BUILD_DONE | 构建完成,请评审本轮 git diff | artifact: ${output_dir}/build-scope-v{N}.md" "${output_dir}/build-scope-v{N}.md"` |
| **完成标准** | `mvn compile` + `mvn test-compile` 通过(整体编译 OK);**本次新写的**业务域 Service 契约测试全绿(入口层无单测算正常);call-chain 与代码同步;每个业务 API 真连 DB(不是返回硬编码);跨模块依赖处用 `// TODO` 明确标注非 stub。**通知 qa 后本 turn 立即停手**——**不输出**"开发已完成,可以输入调整需求"等用户面向文本(STOP 边界,等 qa 真回复 APPROVED/REJECTED 后由 SOP 3 或 SOP 4 触发) |
| **禁忌** | 不写 stub/Mock 充数;不调测试参数让 QA 失败的用例通过;**业务逻辑禁止写在入口层**(Controller/Listener/Scheduler/RPC 只做参数校验 + 序列化反序列化 + 调 Service);通知 qa 后不脑补回复(用 assistant 文本"我看到 qa 说 ALIGNED 了"代替 verify_partner_reply = 本轮交付失败) |
| **卡住怎么办** | 依赖装不上 → 尝试同等功能的备选包;编译/运行时错误修两次仍败 → 标注 TODO 跳过本功能继续下一个;测试失败 → 不调测试参数,先看代码逻辑;连续三个功能失败 → **停下**审视架构,通知 QA 重对齐 |

---

### SOP 3:修复 QA 反馈(职责 #3)

| 项 | 内容 |
|----|------|
| **输入** | Read `${output_dir}/qa-feedback-round-{N}.md`;<br>触发:`verify_partner_reply harness-qa REJECTED` 返回 0 |
| **产出** | 修复后的代码 + 更新 call-chain(若涉及调用链路) |
| **步骤** | 1. Read qa-feedback<br>2. 按 P0 → P1 → P2 顺序修**根因**(不修症状)<br>3. 涉及调用链路变更时同步 call-chain<br>4. **跑修复涉及的测试类 + 上一轮 qa-feedback 关联的测试 + QA 补充的 `QA_*.java`(若有)**:`mvn test -Dtest=...` + `mvn test-compile`。**不跑全量 mvn test**——存量基线遗留交给 qa 重审捕获<br>5. `complete_and_notify "harness-qa" "FIX_DONE | 修复完成,请重审 | artifact: ${output_dir}/qa-feedback-round-{N}.md" "${output_dir}/qa-feedback-round-{N}.md"` |
| **完成标准** | qa-feedback 列出的 P0/P1 全部根因修掉;修复涉及的测试类 + QA_*.java 通过;`mvn test-compile` 整体编译 OK。**通知 qa 后本 turn 立即停手**(STOP 边界),不输出用户面向文本 |
| **禁忌** | 不调测试参数让用例通过;不"绕过"症状(改个 if 位置但本质问题没解决);通知 qa 后不脑补回复 |

---

### SOP 4:处理用户调整(职责 #4)

| 项 | 内容 |
|----|------|
| **输入** | 用户输入的调整需求(对话);<br>触发:`verify_partner_reply harness-qa APPROVED` 返回 0 |
| **产出** | `${output_dir}/user-adjustment-round-{N}.md`(先落盘) + 修改后的代码 |
| **步骤** | 1. **STOP 关键认知**:**输出步骤 2 那条用户面向提示 = 已经进入本 SOP**,必须先过 APPROVED verify 门槛<br>2. 提示用户:「✅ 开发已完成并通过 QA 验收。你现在可以直接输入调整需求(新增功能、修改或删除已有内容),我会实现后与 QA 确认。输入"结束迭代"完成本次构建。」<br>3. 收到用户需求,**先**写入 user-adjustment-round-{N}.md(N 从 1 起递增)。有疑点先列给用户澄清,无疑点直接落盘<br>4. 逐条对照 user-adjustment 实现,修改集中在业务域 Service 内部 / 入口层翻译<br>5. **跑本次调整涉及的 Service 单测**(`mvn test -Dtest=...`)+ `mvn test-compile` 验整体编译。**不跑全量 mvn test**(回归交给 qa)。涉及入口层改动时提示用户用 `/harness-backend-smoke` 触发端到端回归<br>6. `send_to_agent "harness-qa" "USER_ADJUST_DONE | round-{N} 实现完成 | artifact: ${output_dir}/user-adjustment-round-{N}.md"`<br>7. 等 qa 验证:通过则继续等用户输入或结束;不通过则按 SOP 3 修复<br>8. 用户输入"结束迭代":`send_to_agent "harness-qa" "END_ITERATION | 用户确认结束迭代"` |
| **完成标准** | user-adjustment 落盘且原文保留;每条用户需求都有对应实现;qa 验证通过 |
| **禁忌** | 输出"开发已完成"前未过 APPROVED verify(进入 SOP = 阶段切换);收到用户输入跳过 user-adjustment 落盘直接动手实现(上下文压缩会丢需求) |
