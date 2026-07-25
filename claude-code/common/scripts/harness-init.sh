#!/usr/bin/env bash
set -euo pipefail

# Harness Claude Code initialization helpers.
# This runtime is subagent-only: no tmux, panes, send-keys, or direct agent chat.

SCRIPT_PATH="${BASH_SOURCE[0]-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
mkdir -p "$PROJECT_DIR/.harness"

if ! command -v jq >/dev/null 2>&1; then
  echo "错误: jq 未安装,请先执行 brew install jq" >&2
  exit 1
fi

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

init_harness_run() {
  local output_dir="$1"
  local plan_path="$2"
  if [ -z "$output_dir" ] || [ -z "$plan_path" ]; then
    echo "用法: init_harness_run <output_dir> <plan_path>" >&2
    return 2
  fi

  output_dir="$(_abs_path "$output_dir")"
  plan_path="$(_abs_path "$plan_path")"
  mkdir -p "$output_dir"

  local state_file="$output_dir/state.json"

  jq -n \
    --arg project_dir "$PROJECT_DIR" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    '{
      runtime: "claude-code",
      mode: "full",
      project_dir: $project_dir,
      output_dir: $output_dir,
      plan_path: $plan_path,
      artifacts: {
        build_scope: ($output_dir + "/build-scope.md"),
        scope_review: ($output_dir + "/scope-review.md"),
        qa_feedback: ($output_dir + "/qa-feedback.md"),
        code_review: ($output_dir + "/code-review.md"),
        fix_brief: ($output_dir + "/fix-brief.md"),
        call_chain_review: ($output_dir + "/call-chain-review.md")
      },
      thresholds: {
        short_stage_no_progress_seconds: 300,
        long_stage_no_progress_seconds: 900
      },
      limits: {
        scope_attempts: 3,
        fix_rounds: 3,
        stage_recoveries: 2
      },
      phase: "INIT",
      preflight: {
        main_compile: { status: "pending", summary: [] },
        test_compile: { status: "pending", summary: [], user_decision: null }
      },
      scope_attempt: 0,
      build: {
        current_slice: null,
        completed_slices: [],
        commits: []
      },
      review: {
        qa: { status: "pending", artifact: null, blocking_count: 0 },
        code_review: { status: "pending", artifact: null, p0: 0, p1: 0, p2: 0 }
      },
      call_chain: {
        status: "pending",
        artifact: null,
        action: null,
        commit: null,
        prefilter: {
          mode: "on-demand",
          decision: null,
          reason: null,
          agent_decision: null,
          agreement: null,
          safe: null,
          evaluated_at: null,
          compared_at: null
        }
      },
      fix_round: 0,
      retries: {}
    }' > "$state_file"

  : > "$output_dir/progress.tsv"
  export HARNESS_PROFILE="$state_file"
  printf '%s\n' "$state_file"
}

init_harness_fast_run() {
  local output_dir="$1"
  local plan_path="$2"
  if [ -z "$output_dir" ] || [ -z "$plan_path" ]; then
    echo "用法: init_harness_fast_run <output_dir> <plan_path>" >&2
    return 2
  fi

  output_dir="$(_abs_path "$output_dir")"
  plan_path="$(_abs_path "$plan_path")"
  mkdir -p "$output_dir"

  local state_file="$output_dir/state.json"

  jq -n \
    --arg project_dir "$PROJECT_DIR" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    '{
      runtime: "claude-code",
      mode: "fast",
      project_dir: $project_dir,
      output_dir: $output_dir,
      plan_path: $plan_path,
      artifacts: {
        code_review: ($output_dir + "/code-review.md"),
        fix_brief: ($output_dir + "/fix-brief.md")
      },
      thresholds: {
        short_stage_no_progress_seconds: 300,
        long_stage_no_progress_seconds: 900
      },
      limits: {
        fix_rounds: 3,
        stage_recoveries: 2
      },
      phase: "INIT",
      preflight: {
        main_compile: { status: "pending", summary: [] },
        test_compile: { status: "pending", summary: [], user_decision: null }
      },
      build: {
        current_slice: "fast",
        completed_slices: [],
        commits: []
      },
      review: {
        code_review: { status: "pending", artifact: null, p0: 0, p1: 0, p2: 0 }
      },
      fast: {
        skipped: ["qa", "scope-review", "call-chain"]
      },
      fix_round: 0,
      retries: {}
    }' > "$state_file"

  : > "$output_dir/progress.tsv"
  export HARNESS_PROFILE="$state_file"
  printf '%s\n' "$state_file"
}

source "$SCRIPT_DIR/harness-common.sh"
