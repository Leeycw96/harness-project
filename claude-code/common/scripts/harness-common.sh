#!/usr/bin/env bash
# Harness Claude Code common helpers.
# Disk contract: state.json + progress.tsv. HARNESS_PROFILE is the compatible state path variable.

SCRIPT_PATH="${BASH_SOURCE[0]-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

HARNESS_PROFILE="${HARNESS_PROFILE:-$PROJECT_DIR/.harness/state.json}"

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
  case "$HARNESS_PROFILE" in
    state.json|*/state.json)
      printf '%s\n' "$HARNESS_PROFILE"
      return
      ;;
  esac
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

harness_progress_file() {
  local configured output_dir
  configured="$(_harness_profile_value '.progress.events')" || return 1
  if [ -n "$configured" ]; then
    printf '%s\n' "$configured"
    return
  fi
  output_dir="$(harness_output_dir)" || return 1
  [ -n "$output_dir" ] || return 1
  printf '%s/progress.tsv\n' "$output_dir"
}

append_progress_event() {
  local kind="$1" agent="$2" stage="$3" message="$4" artifact="${5:-}"
  local events ts clean_message
  events="$(harness_progress_file)" || return 1
  mkdir -p "$(dirname "$events")"
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

  local progress_file display_agent
  progress_file="$(harness_progress_file)" || return 1

  case "$agent" in
    harness-builder|builder) display_agent="harness-builder" ;;
    harness-qa|qa) display_agent="harness-qa" ;;
    harness-code-review|code-review|code_review) display_agent="harness-code-review" ;;
    harness-call-chain|call-chain|call_chain) display_agent="harness-call-chain" ;;
    *) display_agent="$agent" ;;
  esac

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
      mode: (.call_chain.prefilter.mode // "on-demand"),
      decision: $decision,
      reason: $reason,
      agent_decision: null,
      agreement: null,
      safe: null,
      evaluated_at: $ts,
      compared_at: null
    }'
}

record_call_chain_skip() {
  local ts
  ts="$(date +%FT%T%z)"
  _harness_state_jq \
    --arg ts "$ts" \
    'if (.call_chain.prefilter.mode // "") != "on-demand" then
      error("只有 on-demand 模式可以跳过 CallChain")
    elif (.call_chain.prefilter.decision // "") != "noop" then
      error("只有 prefilter=noop 才能跳过 CallChain")
    else
      .call_chain.status = "skipped"
      | .call_chain.action = "noop"
      | .call_chain.artifact = null
      | .call_chain.commit = null
      | .call_chain.prefilter.agent_decision = "skipped"
      | .call_chain.prefilter.agreement = null
      | .call_chain.prefilter.safe = null
      | .call_chain.prefilter.compared_at = $ts
      | .phase = "DONE"
      | del(.next_action)
    end'
}

record_call_chain_result() {
  local agent_decision="$1" commit="${2:-}" artifact ts
  case "$agent_decision" in
    noop|updated) ;;
    *)
      echo "错误: CallChain agent decision 必须是 noop 或 updated" >&2
      return 2
      ;;
  esac
  if [ "$agent_decision" = "updated" ] && [[ ! "$commit" =~ ^[0-9a-f]{7,64}$ ]]; then
    echo "错误: CallChain UPDATED 必须记录 commit sha" >&2
    return 2
  fi
  artifact="$(_harness_profile_value '.artifacts.call_chain_review')" || return 1
  ts="$(date +%FT%T%z)"
  _harness_state_jq \
    --arg agent_decision "$agent_decision" \
    --arg artifact "$artifact" \
    --arg commit "$commit" \
    --arg ts "$ts" \
    'if (.call_chain.prefilter.mode // "") != "on-demand" then
      error("on-demand CallChain 结果不能写入其他模式")
    elif (.call_chain.prefilter.decision // "") != "run" then
      error("只有 prefilter=run 才能记录 CallChain Agent 结果")
    else
      .call_chain.status = "completed"
      | .call_chain.action = $agent_decision
      | .call_chain.artifact = $artifact
      | .call_chain.commit = (if $commit == "" then null else $commit end)
      | .call_chain.prefilter.agent_decision = $agent_decision
      | .call_chain.prefilter.agreement = ($agent_decision == "updated")
      | .call_chain.prefilter.safe = true
      | .call_chain.prefilter.compared_at = $ts
      | .phase = "DONE"
      | del(.next_action)
    end'
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
