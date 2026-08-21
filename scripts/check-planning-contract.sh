#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plan_skill="$repo_root/harness-plan/skills/harness-plan/SKILL.md"
xml_template="$repo_root/harness-plan/skills/harness-plan/assets/plan-template.xml"
implementation_template="$repo_root/harness-plan/skills/harness-plan/assets/implementation-plan-template.md"
work_dir="$(mktemp -d)"
trap 'find "$work_dir" -depth -delete' EXIT

for required_file in "$plan_skill" "$xml_template" "$implementation_template"; do
  if [ ! -f "$required_file" ]; then
    echo "缺少 Plan 契约文件: $required_file" >&2
    exit 1
  fi
done

if ! command -v xmllint >/dev/null 2>&1; then
  echo "错误: xmllint 未安装，无法验证 Plan XML" >&2
  exit 1
fi
xmllint --noout "$xml_template"

if [ "$(grep -Ec '^[[:space:]]*<implementation-plan path="\.harness/plans/[^"]+-implementation\.md"[[:space:]]*/>[[:space:]]*$' "$xml_template")" -ne 1 ]; then
  echo "Plan XML 必须且仅能包含一个合法的 implementation-plan 声明" >&2
  exit 1
fi

for heading in \
  "Purpose" \
  "Current Flow" \
  "Target Flow" \
  "Change Map" \
  "Interfaces and Data" \
  "Technical Decisions" \
  "Cross-cutting Constraints" \
  "Implementation Sequence" \
  "Validation" \
  "Risks and Recovery"; do
  if ! grep -Fxq "## $heading" "$implementation_template"; then
    echo "代码改造计划模板缺少章节: $heading" >&2
    exit 1
  fi
done

for required_pattern in \
  '\.harness/call-chain/\*\.md' \
  '询问用户是否进行外部调研' \
  '用户拒绝且未指定方案时暂停' \
  '\.harness/plans/<name>\.md' \
  '\.harness/plans/<name>-implementation\.md'; do
  if ! rg -q "$required_pattern" "$plan_skill"; then
    echo "Harness Plan Skill 缺少契约: $required_pattern" >&2
    exit 1
  fi
done

if rg -n -i \
  'build-scope|scope.review|scope_review|build_scope|SCOPE_BUILD|SCOPE_REVIEW|scope_attempt' \
  "$repo_root/harness-plan" "$repo_root/harness-backend" "$repo_root/common"; then
  echo "Codex App runtime 仍含 build-scope 活跃引用" >&2
  exit 1
fi

mkdir -p "$work_dir/.harness/plans" "$work_dir/run-input"
cp "$implementation_template" "$work_dir/.harness/plans/example-implementation.md"
sed \
  's#\.harness/plans/order-cancellation-implementation\.md#.harness/plans/example-implementation.md#' \
  "$xml_template" > "$work_dir/.harness/plans/example.md"
cp "$work_dir/.harness/plans/example.md" "$work_dir/run-input/plan.md"
cp "$work_dir/.harness/plans/example-implementation.md" "$work_dir/run-input/implementation-plan.md"

(
  export PROJECT_DIR="$work_dir"
  source "$repo_root/common/scripts/harness-init.sh"

  resolved="$(resolve_implementation_plan_path "$work_dir/.harness/plans/example.md")"
  [ "$resolved" = "$work_dir/.harness/plans/example-implementation.md" ]

  if init_harness_run "$work_dir/missing-input" "$work_dir/run-input/plan.md" >/dev/null 2>&1; then
    echo "init_harness_run 未拒绝缺失的代码改造计划" >&2
    exit 1
  fi

  full_state="$(init_harness_run "$work_dir/full" "$work_dir/run-input/plan.md" "$work_dir/run-input/implementation-plan.md")"
  fast_state="$(init_harness_fast_run "$work_dir/fast" "$work_dir/run-input/plan.md" "$work_dir/run-input/implementation-plan.md")"

  jq -e '
    .implementation_plan_path != null
    and .artifacts.build_scope == null
    and .artifacts.scope_review == null
    and .limits.scope_attempts == null
    and .scope_attempt == null
  ' "$full_state" >/dev/null
  jq -e '
    .implementation_plan_path != null
    and (.fast.skipped | index("scope-review") | not)
  ' "$fast_state" >/dev/null
)

echo "Codex App Harness Plan 双产物与 Backend 无 build-scope 契约检查通过。"
