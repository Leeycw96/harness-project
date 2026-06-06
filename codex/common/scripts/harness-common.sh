#!/usr/bin/env bash
# Harness Codex App 公共函数。
# 只做磁盘通信：conversation/ 记录消息，signals/ 记录阶段完成信号。

SCRIPT_PATH="${BASH_SOURCE[0]-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

HARNESS_CONFIG="${HARNESS_CONFIG:-$PROJECT_DIR/.harness/config.json}"

_harness_output_dir() {
  [ -f "$HARNESS_CONFIG" ] && jq -r '.output_dir // empty' "$HARNESS_CONFIG"
}

_harness_dir() {
  local rel="$1"
  local output_dir
  output_dir=$(_harness_output_dir)
  [ -n "$output_dir" ] || return 1
  case "$output_dir" in
    /*) printf '%s/%s\n' "$output_dir" "$rel" ;;
    *)  printf '%s/%s/%s\n' "$PROJECT_DIR" "$output_dir" "$rel" ;;
  esac
}

persist_conversation() {
  local from="$1" to="$2" message="$3" artifact="${4:-}"
  local conv_dir
  conv_dir=$(_harness_dir "conversation") || return 1
  mkdir -p "$conv_dir"

  local ts_compact ts_iso file
  ts_compact=$(date +%Y%m%dT%H%M%S)
  ts_iso=$(date +%FT%T%z)
  file="$conv_dir/${ts_compact}-${from}-to-${to}.md"

  {
    printf -- "---\n"
    printf "from: %s\n" "$from"
    printf "to: %s\n" "$to"
    printf "timestamp: %s\n" "$ts_iso"
    [ -n "$artifact" ] && printf "artifact: %s\n" "$artifact"
    printf -- "---\n\n"
    printf "%s\n" "$message"
  } > "$file"
  printf '%s\n' "$file"
}

complete_stage() {
  local agent="$1" tag="$2" message="$3" artifact="${4:-}"
  if [ -z "$agent" ] || [ -z "$tag" ] || [ -z "$message" ]; then
    echo "用法：complete_stage <agent> <TAG> <message> [artifact]" >&2
    return 2
  fi
  if [ -n "$artifact" ] && [ ! -f "$artifact" ]; then
    echo "错误：产出文件不存在: $artifact" >&2
    return 1
  fi

  local signals_dir ts_compact ts_iso signal_file conv_file
  signals_dir=$(_harness_dir "signals") || return 1
  mkdir -p "$signals_dir"
  ts_compact=$(date +%Y%m%dT%H%M%S)
  ts_iso=$(date +%FT%T%z)
  signal_file="$signals_dir/${ts_compact}-${agent}-${tag}.md"

  conv_file=$(persist_conversation "$agent" "orchestrator" "${tag} | ${message}" "$artifact")
  {
    printf -- "---\n"
    printf "agent: %s\n" "$agent"
    printf "tag: %s\n" "$tag"
    printf "timestamp: %s\n" "$ts_iso"
    [ -n "$artifact" ] && printf "artifact: %s\n" "$artifact"
    printf "conversation: %s\n" "$conv_file"
    printf -- "---\n\n"
    printf "%s\n" "$message"
  } > "$signal_file"

  printf '%s\n' "$signal_file"
}

verify_stage_signal() {
  local agent="$1" tag="$2"
  local signals_dir
  signals_dir=$(_harness_dir "signals") || return 1
  local file
  file=$(ls -1 "$signals_dir" 2>/dev/null | grep -E "^[0-9T]+-${agent}-${tag}\.md$" | sort | tail -n 1)
  if [ -z "$file" ]; then
    echo "NO_VALID_SIGNAL: 未找到 ${agent} ${tag}" >&2
    return 1
  fi
  printf '%s/%s\n' "$signals_dir" "$file"
}
