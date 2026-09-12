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
measure_file "codex-plan-skill" "keel-plan/skills/keel-plan/SKILL.md"
measure_file "codex-plan-template" "keel-plan/skills/keel-plan/assets/plan-template.md"
measure_file "codex-orchestration-contract" "common/refs/keel-dev-orchestration.md"
measure_file "codex-full-skill" "keel-dev/skills/keel-dev/SKILL.md"
measure_sum "codex-full-effective-input" \
  "keel-dev/skills/keel-dev/SKILL.md" \
  "common/refs/keel-dev-orchestration.md"
measure_file "codex-fast-skill" "keel-dev/skills/keel-dev-fast/SKILL.md"
measure_sum "codex-fast-effective-input" \
  "keel-dev/skills/keel-dev-fast/SKILL.md" \
  "common/refs/keel-dev-orchestration.md"
measure_file "codex-builder-instructions" "keel-dev/agents/keel-builder.md"
measure_file "codex-qa-instructions" "keel-dev/agents/keel-qa.md"
measure_file "codex-call-chain-instructions" "keel-dev/agents/keel-call-chain.md"
measure_tree "codex-runtime" keel-plan keel-dev common
