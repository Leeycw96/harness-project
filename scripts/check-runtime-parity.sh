#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
trap 'find "$work_dir" -depth -delete' EXIT

normalize() {
  local source_file="$1" output_file="$2" strip_frontmatter="${3:-false}"
  awk -v strip_frontmatter="$strip_frontmatter" '
    NR == 1 && strip_frontmatter == "true" && $0 == "---" {
      in_frontmatter = 1
      next
    }
    in_frontmatter && $0 == "---" {
      in_frontmatter = 0
      next
    }
    in_frontmatter { next }
    strip_frontmatter == "true" && !started && $0 == "" { next }
    {
      started = 1
      gsub(/\.agents\/skills\//, ".runtime/skills/")
      gsub(/\.codex\//, ".runtime/")
      gsub(/\.claude\//, ".runtime/")
      gsub(/Codex App/, "Harness Runtime")
      gsub(/Claude Code/, "Harness Runtime")
      print
    }
  ' "$source_file" > "$output_file"
}

compare_pair() {
  local label="$1" codex_file="$2" claude_file="$3" strip_frontmatter="${4:-false}"
  normalize "$repo_root/$codex_file" "$work_dir/${label}-codex" "$strip_frontmatter"
  normalize "$repo_root/$claude_file" "$work_dir/${label}-claude" "$strip_frontmatter"
  if ! diff -u "$work_dir/${label}-codex" "$work_dir/${label}-claude"; then
    echo "runtime 语义不一致: $label" >&2
    return 1
  fi
}

compare_pair "coding-rules" \
  "common/refs/harness-backend-coding-rules.md" \
  "claude-code/common/refs/harness-backend-coding-rules.md" \
  "true"

for removed in \
  "harness-backend/skills/harness-backend-fix/SKILL.md" \
  "harness-backend/agents/harness-feedback-triage.md" \
  "harness-backend/agents/harness-code-review.md" \
  "harness-backend/agents/harness-code-review.toml" \
  "claude-code/harness-backend/skills/harness-backend-fix/SKILL.md" \
  "claude-code/harness-backend/agents/harness-feedback-triage.md"; do
  if [ -e "$repo_root/$removed" ]; then
    echo "已删除能力仍存在: $removed" >&2
    exit 1
  fi
done

for retained in \
  "claude-code/harness-backend/agents/harness-code-review.md"; do
  if [ ! -f "$repo_root/$retained" ]; then
    echo "Claude Code 保留能力缺失: $retained" >&2
    exit 1
  fi
done

for codex_only_plan_file in \
  "assets/implementation-plan-template.md" \
  "assets/plan-view-template.html" \
  "scripts/render-plan-html.sh"; do
  if [ ! -f "$repo_root/harness-plan/skills/harness-plan/$codex_only_plan_file" ]; then
    echo "Codex App Plan 文件缺失: $codex_only_plan_file" >&2
    exit 1
  fi
  if [ -e "$repo_root/claude-code/harness-plan/skills/harness-plan/$codex_only_plan_file" ]; then
    echo "Claude Code runtime 不应包含 Codex App Plan 文件: $codex_only_plan_file" >&2
    exit 1
  fi
done

if rg -n -i \
  'build-scope|scope.review|scope_review|build_scope|SCOPE_BUILD|SCOPE_REVIEW|scope_attempt' \
  "$repo_root/harness-plan" "$repo_root/harness-backend" "$repo_root/common"; then
  echo "Codex App runtime 仍含 build-scope 活跃引用" >&2
  exit 1
fi
if ! rg -q 'SCOPE_BUILD|build-scope' "$repo_root/claude-code/harness-backend"; then
  echo "Claude Code runtime 的 build-scope 流程被意外移除" >&2
  exit 1
fi

if rg -n \
  'harness-code-review|code-review\.md|review\.code_review|CODE_REVIEW' \
  "$repo_root/harness-backend" "$repo_root/common" \
  --glob '!**/refs/harness-backend-orchestration.md'; then
  echo "Codex App runtime 仍含 CodeReview 活跃引用" >&2
  exit 1
fi

runtime_dir="$work_dir/runtime"
mkdir -p "$runtime_dir"
touch "$runtime_dir/plan.md" "$runtime_dir/implementation-plan.md"
(
  export PROJECT_DIR="$runtime_dir"
  source "$repo_root/common/scripts/harness-init.sh"
  full_state="$(init_harness_run "$runtime_dir/full" "$runtime_dir/plan.md" "$runtime_dir/implementation-plan.md")"
  fast_state="$(init_harness_fast_run "$runtime_dir/fast" "$runtime_dir/plan.md" "$runtime_dir/implementation-plan.md")"
  jq -e '
    .artifacts.code_review == null
    and .artifacts.build_scope == null
    and .artifacts.scope_review == null
    and .artifacts.qa_feedback != null
    and .implementation_plan_path != null
    and .scope_attempt == null
    and .limits.scope_attempts == null
    and (.review | keys == ["qa"])
  ' "$full_state" >/dev/null
  jq -e '
    .artifacts.code_review == null
    and .artifacts.qa_feedback != null
    and .implementation_plan_path != null
    and (.review | keys == ["qa"])
    and (.fast.skipped | index("qa") | not)
    and (.fast.skipped | index("scope-review") | not)
  ' "$fast_state" >/dev/null
)

echo "共享编码规则及 Codex/Claude 计划、build-scope、CodeReview 有意分叉检查通过。"
