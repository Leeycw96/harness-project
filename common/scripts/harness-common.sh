#!/usr/bin/env bash
# Harness Codex App common helpers.
# Disk contract: profile.json + state.json + progress/. No tmux, signals, or conversation logs.

SCRIPT_PATH="${BASH_SOURCE[0]-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

HARNESS_PROFILE="${HARNESS_PROFILE:-$PROJECT_DIR/.harness/profile.json}"

_harness_require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "错误: jq 未安装" >&2
    return 1
  fi
}

_harness_profile_value() {
  local expr="$1"
  _harness_require_jq || return 1
  [ -f "$HARNESS_PROFILE" ] || {
    echo "错误: HARNESS_PROFILE 不存在: $HARNESS_PROFILE" >&2
    return 1
  }
  jq -r "$expr // empty" "$HARNESS_PROFILE"
}

harness_output_dir() {
  _harness_profile_value '.output_dir'
}

harness_state_file() {
  local output_dir
  output_dir="$(harness_output_dir)" || return 1
  [ -n "$output_dir" ] || return 1
  printf '%s/state.json\n' "$output_dir"
}

harness_progress_dir() {
  local output_dir
  output_dir="$(harness_output_dir)" || return 1
  [ -n "$output_dir" ] || return 1
  printf '%s/progress\n' "$output_dir"
}

harness_artifact_path() {
  local key="$1"
  _harness_profile_value ".artifacts.${key}"
}

harness_state_jq() {
  local state_file tmp
  state_file="$(harness_state_file)" || return 1
  [ -f "$state_file" ] || {
    echo "错误: state.json 不存在: $state_file" >&2
    return 1
  }
  tmp="$(mktemp)"
  jq "$@" "$state_file" > "$tmp"
  mv "$tmp" "$state_file"
}

harness_set_phase() {
  local phase="$1" next_action="${2:-}"
  if [ -n "$next_action" ]; then
    harness_state_jq --arg phase "$phase" --arg next "$next_action" \
      '.phase = $phase | .next_action = $next'
  else
    harness_state_jq --arg phase "$phase" '.phase = $phase'
  fi
}

append_progress_event() {
  local kind="$1" agent="$2" stage="$3" message="$4" artifact="${5:-}"
  local progress_dir events ts clean_message
  progress_dir="$(harness_progress_dir)" || return 1
  mkdir -p "$progress_dir"
  events="$progress_dir/events.tsv"
  ts="$(date +%FT%T%z)"
  clean_message="$(printf '%s' "$message" | tr '\n\t' '  ')"
  printf '%s\t%s\t%s\t%s\t%s' "$ts" "$kind" "$agent" "$stage" "$clean_message" >> "$events"
  [ -n "$artifact" ] && printf '\t%s' "$artifact" >> "$events"
  printf '\n' >> "$events"
}

update_progress() {
  local agent="$1" stage="$2" message="$3" artifact="${4:-}"
  if [ -z "$agent" ] || [ -z "$stage" ] || [ -z "$message" ]; then
    echo "用法: update_progress <agent> <stage> <message> [artifact]" >&2
    return 2
  fi

  local progress_dir progress_file ts display_agent
  progress_dir="$(harness_progress_dir)" || return 1
  mkdir -p "$progress_dir"
  ts="$(date +%FT%T%z)"

  case "$agent" in
    harness-builder|builder) progress_file="$progress_dir/builder.md"; display_agent="harness-builder" ;;
    harness-qa|qa) progress_file="$progress_dir/qa.md"; display_agent="harness-qa" ;;
    harness-code-review|code-review|code_review) progress_file="$progress_dir/code-review.md"; display_agent="harness-code-review" ;;
    harness-call-chain|call-chain|call_chain) progress_file="$progress_dir/call-chain.md"; display_agent="harness-call-chain" ;;
    harness-feedback-triage|feedback-triage|feedback_triage|triage) progress_file="$progress_dir/feedback-triage.md"; display_agent="harness-feedback-triage" ;;
    *) progress_file="$progress_dir/${agent}.md"; display_agent="$agent" ;;
  esac

  {
    printf '# %s progress\n\n' "$display_agent"
    printf 'updated_at: %s\n' "$ts"
    printf 'stage: %s\n' "$stage"
    [ -n "$artifact" ] && printf 'artifact: %s\n' "$artifact"
    printf '\n## Current\n\n'
    printf '%s\n' "$message"
  } > "$progress_file"

  append_progress_event "progress" "$display_agent" "$stage" "$message" "$artifact"
  printf '%s\n' "$progress_file"
}

complete_stage() {
  local agent="$1" tag="$2" message="$3" artifact="${4:-}"
  if [ -z "$agent" ] || [ -z "$tag" ] || [ -z "$message" ]; then
    echo "用法: complete_stage <agent> <TAG> <message> [artifact]" >&2
    return 2
  fi
  if [ -n "$artifact" ] && [ ! -f "$artifact" ]; then
    echo "错误: 产出文件不存在: $artifact" >&2
    return 1
  fi

  update_progress "$agent" "$tag" "$message" "$artifact" >/dev/null
  append_progress_event "complete" "$agent" "$tag" "$message" "$artifact"
  printf '%s | %s' "$tag" "$message"
  [ -n "$artifact" ] && printf ' | artifact: %s' "$artifact"
  printf '\n'
}

validate_artifact() {
  local artifact="$1" pattern="${2:-}"
  if [ -z "$artifact" ] || [ ! -f "$artifact" ]; then
    echo "INVALID_ARTIFACT: 文件不存在: ${artifact:-<empty>}" >&2
    return 1
  fi
  if [ -n "$pattern" ] && ! grep -Eq "$pattern" "$artifact"; then
    echo "INVALID_ARTIFACT: $artifact 未匹配期望模式: $pattern" >&2
    return 1
  fi
  printf 'VALID_ARTIFACT: %s\n' "$artifact"
}
