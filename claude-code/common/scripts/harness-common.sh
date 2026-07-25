#!/usr/bin/env bash
# Harness Claude Code common helpers.
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

_harness_state_jq() {
  local state_file tmp
  state_file="$(harness_state_file)" || return 1
  [ -f "$state_file" ] || {
    echo "错误: state.json 不存在: $state_file" >&2
    return 1
  }
  tmp="$(mktemp)"
  if ! jq "$@" "$state_file" > "$tmp"; then
    rm -f -- "$tmp"
    return 1
  fi
  if ! mv "$tmp" "$state_file"; then
    rm -f -- "$tmp"
    return 1
  fi
}

harness_progress_dir() {
  local output_dir
  output_dir="$(harness_output_dir)" || return 1
  [ -n "$output_dir" ] || return 1
  printf '%s/progress\n' "$output_dir"
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

record_call_chain_prefilter() {
  local decision="$1" reason="$2" ts
  case "$decision" in
    noop|run) ;;
    *)
      echo "错误: CallChain prefilter decision 必须是 noop 或 run" >&2
      return 2
      ;;
  esac
  [ -n "$reason" ] || {
    echo "错误: CallChain prefilter reason 不能为空" >&2
    return 2
  }
  ts="$(date +%FT%T%z)"
  _harness_state_jq \
    --arg decision "$decision" \
    --arg reason "$reason" \
    --arg ts "$ts" \
    '.call_chain.prefilter = {
      mode: "shadow",
      decision: $decision,
      reason: $reason,
      agent_decision: null,
      agreement: null,
      safe: null,
      evaluated_at: $ts,
      compared_at: null
    }'
}

record_call_chain_shadow_result() {
  local agent_decision="$1" ts
  case "$agent_decision" in
    noop|updated) ;;
    *)
      echo "错误: CallChain agent decision 必须是 noop 或 updated" >&2
      return 2
      ;;
  esac
  ts="$(date +%FT%T%z)"
  _harness_state_jq \
    --arg agent_decision "$agent_decision" \
    --arg ts "$ts" \
    'if (.call_chain.prefilter.decision // "") == "" then
      error("CallChain prefilter decision 尚未记录")
    else
      .call_chain.prefilter.agent_decision = $agent_decision
      | .call_chain.prefilter.agreement = (
          (.call_chain.prefilter.decision == "noop" and $agent_decision == "noop")
          or (.call_chain.prefilter.decision == "run" and $agent_decision == "updated")
        )
      | .call_chain.prefilter.safe = (
          .call_chain.prefilter.decision != "noop" or $agent_decision == "noop"
        )
      | .call_chain.prefilter.compared_at = $ts
    end'
}
