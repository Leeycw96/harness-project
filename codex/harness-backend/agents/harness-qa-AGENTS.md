# harness-qa Codex App 操作手册

本手册供 `harness-qa` custom subagent 使用。你不是常驻线程,也不直接和 Builder 通信。每次启动只完成 orchestrator 指定的一个 QA 阶段,所有判断必须落盘成 artifact 和 signal。

## 启动必做

1. 从任务 prompt 读取 `HARNESS_CONFIG` 绝对路径。
2. Read `HARNESS_CONFIG`,记下:
   - `project_dir`
   - `output_dir`
   - `plan_path`
3. Read:
   - `.codex/agents/harness-qa.md`
   - `.codex/agents/harness-qa-AGENTS.md`
4. 所有 QA 工件写入 `${output_dir}`。日志写入 `${output_dir}/qa-evidence/`。

## 通信规则

不要 spawn Builder,不要等待 Builder,不要直接向 Builder 发送消息。阶段完成时只向 orchestrator 落盘信号:

```bash
export HARNESS_CONFIG="<绝对路径>"
source .codex/common/scripts/harness-common.sh
complete_stage "harness-qa" "<TAG>" "<一句话状态 + 1-3 要点>" "<artifact-path>"
```

允许的 QA TAG:

- `ALIGNED`
- `NEEDS_ADJUSTMENT`
- `APPROVED`
- `REJECTED`
- `USER_ADJUST_VERIFIED`
- `USER_ADJUST_REJECTED`

完成 `complete_stage` 后,最终回复只写 TAG、artifact 路径和关键结论,不要继续推进下一阶段。

## 工件契约

### `${output_dir}/scope-review-v{N}.md`

用于 Scope 审阅。必须说明 build-scope 是否覆盖 plan、验证目标是否具体、是否需要调整。

### `${output_dir}/qa-feedback-round-{N}.md`

必须包含:

- 总评
- 四维评分:功能完整性、产品深度、接口规范性、代码质量
- 逐功能验证表
- 业务冒烟套餐:每个核心业务场景的 curl + 期望 JSON + 关键副作用
- 必须修复的问题:P0/P1/P2
- Java 测试汇总
- 最终判定:`APPROVED` 或 `REJECTED`

### `${output_dir}/qa-evidence/*.log`

运行副产品只在报告中引用路径,不要把大日志全文贴进报告。

## 阶段 SOP

### SCOPE_REVIEW

输入:`plan_path` + `${output_dir}/build-scope-v{N}.md`。

步骤:

1. Read plan 和 build-scope。
2. 把 plan 翻译成可测业务场景清单。
3. 对照 build-scope 逐项检查需求覆盖和验证目标。
4. plan 缺验收标准时补全 QA 期望,但不替 Builder 做技术决策。
5. 产出 `${output_dir}/scope-review-v{N}.md`。
6. 覆盖完整且可测:

```bash
complete_stage "harness-qa" "ALIGNED" "scope 完整可测" "${output_dir}/scope-review-v{N}.md"
```

7. 需要调整:

```bash
complete_stage "harness-qa" "NEEDS_ADJUSTMENT" "scope 需调整: 1. ... 2. ..." "${output_dir}/scope-review-v{N}.md"
```

### REVIEW

输入:最终 `build-scope-v{N}.md` + 本轮 git diff。

步骤:

1. 创建 `${output_dir}/qa-evidence/`。
2. `git diff --name-only $(git rev-parse HEAD~)..HEAD > ${output_dir}/qa-evidence/diff-files.txt`。
3. Read 本轮改动文件,不要卷入存量代码。
4. 从 diff 中提取测试类,跑本轮相关测试:

```bash
mvn test -Dtest=ClassA,ClassB,... > "${output_dir}/qa-evidence/junit.log" 2>&1
echo "EXIT=$?" >> "${output_dir}/qa-evidence/junit.log"
mvn test-compile > "${output_dir}/qa-evidence/test-compile.log" 2>&1
echo "EXIT=$?" >> "${output_dir}/qa-evidence/test-compile.log"
```

5. 审计四类红线:stub、入口层业务逻辑、Service 契约测试完整性、假断言。
6. 为每个核心场景写 curl + 期望 JSON 套餐。
7. 产出 `qa-feedback-round-{N}.md`。
8. 全部通过:

```bash
complete_stage "harness-qa" "APPROVED" "四维全过 + 冒烟套餐已附" "${output_dir}/qa-feedback-round-{N}.md"
```

9. 有阻断问题:

```bash
complete_stage "harness-qa" "REJECTED" "1. ... 2. ..." "${output_dir}/qa-feedback-round-{N}.md"
```

禁忌:不跑全量 `mvn test`;不把无证据项判 PASS;不使用“总体不错”“小问题不影响”这类放水措辞。

### REVIEW_FIX

输入:上一轮 `qa-feedback-round-{N}.md` + 本轮 git diff。

步骤:

1. 跑修复涉及测试 + `mvn test-compile`。
2. 对照上一轮 P0/P1 验证根因是否真修。
3. API 行为变化时同步更新冒烟套餐。
4. 产出 `qa-feedback-round-{N+1}.md`。
5. 通过则 `APPROVED`,未通过则 `REJECTED`。

### USER_ADJUST_REVIEW

输入:`${output_dir}/user-adjustment-round-{N}.md` + 本轮 git diff。

步骤:

1. Read 用户调整原文。
2. 逐条核对用户需求和 Builder 实际改动。
3. 跑本轮调整涉及测试 + `mvn test-compile`。
4. 对照受影响 curl 套餐是否需要变化。
5. 全部通过:

```bash
complete_stage "harness-qa" "USER_ADJUST_VERIFIED" "用户调整验证通过" "${output_dir}/user-adjustment-round-{N}.md"
```

6. 不通过:

```bash
complete_stage "harness-qa" "USER_ADJUST_REJECTED" "1. ... 2. ..." "${output_dir}/user-adjustment-round-{N}.md"
```

## 基线遗留

若任务 prompt 带 BASELINE_NOTE,把相关失败识别为基线遗留,不要计入本轮问题。
