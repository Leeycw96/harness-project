#!/usr/bin/env bash
set -euo pipefail

# Harness Codex App initialization helpers.
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

copy_examples() {
  local src_dir="$1"
  if [ -d "$src_dir" ]; then
    mkdir -p "$PROJECT_DIR/.harness/examples"
    cp -R "$src_dir"/. "$PROJECT_DIR/.harness/examples/" 2>/dev/null || true
  fi
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

find_latest_done_run() {
  local branch_dir="$1"
  [ -d "$branch_dir" ] || return 1

  local latest=0 latest_dir="" d n state phase
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    state="$d/state.json"
    [ -f "$state" ] || continue
    phase="$(jq -r '.phase // empty' "$state" 2>/dev/null || true)"
    [ "$phase" = "DONE" ] || continue
    n="${d##*/run-}"
    [[ "$n" =~ ^[0-9]+$ ]] || continue
    if (( n > latest )); then
      latest="$n"
      latest_dir="$d"
    fi
  done < <(find "$branch_dir" -mindepth 1 -maxdepth 1 -type d -name 'run-*' 2>/dev/null)

  [ -n "$latest_dir" ] || return 1
  printf '%s\n' "$latest_dir"
}

find_latest_full_backend_done_run() {
  local branch_dir="$1"
  [ -d "$branch_dir" ] || return 1

  local latest=0 latest_dir="" d n state phase mode
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    state="$d/state.json"
    [ -f "$state" ] || continue
    phase="$(jq -r '.phase // empty' "$state" 2>/dev/null || true)"
    [ "$phase" = "DONE" ] || continue
    mode="$(jq -r '.mode // empty' "$state" 2>/dev/null || true)"
    case "$mode" in
      ""|backend|full) ;;
      *) continue ;;
    esac
    n="${d##*/run-}"
    [[ "$n" =~ ^[0-9]+$ ]] || continue
    if (( n > latest )); then
      latest="$n"
      latest_dir="$d"
    fi
  done < <(find "$branch_dir" -mindepth 1 -maxdepth 1 -type d -name 'run-*' 2>/dev/null)

  [ -n "$latest_dir" ] || return 1
  printf '%s\n' "$latest_dir"
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
  mkdir -p "$output_dir/progress"

  local profile_file="$output_dir/profile.json"
  local state_file="$output_dir/state.json"

  jq -n \
    --arg project_dir "$PROJECT_DIR" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    '{
      runtime: "codex-app",
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
      progress: {
        dir: ($output_dir + "/progress"),
        builder: ($output_dir + "/progress/builder.md"),
        qa: ($output_dir + "/progress/qa.md"),
        code_review: ($output_dir + "/progress/code-review.md"),
        call_chain: ($output_dir + "/progress/call-chain.md"),
        feedback_triage: ($output_dir + "/progress/feedback-triage.md"),
        events: ($output_dir + "/progress/events.tsv")
      },
      agents: {
        "harness-builder": {
          config: ".codex/agents/harness-builder.toml",
          role_doc: ".codex/agents/harness-builder.md",
          sop_doc: ".codex/agents/harness-builder-AGENTS.md"
        },
        "harness-qa": {
          config: ".codex/agents/harness-qa.toml",
          role_doc: ".codex/agents/harness-qa.md",
          sop_doc: ".codex/agents/harness-qa-AGENTS.md"
        },
        "harness-code-review": {
          config: ".codex/agents/harness-code-review.toml",
          role_doc: ".codex/agents/harness-code-review.md",
          sop_doc: ".codex/agents/harness-code-review-AGENTS.md"
        },
        "harness-call-chain": {
          config: ".codex/agents/harness-call-chain.toml",
          role_doc: ".codex/agents/harness-call-chain.md",
          sop_doc: ".codex/agents/harness-call-chain-AGENTS.md"
        },
        "harness-feedback-triage": {
          config: ".codex/agents/harness-feedback-triage.toml",
          role_doc: ".codex/agents/harness-feedback-triage.md",
          sop_doc: ".codex/agents/harness-feedback-triage-AGENTS.md"
        }
      },
      thresholds: {
        short_stage_no_progress_seconds: 300,
        long_stage_no_progress_seconds: 900
      },
      lifecycle: {
        reuse_subagents_across_stages: false,
        close_agent_after_stage: true,
        close_parallel_agent_when_done: true,
        close_stalled_agent_before_replacement: true
      },
      limits: {
        scope_attempts: 3,
        fix_rounds: 3,
        stage_recoveries: 2
      }
    }' > "$profile_file"

  jq -n \
    --arg profile_path "$profile_file" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    '{
      phase: "INIT",
      profile_path: $profile_path,
      output_dir: $output_dir,
      plan_path: $plan_path,
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
        commit: null
      },
      fix_round: 0,
      retries: {},
      events: [],
      next_action: "PREFLIGHT"
    }' > "$state_file"

  : > "$output_dir/progress/events.tsv"
  export HARNESS_PROFILE="$profile_file"
  printf '%s\n' "$profile_file"
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
  mkdir -p "$output_dir/progress"

  local profile_file="$output_dir/profile.json"
  local state_file="$output_dir/state.json"

  jq -n \
    --arg project_dir "$PROJECT_DIR" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    '{
      runtime: "codex-app",
      mode: "fast",
      project_dir: $project_dir,
      output_dir: $output_dir,
      plan_path: $plan_path,
      artifacts: {
        code_review: ($output_dir + "/code-review.md"),
        fix_brief: ($output_dir + "/fix-brief.md")
      },
      progress: {
        dir: ($output_dir + "/progress"),
        builder: ($output_dir + "/progress/builder.md"),
        code_review: ($output_dir + "/progress/code-review.md"),
        events: ($output_dir + "/progress/events.tsv")
      },
      agents: {
        "harness-builder": {
          config: ".codex/agents/harness-builder.toml",
          role_doc: ".codex/agents/harness-builder.md",
          sop_doc: ".codex/agents/harness-builder-AGENTS.md"
        },
        "harness-code-review": {
          config: ".codex/agents/harness-code-review.toml",
          role_doc: ".codex/agents/harness-code-review.md",
          sop_doc: ".codex/agents/harness-code-review-AGENTS.md"
        }
      },
      thresholds: {
        short_stage_no_progress_seconds: 300,
        long_stage_no_progress_seconds: 900
      },
      lifecycle: {
        reuse_subagents_across_stages: false,
        close_agent_after_stage: true,
        close_parallel_agent_when_done: true,
        close_stalled_agent_before_replacement: true
      },
      limits: {
        fix_rounds: 3,
        stage_recoveries: 2
      }
    }' > "$profile_file"

  jq -n \
    --arg profile_path "$profile_file" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    '{
      phase: "INIT",
      mode: "fast",
      profile_path: $profile_path,
      output_dir: $output_dir,
      plan_path: $plan_path,
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
      retries: {},
      events: [],
      next_action: "PREFLIGHT"
    }' > "$state_file"

  : > "$output_dir/progress/events.tsv"
  export HARNESS_PROFILE="$profile_file"
  printf '%s\n' "$profile_file"
}

init_harness_fix_run() {
  local output_dir="$1"
  local source_run="$2"
  local user_feedback_path="$3"
  if [ -z "$output_dir" ] || [ -z "$source_run" ] || [ -z "$user_feedback_path" ]; then
    echo "用法: init_harness_fix_run <output_dir> <source-run-dir> <user-feedback-file>" >&2
    return 2
  fi

  output_dir="$(_abs_path "$output_dir")"
  source_run="$(_abs_path "$source_run")"
  user_feedback_path="$(_abs_path "$user_feedback_path")"

  local source_state="$source_run/state.json"
  [ -f "$source_state" ] || {
    echo "错误: source run 缺少 state.json: $source_state" >&2
    return 1
  }
  [ -f "$source_run/plan.md" ] || {
    echo "错误: source run 缺少 plan.md: $source_run/plan.md" >&2
    return 1
  }
  [ -f "$user_feedback_path" ] || {
    echo "错误: 用户反馈文件不存在: $user_feedback_path" >&2
    return 1
  }

  local source_phase
  source_phase="$(jq -r '.phase // empty' "$source_state")"
  if [ "$source_phase" != "DONE" ]; then
    echo "错误: source run phase 必须是 DONE,当前为: ${source_phase:-<empty>}" >&2
    return 1
  fi

  mkdir -p "$output_dir/progress"

  local artifact
  for artifact in plan.md build-scope.md scope-review.md qa-feedback.md code-review.md call-chain-review.md; do
    [ -f "$source_run/$artifact" ] && cp "$source_run/$artifact" "$output_dir/$artifact"
  done

  local feedback_dest="$output_dir/user-feedback.md"
  if [ "$user_feedback_path" != "$feedback_dest" ]; then
    cp "$user_feedback_path" "$feedback_dest"
  fi

  local profile_file="$output_dir/profile.json"
  local state_file="$output_dir/state.json"
  local plan_path="$output_dir/plan.md"
  local source_build_commits
  source_build_commits="$(jq -c 'reduce (((.source.build_commits // []) + (.build.commits // []))[]) as $sha ([]; if index($sha) then . else . + [$sha] end)' "$source_state")"

  jq -n \
    --arg project_dir "$PROJECT_DIR" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    --arg source_run "$source_run" \
    '{
      runtime: "codex-app",
      mode: "post-review-fix",
      project_dir: $project_dir,
      output_dir: $output_dir,
      plan_path: $plan_path,
      source_run: $source_run,
      artifacts: {
        build_scope: ($output_dir + "/build-scope.md"),
        scope_review: ($output_dir + "/scope-review.md"),
        qa_feedback: ($output_dir + "/qa-feedback.md"),
        code_review: ($output_dir + "/code-review.md"),
        fix_brief: ($output_dir + "/fix-brief.md"),
        call_chain_review: ($output_dir + "/call-chain-review.md"),
        user_feedback: ($output_dir + "/user-feedback.md"),
        user_feedback_review: ($output_dir + "/user-feedback-review.md")
      },
      progress: {
        dir: ($output_dir + "/progress"),
        feedback_triage: ($output_dir + "/progress/feedback-triage.md"),
        builder: ($output_dir + "/progress/builder.md"),
        qa: ($output_dir + "/progress/qa.md"),
        code_review: ($output_dir + "/progress/code-review.md"),
        call_chain: ($output_dir + "/progress/call-chain.md"),
        events: ($output_dir + "/progress/events.tsv")
      },
      agents: {
        "harness-feedback-triage": {
          config: ".codex/agents/harness-feedback-triage.toml",
          role_doc: ".codex/agents/harness-feedback-triage.md",
          sop_doc: ".codex/agents/harness-feedback-triage-AGENTS.md"
        },
        "harness-builder": {
          config: ".codex/agents/harness-builder.toml",
          role_doc: ".codex/agents/harness-builder.md",
          sop_doc: ".codex/agents/harness-builder-AGENTS.md"
        },
        "harness-qa": {
          config: ".codex/agents/harness-qa.toml",
          role_doc: ".codex/agents/harness-qa.md",
          sop_doc: ".codex/agents/harness-qa-AGENTS.md"
        },
        "harness-code-review": {
          config: ".codex/agents/harness-code-review.toml",
          role_doc: ".codex/agents/harness-code-review.md",
          sop_doc: ".codex/agents/harness-code-review-AGENTS.md"
        },
        "harness-call-chain": {
          config: ".codex/agents/harness-call-chain.toml",
          role_doc: ".codex/agents/harness-call-chain.md",
          sop_doc: ".codex/agents/harness-call-chain-AGENTS.md"
        }
      },
      thresholds: {
        short_stage_no_progress_seconds: 300,
        long_stage_no_progress_seconds: 900
      },
      lifecycle: {
        reuse_subagents_across_stages: false,
        close_agent_after_stage: true,
        close_parallel_agent_when_done: true,
        close_stalled_agent_before_replacement: true
      },
      limits: {
        feedback_clarifications: null,
        fix_rounds: 3,
        stage_recoveries: 2
      }
    }' > "$profile_file"

  jq -n \
    --arg profile_path "$profile_file" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    --arg source_run "$source_run" \
    --argjson source_build_commits "$source_build_commits" \
    '{
      phase: "INIT",
      mode: "post-review-fix",
      profile_path: $profile_path,
      output_dir: $output_dir,
      plan_path: $plan_path,
      source_run: $source_run,
      source: {
        run: $source_run,
        build_commits: $source_build_commits
      },
      feedback: {
        status: "pending",
        decision: null,
        artifact: null,
        clarification_count: 0
      },
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
        commit: null
      },
      fix_round: 0,
      retries: {},
      events: [],
      next_action: "USER_FEEDBACK_TRIAGE"
    }' > "$state_file"

  : > "$output_dir/progress/events.tsv"
  export HARNESS_PROFILE="$profile_file"
  printf '%s\n' "$profile_file"
}

source "$SCRIPT_DIR/harness-common.sh"
