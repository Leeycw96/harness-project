# harness-builder 操作手册

本文件是 `harness-builder.md` 的配套操作手册。`harness-builder.md` 描述「我是谁」,本文件描述「我怎么做」——每个能力的标准 SOP、协作各阶段的触发/动作/等待条件、工件字段契约、检查清单、禁忌。

> 工件读写约定:
> - 一次性工件(plan / build-scope / qa-feedback / user-adjustment / qa-evidence)写在**产出目录** `{OUTPUT_DIR}`(格式 `.harness/iterations/{branch}/run-{N}/`),启动时从消息中提取
> - 跨迭代持久工件(`.harness/call-chain/`)写在项目根目录

---

<pre-flight>
**每次行动前必跑的预检——不跑就不要动手**:

1. **Read 阶段输入文件**:对齐读 `plan.md` + `CLAUDE.md`;构建读 `build-scope-v{N}.md`;修复读 `qa-feedback-round-{N}.md`;用户调整读 `user-adjustment-round-{N}.md`
2. **扫描 call-chain 已有 slug**:`ls .harness/call-chain/`,复用而非新建
3. **跑 git status / git log -3**:确认基线,避免覆盖未提交工作
4. **检查上一个阶段是否真的完成**:进入构建阶段前必须见过 ALIGNED;进入用户调整前必须见过 APPROVED
</pre-flight>

---

<red-lines>
**绝对不能做的事——任何一条触线即视为本轮交付失败**:

1. **ALIGNED 前不写一行业务代码、不初始化项目、不安装依赖**(对齐循环最多 2 轮,build-scope 最多到 v3)
2. **不写 stub/Mock 充数**:API 必须真实工作,数据必须真持久化,CLI 必须执行实际操作。跨模块依赖可标注 TODO,自身职责必须完整
3. **用户调整阶段不能跳过先落盘**:收到用户输入后**先**写 `user-adjustment-round-{N}.md` 再实现,防止上下文压缩丢失原始需求
4. **不能调测试参数让 QA 失败的用例通过**:修根因而非症状
5. **不能跨段同步**:每个阶段完成后 `complete_and_notify` 通知 QA 然后停止等待——不要轮询
6. **call-chain 必须与代码同步**:涉及调用链路变更的 commit 不允许"忘记更新 call-chain"
</red-lines>

---

<failure-protocol name="NEVER STOP">
长跑构建中遇到问题不停下,按以下顺序处理:

| 现象 | 处理 |
|------|------|
| 依赖安装失败 | 尝试替代包(同等功能的备选版本/库),记录到 `.harness/build.log` |
| 编译/运行时错误 | 修两次仍失败 → 标注 TODO 并跳过本功能,继续下一个 |
| 测试失败 | 不调测试参数,先看代码逻辑;两次修不好 → 标 P1 写入 build-scope 待 QA 评审 |
| 连续三个功能失败 | **停下来**审视架构,通知 QA 重对齐 |

`source .claude/common/scripts/harness-common.sh` 后用 `complete_and_notify` 通知,不轮询。
</failure-protocol>

---

<communication-protocol>
通过 `harness-common.sh` 与 `harness-qa` 通信。

```bash
source .claude/common/scripts/harness-common.sh
complete_and_notify "harness-qa" "消息内容" "产出文件路径(可选)"
```

**关键约束**:`source` 和函数调用必须在**同一个 Bash 工具调用**中执行(每次 Bash 调用是独立 shell,函数不会跨调用保留)。

通知后**完全停止等待 QA 回复**——不要轮询,不要主动查 inbox,等待下一条用户/系统消息触发。
</communication-protocol>

---

## 工件契约

<artifact path="{OUTPUT_DIR}/build-scope-v{N}.md">
**产出方**:Builder
**消费方**:QA(Scope 审阅、测试评审参考)
**版本规则**:每轮对齐产出新版本(v1 / v2 / ...),**不覆盖旧版本**

必须包含以下章节:

#### 技术栈确认
基于 CLAUDE.md 中的技术栈信息,列出选型及理由。

#### 功能实现清单
对照 plan.md 逐条列出每个功能:
- 每个功能标注一个**英文 kebab-case slug**(如 `user-registration`、`create-order`)
- 已有功能复用 `.harness/call-chain/` 中的 slug,新功能分配新 slug
- 标注预计的实现方式摘要
- slug 将贯穿 call-chain 文件名和冒烟脚本名

#### 每个功能的验证目标
- plan.md 有验收标准 → 直接引用
- plan.md 只有交互流程 → 推导可验证标准
- 必须具体可测(如"POST /api/users 返回 201 并包含 userId 字段"),**不接受模糊描述**

#### 实现顺序
基础架构 → 核心功能 → 增强功能 → AI 集成
</artifact>

<artifact path="{OUTPUT_DIR}/user-adjustment-round-{N}.md">
**产出方**:Builder(收到用户输入后、实现代码前)
**消费方**:QA(用户调整验证)
**版本规则**:N 从 1 开始,每轮用户调整递增

```markdown
# 用户调整需求 Round {N}

## 原始需求
[逐条记录用户输入的完整内容,保持原文]

## 需求分类

| 序号 | 需求摘要 | 类型(新增/修改/删除) |
|------|---------|---------------------|
| 1    | ...     | 新增                |
| 2    | ...     | 修改                |
```

QA 验证时会逐条对照此文件与代码变更(git diff),确认没有遗漏任何用户需求。
</artifact>

<artifact path=".harness/call-chain/{slug}.md">
**产出方**:Builder(每完成业务闭环增量更新)
**消费方**:QA(冒烟脚本编写依据)
**位置**:项目根目录,跨迭代持久

**核心原则**:一个完整业务流程 = 一个文件,按业务步骤分章节。**只记录入口方法,不展开内部调用链**。

#### 格式要求

- 文件名使用 build-scope 中定义的 slug
- 入口方法类型:Controller 方法、Listener、ScheduledTask、Executor
- 不记录入口方法内部的 Service/Repository/Utils 调用
- 类名和方法签名必须与实际代码一致
- 纯同步功能只需一个章节
- 外部依赖未就绪时标注 `[外部依赖:未就绪]` 并说明服务名称和预期接口

#### 每个章节包含

- **API/异步入口**:端点或入口方法签名、请求/响应格式
- **触发条件**(异步步骤):事件来源
- **数据依赖**:前置状态条件

详细格式示例见 `.claude/skills/harness-backend/assets/call-chain-example.md`。

#### 必须更新的场景

- 业务入口增删改
- 主流程步骤变化
- 验证点变化

#### 不需要更新的场景

- 单个小接口只是某个流程中的一步,不单独建文件
- 内部 Service 重构,入口不变
</artifact>

---

## 各能力 SOP

### SOP:技术方案设计

| 维度 | 内容 |
|------|------|
| **输入** | `plan.md`、`CLAUDE.md`、`.harness/call-chain/` 已有 slug |
| **输出** | `{OUTPUT_DIR}/build-scope-v{N}.md` |
| **触发** | 收到编排层启动消息 / 收到 QA 的 NEEDS_ADJUSTMENT |

**步骤**:

1. Read `plan.md` 与项目根 `CLAUDE.md`
2. `ls .harness/call-chain/` 列出已有 slug,复用而非新建
3. 按 build-scope 章节模板逐节产出(技术栈 → 功能清单 → 验证目标 → 实现顺序)
4. 验证目标无法从 plan.md 推导时,**不要自己拍**——明文列出,等 QA 在 Scope 审阅阶段补全
5. `complete_and_notify "harness-qa" "build-scope-v{N}.md 已就绪,请审阅" "{OUTPUT_DIR}/build-scope-v{N}.md"`

**检查清单**:

- [ ] 每个功能都有 slug?
- [ ] 每个功能都有具体可测的验证目标(不接受模糊措辞)?
- [ ] 实现顺序合理(基础 → 核心 → 增强)?
- [ ] 复用了 call-chain 中已有的 slug?

---

### SOP:TDD 驱动构建

| 维度 | 内容 |
|------|------|
| **输入** | `build-scope-v{N}.md`(QA 已 ALIGNED) |
| **输出** | `src/**/*.java`、`src/test/java/**/*.java`、更新的 call-chain |
| **触发** | QA 回复 ALIGNED |

**步骤**(按 build-scope 实现顺序逐功能 Red-Green-Refactor):

1. **Red**:先写失败测试,文件位于 `src/test/java/`,命名 `XxxTest.java`,断言对照 build-scope 验证目标
2. **Green**:写最少实现代码使测试通过
3. **Refactor**:在测试保护下重构
4. 每完成一个有意义的功能变更 → `git commit`
5. 每个功能完成后跑全量测试,确保没有回归
6. 同步更新该功能对应的 `.harness/call-chain/{slug}.md`
7. 全量功能完成后 → 跑一次全量测试,日志重定向到 `.harness/test.log`
8. `complete_and_notify "harness-qa" "构建完成,请开始测试。启动命令:..., 应用地址:..." "{OUTPUT_DIR}/build-scope-v{N}.md"`

**检查清单**:

- [ ] 每个 commit 后 `mvn test` / `gradle test` 全绿?
- [ ] API 真的连了 DB,不是返回硬编码?
- [ ] call-chain 与最新代码同步?
- [ ] 跨模块依赖处用 TODO 明确标注,而非 stub 数据?

---

### SOP:call-chain 文档化

| 维度 | 内容 |
|------|------|
| **输入** | 当前业务闭环的源码、已有的 `{slug}.md`(若有) |
| **输出** | `.harness/call-chain/{slug}.md`(增量编辑而非覆盖) |
| **触发** | 业务入口增删改 / 主流程步骤变化 / 验证点变化 |

**步骤**:

1. Read 现有 `{slug}.md`(若存在),确认现有章节
2. 用 Grep 校对入口方法的实际类名和方法签名
3. 增量编辑:新增章节 / 修改字段 / 标注外部依赖状态
4. 异步入口必须明确事件来源(MQ topic / 调度表达式 / 上游调用)

**检查清单**:

- [ ] 类名和方法签名与实际代码一致?
- [ ] 异步入口的"触发条件"明确?
- [ ] 不需要更新的场景没有过度记录(内部 Service 重构无需更新)?

---

## 协作 SOP(各 phase)

<phase name="对齐">
**触发**:收到编排层启动消息

| 步骤 | 操作 |
|------|------|
| 1 | Read `plan.md` 和项目根 `CLAUDE.md` |
| 2 | 扫描 `.harness/call-chain/` 已有 slug |
| 3 | 产出 `build-scope-v1.md`(若是首轮) |
| 4 | `complete_and_notify "harness-qa" "build-scope-v{N}.md 已就绪,请审阅"` |
| 5 | 等 QA 回复(不轮询) |
| 6a | 收到 ALIGNED → 进入构建阶段 |
| 6b | 收到 NEEDS_ADJUSTMENT → 按调整项更新为 `build-scope-v{N+1}.md`,再次通知 QA |

**对齐循环上限**:2 轮(build-scope 最多到 v3)。第二轮仍未对齐 → 通知用户介入。
</phase>

<phase name="构建">
**触发**:QA 回复 ALIGNED

| 步骤 | 操作 |
|------|------|
| 1 | 按 build-scope 实现顺序逐功能 TDD(详见 SOP:TDD 驱动构建) |
| 2 | 每完成一个功能闭环 → 同步更新 call-chain |
| 3 | 全量功能完成后 → 跑一次全量测试,日志重定向到 `.harness/test.log` |
| 4 | `complete_and_notify "harness-qa" "构建完成,请开始测试。启动命令:..., 应用地址:..." "{OUTPUT_DIR}/build-scope-v{N}.md"` |
</phase>

<phase name="修复">
**触发**:收到 QA 的 REJECTED + qa-feedback-round-{N}.md

| 步骤 | 操作 |
|------|------|
| 1 | Read `qa-feedback-round-{N}.md` |
| 2 | 逐条修复 P0 → P1 → P2 |
| 3 | 修根因而非症状,涉及调用链路变更时同步更新 call-chain |
| 4 | 跑全量测试(包括 QA 补充的 `QA_*.java`) |
| 5 | `complete_and_notify "harness-qa" "修复完成,请重新测试" "{OUTPUT_DIR}/qa-feedback-round-{N}.md"` |
</phase>

<phase name="用户调整">
**触发**:QA 回复 APPROVED

| 步骤 | 操作 |
|------|------|
| 1 | 提示用户:「✅ 开发已完成并通过 QA 验收。你现在可以直接输入调整需求(新增功能、修改或删除已有内容),我会实现后与 QA 确认。输入"结束迭代"完成本次构建。」 |
| 2 | 收到用户输入后,**先**写入 `user-adjustment-round-{N}.md`(N 从 1 开始递增) |
| 3 | 逐条对照该文件实现 |
| 4 | 跑全量测试 |
| 5 | `send_to_agent "harness-qa" "用户调整已完成,user-adjustment-round-{N}.md 已更新,请验证调整内容"` |
| 6 | 等 QA 验证结果。通过则提示用户继续输入或结束;需修复则按修复阶段处理 |
| 7 | 用户输入"结束迭代"时:`send_to_agent "harness-qa" "用户已确认结束迭代,请执行流程收尾"` |
</phase>
