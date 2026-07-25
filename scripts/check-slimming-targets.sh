#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
baseline_file="$repo_root/evals/harness/baseline-2.1.0.tsv"

baseline_chars() {
  local component="$1"
  awk -F '\t' -v component="$component" '$1 == component { print $3 }' "$baseline_file"
}

file_chars() {
  wc -m < "$1" | tr -d ' '
}

sum_chars() {
  local total=0 file
  for file in "$@"; do
    total=$((total + $(file_chars "$file")))
  done
  printf '%s\n' "$total"
}

check_reduction() {
  local component="$1" current="$2" required_percent="$3"
  local baseline actual_percent
  baseline="$(baseline_chars "$component")"
  [ -n "$baseline" ] || {
    echo "缺少 baseline: $component" >&2
    return 1
  }
  if (( current * 100 > baseline * (100 - required_percent) )); then
    echo "$component 未达到 ${required_percent}% 缩减目标: baseline=$baseline current=$current" >&2
    return 1
  fi
  actual_percent=$((100 - current * 100 / baseline))
  echo "$component: ${actual_percent}% reduction"
}

check_reduction "codex-plan-skill" \
  "$(file_chars "$repo_root/harness-plan/skills/harness-plan/SKILL.md")" 40
check_reduction "codex-full-effective-input" \
  "$(sum_chars \
    "$repo_root/harness-backend/skills/harness-backend/SKILL.md" \
    "$repo_root/common/refs/harness-backend-orchestration.md")" 40
check_reduction "codex-fast-effective-input" \
  "$(sum_chars \
    "$repo_root/harness-backend/skills/harness-backend-fast/SKILL.md" \
    "$repo_root/common/refs/harness-backend-orchestration.md")" 40
check_reduction "codex-builder-instructions" \
  "$(file_chars "$repo_root/harness-backend/agents/harness-builder.md")" 30
check_reduction "codex-qa-instructions" \
  "$(file_chars "$repo_root/harness-backend/agents/harness-qa.md")" 30
check_reduction "codex-code-review-instructions" \
  "$(file_chars "$repo_root/harness-backend/agents/harness-code-review.md")" 30
check_reduction "codex-call-chain-instructions" \
  "$(file_chars "$repo_root/harness-backend/agents/harness-call-chain.md")" 30
