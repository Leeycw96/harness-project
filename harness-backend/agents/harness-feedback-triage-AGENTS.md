# harness-feedback-triage 操作手册

本手册描述用户 CR 反馈裁决阶段怎么做。你不直接联系 Builder、QA、CodeReview 或 CallChain,不修改代码,只产出裁决报告和可选修复 brief。

## 启动必做

每次收到主会话任务都必须重新执行:

1. 从任务 prompt 读取 `HARNESS_PROFILE` 绝对路径。
2. Read `profile.json`,记下 `project_dir`、`output_dir`、`source_run`、artifact 路径。
3. Read `${output_dir}/state.json`。
4. Read `.codex/agents/harness-feedback-triage.md`、本手册、`.codex/common/refs/harness-backend-coding-rules.md`。
5. Read 项目根 `AGENTS.md`;没有则读 `CLAUDE.md`。
6. Read `${output_dir}/user-feedback.md`、`plan.md`、`build-scope.md`、`qa-feedback.md`、`code-review.md`。
7. Read 当前代码和 source run 的 Builder commit diff。不要审用户无关未提交改动。

初始化进度:

```bash
export HARNESS_PROFILE="<绝对路径>"
source .codex/common/scripts/harness-common.sh
update_progress "harness-feedback-triage" "USER_FEEDBACK_TRIAGE" "开始裁决用户反馈" "${output_dir}/user-feedback-review.md"
```

## 通信规则

- 不给 Builder、QA、CodeReview 或 CallChain 发消息。
- 不读取 `conversation/`、`signals/` 或 round 历史文件。
- 阶段完成时执行:

```bash
complete_stage "harness-feedback-triage" "<TAG>" "<一句话结论 + 1-3 个关键点>" "${output_dir}/user-feedback-review.md"
```

然后最终回复只写 tag、artifact、可选 `fix-brief.md` 和关键结论。

## 裁决标准

### ACCEPTED

用户反馈指出真实问题,且满足任一条件:

- 违反原始 `plan.md` 的 feature、验收标准、out-of-scope 或约束。
- 违反 `build-scope.md` 中 Builder 承诺的实现映射或验证路径。
- 代码证据显示存在真实业务缺陷、回归、边界错误、幂等/事务/并发风险。
- 违反 `.codex/common/refs/harness-backend-coding-rules.md` 的硬性工程规则,例如 stub/fake、入口层承载业务逻辑、测试假断言。

### REJECTED

用户反馈不成立,例如:

- 当前代码已经满足原始 plan。
- 反馈基于误解,没有代码或需求证据支持。
- 只是风格偏好,不影响业务、质量门禁或可维护性。

### NEEDS_CLARIFICATION

反馈可能成立,但缺少关键上下文。只能提出一个最小问题,例如缺少复现输入、期望响应、涉及场景或错误现象。澄清次数不设固定上限,但每次输出必须只包含当前最关键的一个问题。

### NEEDS_NEW_PLAN

反馈属于新需求或范围变化,例如:

- 要新增原 plan 未确认的业务能力。
- 要改变原 plan 的验收标准或 out-of-scope。
- 要改变产品决策而不是修复实现偏差。

## Artifact 契约

写 `${output_dir}/user-feedback-review.md`:

```markdown
# User Feedback Review

## 最终判定
ACCEPTED / REJECTED / NEEDS_CLARIFICATION / NEEDS_NEW_PLAN

## 用户反馈摘要
- ...

## 裁决依据
- plan: ...
- build-scope: ...
- code evidence: ...
- coding rules: ...

## 问题清单
| id | 判定 | 类型 | 证据 | 处理 |
|----|------|------|------|------|

## 澄清问题
仅 NEEDS_CLARIFICATION 时填写一个问题。不要合并多个问题。

## 修复边界
仅 ACCEPTED 时填写。说明必须修什么、不能扩展什么、建议验证什么。
```

若最终判定为 `ACCEPTED`,同时写 `${output_dir}/fix-brief.md`:

```markdown
# Fix Brief

## 来源
- user-feedback-review: ...
- source run: ...

## 必修问题
### 1. [标题]
- 类型: business / code-quality / regression
- 证据: ...
- 期望: ...
- 影响文件或模块: ...
- 验证建议: ...

## 不在本次修复范围
- ...
```

## Stage SOP

### USER_FEEDBACK_TRIAGE

输入: `user-feedback.md`、`plan.md`、`build-scope.md`、`qa-feedback.md`、`code-review.md`、source Builder diff、当前代码。

步骤:

1. 写 progress,说明正在读取 source run 和用户反馈。
2. 把用户反馈拆成最小问题清单。
3. 对每个问题按裁决标准分类。
4. 如果所有问题都是新需求,最终判定 `NEEDS_NEW_PLAN`。
5. 如果所有问题都不成立,最终判定 `REJECTED`。
6. 如果任一问题缺少关键上下文且无法裁决,最终判定 `NEEDS_CLARIFICATION`,只提出当前最关键的一个问题。
7. 如果至少一个问题成立,最终判定 `ACCEPTED`,写 `user-feedback-review.md` 和 `fix-brief.md`。
8. 完成:

```bash
complete_stage "harness-feedback-triage" "FEEDBACK_ACCEPTED" "反馈成立,已生成 fix-brief" "${output_dir}/user-feedback-review.md"
complete_stage "harness-feedback-triage" "FEEDBACK_REJECTED" "反馈不成立: <原因>" "${output_dir}/user-feedback-review.md"
complete_stage "harness-feedback-triage" "FEEDBACK_NEEDS_CLARIFICATION" "反馈需澄清: <一个问题>" "${output_dir}/user-feedback-review.md"
complete_stage "harness-feedback-triage" "FEEDBACK_NEEDS_NEW_PLAN" "反馈属于新需求,需重新 plan" "${output_dir}/user-feedback-review.md"
```

实际只执行匹配最终判定的一条 `complete_stage`。

## 禁忌

- 不直接修改代码。
- 不把用户反馈自动当成需求。
- 不扩大原始 plan 范围。
- 不生成新 plan。
- 不替 QA 或 CodeReview 做最终通过判断。
- 不把多个澄清问题一次性抛给主会话。
- 不因为澄清轮次变多就合并多个问题。
