#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
baseline_file="$repo_root/evals/keel/baseline-2.1.0.tsv"

baseline_chars() {
  local component="$1"
  awk -F '\t' -v component="$component" '$1 == component { print $3 }' "$baseline_file"
}

metrics="$("$repo_root/scripts/keel-metrics.sh")"
current_chars() {
  local component="$1"
  awk -F '\t' -v component="$component" '$1 == component { print $3 }' <<< "$metrics"
}

check_reduction() {
  local component="$1" current="$2" required_percent="$3"
  local baseline actual_percent
  [[ "$current" =~ ^[0-9]+$ ]] || { echo "缺少当前体量: $component" >&2; return 1; }
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

check_reduction "codex-full-effective-input" "$(current_chars codex-full-effective-input)" 40
check_reduction "codex-fast-effective-input" "$(current_chars codex-fast-effective-input)" 40
# Compare Agent instructions plus relocated task/spec sections against the original scope.
for role in builder qa call-chain; do
  check_reduction "codex-$role-instructions" "$(current_chars "codex-$role-baseline-input")" 30
done
