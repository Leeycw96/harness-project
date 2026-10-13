#!/usr/bin/env bash
set -euo pipefail

# Keel Codex App initialization helpers.
# This runtime is subagent-only: no tmux, panes, send-keys, or direct agent chat.

SCRIPT_PATH="${BASH_SOURCE[0]-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"

_abs_path() {
  local p="$1"
  case "$p" in
    /*) printf '%s\n' "$p" ;;
    *) printf '%s/%s\n' "$PROJECT_DIR" "$p" ;;
  esac
}

get_latest_run_number() {
  local branch_dir="$1"
  [ -d "$branch_dir" ] || { echo "0"; return; }
  local max=0 d n
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    n="${d##*/run-}"
    [[ "$n" =~ ^[0-9]+$ ]] || continue
    (( n > max )) && max=$n
  done < <(find "$branch_dir" -mindepth 1 -maxdepth 1 -type d -name 'run-*' 2>/dev/null)
  echo "$max"
}

get_next_run_number() {
  local branch_dir="$1"
  local latest
  latest="$(get_latest_run_number "$branch_dir")"
  echo $((latest + 1))
}

validate_keel_plan() {
  local plan_path="${1:-}"
  [ -n "$plan_path" ] || { echo "用法: validate_keel_plan <plan_path>" >&2; return 2; }
  command -v python3 >/dev/null 2>&1 || { echo "错误: 需要 Python 3 验证 Markdown 计划" >&2; return 1; }
  python3 "$SCRIPT_DIR/keel-plan.py" validate "$(_abs_path "$plan_path")"
}

init_keel_run() {
  local output_dir="${1:-}"
  local plan_path="${2:-}"
  if [ "$#" -ne 2 ] || [ -z "$output_dir" ] || [ -z "$plan_path" ]; then
    echo "用法: init_keel_run <output_dir> <plan_path>" >&2
    return 2
  fi

  output_dir="$(_abs_path "$output_dir")"
  plan_path="$(_abs_path "$plan_path")"
  command -v python3 >/dev/null 2>&1 || { echo "错误: 需要 Python 3 快照 Markdown 计划" >&2; return 1; }
  python3 "$SCRIPT_DIR/keel-plan.py" snapshot "$plan_path" "$output_dir"
}
