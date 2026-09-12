#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
trap 'find "$work_dir" -depth -delete' EXIT

# Check language-neutral development rules.
rules="$repo_root/common/refs/keel-dev-coding-rules.md"
orchestration="$repo_root/common/refs/keel-dev-orchestration.md"
for marker in '对外业务契约' '函数、模块' '测试命名、扩展名、位置和发现规则沿用项目约定' '不要求所有语言都有独立编译阶段'; do
  grep -Fq "$marker" "$rules" || { echo "缺少语言无关契约: $marker" >&2; exit 1; }
done
grep -Fq 'not-applicable' "$orchestration"
grep -Fq '无法执行不等于不适用' "$orchestration"
if rg -n 'QA_<被测类名>_<场景>\.java|业务逻辑放在 Service|TDD 单测.*只.*Service|非 Maven 项目按项目手册执行' \
  "$repo_root/common/refs" "$repo_root/keel-dev"; then
  echo "runtime 恢复了 Java 专属强制约定" >&2
  exit 1
fi

for required in \
  "keel-plan/skills/keel-plan/assets/plan-template.md" \
  "keel-plan/skills/keel-plan/assets/plan-view-template.html" \
  "keel-plan/skills/keel-plan/scripts/render-plan-html.sh" \
  "keel-dev/agents/keel-builder.toml" \
  "keel-dev/agents/keel-qa.toml" \
  "keel-dev/agents/keel-call-chain.toml"; do
  [ -f "$repo_root/$required" ] || { echo "缺少 runtime 文件: $required" >&2; exit 1; }
done
if rg -n -i 'build-scope|scope_review|keel-code-review|CODE_REVIEW|claude-code|\.claude/' \
  "$repo_root/keel-plan" "$repo_root/keel-dev" "$repo_root/common" "$repo_root/bin"; then
  echo "单 runtime 中存在已移除能力引用" >&2
  exit 1
fi

runtime_dir="$work_dir/runtime"
mkdir -p "$runtime_dir"
cp "$repo_root/keel-plan/skills/keel-plan/assets/plan-template.md" "$runtime_dir/plan.md"
(
  export PROJECT_DIR="$runtime_dir"
  source "$repo_root/common/scripts/keel-init.sh"
  full_state="$(init_keel_run "$runtime_dir/full" "$runtime_dir/plan.md")"
  fast_state="$(init_keel_fast_run "$runtime_dir/fast" "$runtime_dir/plan.md")"
  jq -e '
    .artifacts.code_review == null
    and .artifacts.build_scope == null
    and .artifacts.scope_review == null
    and .artifacts.qa_feedback != null
    and .plan_path != null
    and (has("implementation_plan_path") | not)
    and .scope_attempt == null
    and .limits.scope_attempts == null
    and (.review | keys == ["qa"])
  ' "$full_state" >/dev/null
  jq -e '
    .artifacts.code_review == null
    and .artifacts.qa_feedback != null
    and .plan_path != null
    and (has("implementation_plan_path") | not)
    and (.review | keys == ["qa"])
    and (.fast.skipped | index("qa") | not)
    and (.fast.skipped | index("scope-review") | not)
  ' "$fast_state" >/dev/null
)

echo "Codex App 单 runtime 与语言无关契约检查通过。"
