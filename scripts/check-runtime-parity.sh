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

compare_pair "plan" \
  "harness-plan/skills/harness-plan/SKILL.md" \
  "claude-code/harness-plan/skills/harness-plan/SKILL.md"
compare_pair "full" \
  "harness-backend/skills/harness-backend/SKILL.md" \
  "claude-code/harness-backend/skills/harness-backend/SKILL.md"
compare_pair "fast" \
  "harness-backend/skills/harness-backend-fast/SKILL.md" \
  "claude-code/harness-backend/skills/harness-backend-fast/SKILL.md"
compare_pair "orchestration" \
  "common/refs/harness-backend-orchestration.md" \
  "claude-code/common/refs/harness-backend-orchestration.md"
compare_pair "coding-rules" \
  "common/refs/harness-backend-coding-rules.md" \
  "claude-code/common/refs/harness-backend-coding-rules.md"

for agent in builder qa code-review call-chain; do
  compare_pair "$agent" \
    "harness-backend/agents/harness-${agent}.md" \
    "claude-code/harness-backend/agents/harness-${agent}.md" \
    "true"
done

for removed in \
  "harness-backend/skills/harness-backend-fix/SKILL.md" \
  "harness-backend/agents/harness-feedback-triage.md" \
  "claude-code/harness-backend/skills/harness-backend-fix/SKILL.md" \
  "claude-code/harness-backend/agents/harness-feedback-triage.md"; do
  if [ -e "$repo_root/$removed" ]; then
    echo "已删除能力仍存在: $removed" >&2
    exit 1
  fi
done

echo "Codex App 与 Claude Code runtime 语义检查通过。"
