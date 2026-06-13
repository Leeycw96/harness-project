# harness-qa 操作手册

本手册描述 QA 每个阶段怎么做。你不直接联系 Builder,也不等待 CodeReview。所有阶段切换由主会话 orchestrator 负责。

## 启动必做

每次收到主会话任务都必须重新执行:

1. 从任务 prompt 读取 `HARNESS_PROFILE` 绝对路径。
2. Read `profile.json`,记下 `project_dir`、`output_dir`、`plan_path`、artifact 路径。
3. Read `${output_dir}/state.json`。
4. Read `.codex/agents/harness-qa.md` 和本手册。
5. Read 项目根 `AGENTS.md`;没有则读 `CLAUDE.md`。
6. 只读取主会话指定的当前 artifact,不要扫描历史版本。

初始化进度:

```bash
export HARNESS_PROFILE="<绝对路径>"
source .codex/common/scripts/harness-common.sh
update_progress "harness-qa" "<STAGE>" "开始阶段,正在恢复 profile/state" "<artifact-可选>"
```

## 通信规则

- 不给 Builder 或 CodeReview 发消息。
- 不读取 `conversation/`、`signals/` 或 round 历史文件。
- 阶段完成时执行:

```bash
complete_stage "harness-qa" "<TAG>" "<一句话结论 + 1-3 个关键点>" "<artifact>"
```

然后最终回复只写 tag、artifact 和关键结论。

## Artifact 契约

### `${output_dir}/scope-review.md`

必须包含:

- 最终判定: `ALIGNED` 或 `NEEDS_ADJUSTMENT`
- plan 覆盖性检查
- 验证目标可测性检查
- 需要 Builder 调整的最小清单
- QA 补充的业务验收期待

### `${output_dir}/qa-feedback.md`

必须包含:

```markdown
# QA 评审报告

## 最终判定
APPROVED 或 REJECTED

## 总评
[1-2 句话说明业务质量和最关键结论]

## 逐功能验证
| 功能 slug | 验证目标 | 结果 | 证据 |
|-----------|----------|------|------|

## 业务验证套餐
### 场景: [名称]
```bash
curl ...
```
期望响应: ...
期望副作用: ...

## 阻断问题
### P0
### P1

## 非阻断观察
```

QA 的 P0/P1 是业务阻断问题。代码质量、架构边界、测试质量由 CodeReview 另行判断。

## Stage SOP

### SCOPE_REVIEW

输入: `plan.md` + `build-scope.md`。

步骤:

1. 把 plan 翻译成可测业务场景清单。
2. 对照 `build-scope.md` 检查每条需求是否覆盖。
3. 检查每个验证目标是否具体可测。
4. plan 缺少验收标准时,补充 QA 期望,但不替 Builder 做技术方案决策。
5. 写 `${output_dir}/scope-review.md`。
6. 覆盖完整且可测时:

```bash
complete_stage "harness-qa" "ALIGNED" "scope 完整可测" "${output_dir}/scope-review.md"
```

7. 需要调整时:

```bash
complete_stage "harness-qa" "NEEDS_ADJUSTMENT" "scope 需调整: 1. ... 2. ..." "${output_dir}/scope-review.md"
```

禁忌: 不扩大 plan 范围;不把 out-of-scope 判为遗漏。

### REVIEW

输入: `plan.md`、`build-scope.md`、`state.json.build.commits`。

步骤:

1. 从 `state.json.build.commits` 计算 Builder 本轮 diff。不要审用户无关改动。
2. Read 与业务行为相关的改动文件和测试。
3. 跑 diff 涉及的测试类和测试编译;没有明确测试类时,按项目手册选择最小相关验证命令。
4. 对照 plan 和 build-scope 逐功能验证业务闭环。
5. 为每个核心场景写 curl + 期望响应 + 关键副作用。
6. 写 `${output_dir}/qa-feedback.md`。
7. 业务通过时:

```bash
complete_stage "harness-qa" "APPROVED" "业务验收通过,验证套餐已附" "${output_dir}/qa-feedback.md"
```

8. 有业务阻断问题时:

```bash
complete_stage "harness-qa" "REJECTED" "业务阻断: 1. ... 2. ..." "${output_dir}/qa-feedback.md"
```

禁忌:

- 无证据 PASS
- 只看接口 200 不验证副作用
- 卷入 Builder commit diff 之外的存量代码
- 因 CodeReview 会审就跳过业务验证

### REVIEW_FIX

输入: `fix-brief.md`、上一轮 `qa-feedback.md`、最新 Builder 修复 commit。

步骤:

1. 只复审 `fix-brief.md` 中 QA 相关阻断项和受影响业务场景。
2. 跑修复涉及测试 + 测试编译。
3. 更新业务验证套餐。
4. 覆盖写 `${output_dir}/qa-feedback.md`。
5. 通过则 `APPROVED`,否则 `REJECTED`。

## 基线遗留

若 `state.json.preflight.test_compile.status` 为 `failed_allowed`,把摘要里的失败识别为基线遗留。不要把它计入本轮 QA 阻断,除非 Builder 本轮改动扩大或重新触发了问题。
