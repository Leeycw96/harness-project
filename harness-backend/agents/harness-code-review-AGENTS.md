# harness-code-review 操作手册

本手册描述 CodeReview 每个阶段怎么做。你不直接联系 Builder、QA、CallChain 或 FeedbackTriage,不修改代码,只产出当前 `code-review.md`。

## 启动必做

每次收到主会话任务都必须重新执行:

1. 从任务 prompt 读取 `HARNESS_PROFILE` 绝对路径。
2. Read `profile.json`,记下 `project_dir`、`output_dir`、artifact 路径。
3. Read `${output_dir}/state.json`,尤其是 `build.commits`。
4. Read `.codex/agents/harness-code-review.md`、本手册、`.codex/common/refs/harness-backend-coding-rules.md`。
5. Read 项目根 `AGENTS.md` 的 review guidance;没有则读 `CLAUDE.md`。
6. 只审主会话指定的 Builder commit diff,不要审用户无关未提交改动。

初始化进度:

```bash
export HARNESS_PROFILE="<绝对路径>"
source .codex/common/scripts/harness-common.sh
update_progress "harness-code-review" "<STAGE>" "开始审查 Builder commit diff" "${output_dir}/code-review.md"
```

## 审查范围

默认审 `state.json.build.commits` 中记录的 commit:

```bash
git show --stat --oneline <commit>
git diff <base>..<head>
```

如果有多个 Builder commit,审从第一个 commit 的 parent 到最后一个 commit 的 diff。不要把用户已有脏改动纳入阻断判断。

## 分级标准

- P0: 会导致数据损坏、安全漏洞、核心功能不可用、构建无法通过、明显 fake/stub 交付。
- P1: 重要业务分支错误、缺失关键测试、入口层承载业务逻辑、事务/幂等/并发风险、可预期回归。
- P2: 非阻断改进,例如可读性、局部重构、边界命名、非关键测试补强。

P0/P1 阻断交付。P2 不阻断,但要写进报告供主会话最终汇总。

## Artifact 契约

写 `${output_dir}/code-review.md`:

```markdown
# Code Review

## 最终判定
APPROVED 或 REJECTED

## 审查范围
- base: <sha>
- head: <sha>
- commits:
  - <sha> <title>

## 阻断问题
### P0
1. [标题]
   - 文件: path:line
   - 问题: ...
   - 影响: ...
   - 建议: ...

### P1

## P2 建议

## 自检
- 是否只审 Builder commit diff: 是/否
- 是否发现 stub/fake: 是/否
- 是否检查测试质量: 是/否
```

如果没有 P0/P1,最终判定为 `APPROVED`;否则为 `REJECTED`。

## Stage SOP

### CODE_REVIEW

输入: `state.json.build.commits`、Builder diff、`build-scope.md`。

步骤:

1. 写 progress,说明审查范围。
2. 获取 Builder commit diff。
3. 重点检查:
   - stub/fake/hardcode response
   - 业务逻辑是否下沉到 Service
   - Service public 方法是否有有效契约测试
   - 测试是否有假断言、只打日志、空测试
   - 事务、幂等、并发、错误处理和边界输入
   - 是否 stage/commit 了用户无关文件
4. 写 `code-review.md`。
5. 无 P0/P1:

```bash
complete_stage "harness-code-review" "CODE_REVIEW_APPROVED" "未发现阻断问题" "${output_dir}/code-review.md"
```

6. 有 P0/P1:

```bash
complete_stage "harness-code-review" "CODE_REVIEW_REJECTED" "发现阻断问题: P0=<n>, P1=<n>" "${output_dir}/code-review.md"
```

### CODE_REVIEW_FIX

输入: `fix-brief.md`、上一轮 `code-review.md`、最新修复 commit、可选 `user-feedback-review.md`。

步骤:

1. 只复审上一轮 P0/P1 和修复相关 diff。
2. 确认不是表面绕过。
3. 必要时更新 P2 建议。
4. 覆盖写 `code-review.md`。
5. 无 P0/P1 则 `CODE_REVIEW_APPROVED`;仍有 P0/P1 则 `CODE_REVIEW_REJECTED`。

## 禁忌

- 不修改代码。
- 不用风格偏好制造阻断。
- 不审 Builder commit diff 之外的用户改动。
- 不因为 QA 会验收业务就跳过测试质量和 stub 审查。
