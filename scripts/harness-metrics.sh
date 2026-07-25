#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

measure_file() {
  local label="$1" file="$2"
  printf '%s\t%s\t%s\n' \
    "$label" \
    "$(wc -l < "$file" | tr -d ' ')" \
    "$(wc -m < "$file" | tr -d ' ')"
}

measure_tree() {
  local label="$1"
  shift
  local values
  values="$(find "$@" -type f -print0 | xargs -0 cat | wc -l -m)"
  printf '%s\t%s\n' "$label" "$(printf '%s' "$values" | xargs)"
}

measure_sum() {
  local label="$1"
  shift
  local lines=0 chars=0 file
  for file in "$@"; do
    lines=$((lines + $(wc -l < "$file" | tr -d ' ')))
    chars=$((chars + $(wc -m < "$file" | tr -d ' ')))
  done
  printf '%s\t%s\t%s\n' "$label" "$lines" "$chars"
}

printf 'component\tlines\tchars\n'
measure_file "codex-plan-skill" "harness-plan/skills/harness-plan/SKILL.md"
measure_file "codex-orchestration-contract" "common/refs/harness-backend-orchestration.md"
measure_file "codex-full-skill" "harness-backend/skills/harness-backend/SKILL.md"
measure_sum "codex-full-effective-input" \
  "harness-backend/skills/harness-backend/SKILL.md" \
  "common/refs/harness-backend-orchestration.md"
measure_file "codex-fast-skill" "harness-backend/skills/harness-backend-fast/SKILL.md"
measure_sum "codex-fast-effective-input" \
  "harness-backend/skills/harness-backend-fast/SKILL.md" \
  "common/refs/harness-backend-orchestration.md"
measure_file "codex-builder-instructions" "harness-backend/agents/harness-builder.md"
measure_file "codex-qa-instructions" "harness-backend/agents/harness-qa.md"
measure_file "codex-code-review-instructions" "harness-backend/agents/harness-code-review.md"
measure_file "codex-call-chain-instructions" "harness-backend/agents/harness-call-chain.md"
measure_tree "codex-runtime" harness-plan harness-backend common
measure_tree "claude-runtime" claude-code/harness-plan claude-code/harness-backend claude-code/common
