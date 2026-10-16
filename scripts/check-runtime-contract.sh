#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
work_dir="$(cd "$work_dir" && pwd -P)"
trap 'find "$work_dir" -depth -delete' EXIT

# Check language-neutral development rules.
rules="$repo_root/common/refs/keel-code-quality-spec.md"
orchestration="$repo_root/keel-dev/skills/keel-dev/SKILL.md"
for marker in '别人会调用的业务能力' '函数、模块' '测试文件的名字、后缀、目录和运行方式沿用项目约定' '项目没有编译步骤'; do
  grep -Fq "$marker" "$rules" || { echo "缺少语言无关契约: $marker" >&2; exit 1; }
done
grep -Fq '无法执行不等于不适用' "$orchestration"
if rg -n 'QA_<被测类名>_<场景>\.java|业务逻辑放在 Service|TDD 单测.*只.*Service|非 Maven 项目按项目手册执行' \
  "$repo_root/common/refs" "$repo_root/keel-dev"; then
  echo "runtime 恢复了 Java 专属强制约定" >&2
  exit 1
fi

for required in \
  "keel-plan/skills/keel-plan/assets/plan-template.md" \
  "keel-plan/skills/keel-plan/assets/plan-template.features/cancel-order.md" \
  "keel-plan/skills/keel-plan/assets/plan-template.features/confirm-refund.md" \
  "keel-plan/skills/keel-plan/assets/plan-review-template.md" \
  "keel-plan/skills/keel-plan/assets/plan-view-template.html" \
  "keel-plan/skills/keel-plan/assets/data-model-example.html" \
  "keel-plan/skills/keel-plan/assets/interface-example.html" \
  "keel-plan/skills/keel-plan/scripts/render-plan-html.sh" \
  "keel-plan/agents/keel-planner.toml" \
  "keel-plan/agents/keel-planner.md" \
  "common/refs/keel-code-change-spec.md" \
  "common/refs/keel-business-flow-spec.md" \
  "common/refs/keel-delivery-spec.md" \
  "common/refs/keel-code-quality-spec.md" \
  "common/refs/keel-document-writing-spec.md" \
  "common/refs/keel-implementation-spec.md" \
  "common/refs/keel-investigation-spec.md" \
  "common/refs/keel-proposal-spec.md" \
  "common/refs/keel-fix-review-spec.md" \
  "common/refs/keel-acceptance-spec.md" \
  "common/refs/keel-qa-scoring-spec.md" \
  "common/scripts/keel-init.sh" \
  "common/scripts/keel-plan.py" \
  "common/scripts/keel-qa-score.py" \
  "common/refs/keel-flow-index-spec.md" \
  "common/refs/keel-bug-scope-spec.md" \
  "keel-dev/skills/keel-fix/SKILL.md" \
  "keel-dev/skills/keel-fix/assets/bug-template.md" \
  "keel-dev/skills/keel-fix/assets/investigation-template.md" \
  "keel-dev/skills/keel-fix/scripts/keel-fix.py" \
  "keel-dev/agents/keel-builder.toml" \
  "keel-dev/agents/keel-qa.toml" \
  "keel-dev/agents/keel-doc-writer.toml"; do
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
cp -R "$repo_root/keel-plan/skills/keel-plan/assets/plan-template.features" "$runtime_dir/"
(
  export PROJECT_DIR="$runtime_dir"
  source "$repo_root/common/scripts/keel-init.sh"
  run_plan="$(init_keel_run "$runtime_dir/full" "$runtime_dir/plan.md")"
  [ "$run_plan" = "$runtime_dir/full/plan.md" ]
  validate_keel_plan "$run_plan" >/dev/null
  [ ! -e "$runtime_dir/full/state.json" ]
  [ ! -e "$runtime_dir/full/profile.json" ]
)

python3 "$repo_root/scripts/test-aso-contract.py"
python3 "$repo_root/scripts/test-fix-contract.py"
python3 "$repo_root/scripts/test-qa-score.py"

echo "Codex App 单 runtime、任务＋Spec 输入与语言无关契约检查通过。"
