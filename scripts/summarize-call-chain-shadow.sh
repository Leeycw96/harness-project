#!/usr/bin/env bash
set -euo pipefail

check_ready=false
root=".keel/iterations"

while [ $# -gt 0 ]; do
  case "$1" in
    --check-ready)
      check_ready=true
      ;;
    -h|--help)
      echo "用法: scripts/summarize-call-chain-shadow.sh [--check-ready] [iterations-dir]"
      exit 0
      ;;
    -*)
      echo "未知参数: $1" >&2
      exit 2
      ;;
    *)
      root="$1"
      ;;
  esac
  shift
done

completed=0
incomplete=0
noop_samples=0
run_samples=0
updated_samples=0
agreements=0
unsafe=0

printf 'state\tprefilter\tagent\tagreement\tsafe\treason\n'

if [ -d "$root" ]; then
  while IFS= read -r state_file; do
    mode="$(jq -r '.call_chain.prefilter.mode // empty' "$state_file")"
    [ "$mode" = "shadow" ] || continue

    decision="$(jq -r '.call_chain.prefilter.decision // empty' "$state_file")"
    agent_decision="$(jq -r '.call_chain.prefilter.agent_decision // empty' "$state_file")"
    agreement="$(jq -r 'if .call_chain.prefilter.agreement == null then "" else (.call_chain.prefilter.agreement | tostring) end' "$state_file")"
    safe="$(jq -r 'if .call_chain.prefilter.safe == null then "" else (.call_chain.prefilter.safe | tostring) end' "$state_file")"
    reason="$(jq -r '.call_chain.prefilter.reason // empty' "$state_file" | tr '\n\t' '  ')"

    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${state_file#$root/}" "$decision" "$agent_decision" "$agreement" "$safe" "$reason"

    case "$decision:$agent_decision" in
      noop:noop|noop:updated|run:noop|run:updated) ;;
      *)
        incomplete=$((incomplete + 1))
        continue
        ;;
    esac

    completed=$((completed + 1))
    [ "$decision" = "noop" ] && noop_samples=$((noop_samples + 1))
    [ "$decision" = "run" ] && run_samples=$((run_samples + 1))
    [ "$agent_decision" = "updated" ] && updated_samples=$((updated_samples + 1))
    [ "$agreement" = "true" ] && agreements=$((agreements + 1))
    [ "$decision:$agent_decision" = "noop:updated" ] && unsafe=$((unsafe + 1))
  done < <(find "$root" -type f -name state.json | sort)
fi

printf '\ncompleted=%s incomplete=%s noop=%s run=%s updated=%s agreements=%s unsafe=%s\n' \
  "$completed" "$incomplete" "$noop_samples" "$run_samples" "$updated_samples" "$agreements" "$unsafe"

if [ "$check_ready" = "true" ]; then
  ready=true
  if (( completed < 10 )); then
    echo "未达准入: completed 样本少于 10" >&2
    ready=false
  fi
  if (( noop_samples < 5 )); then
    echo "未达准入: prefilter=noop 样本少于 5" >&2
    ready=false
  fi
  if (( updated_samples < 3 )); then
    echo "未达准入: Agent UPDATED 正样本少于 3" >&2
    ready=false
  fi
  if (( unsafe > 0 )); then
    echo "未达准入: 存在 prefilter=noop 但 Agent=updated 的漏判" >&2
    ready=false
  fi
  [ "$ready" = "true" ] || exit 1
  echo "CallChain 按需调度准入条件已满足。"
fi
