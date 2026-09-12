#!/usr/bin/env bash
set -euo pipefail

results_dir="${1:-evals/keel/results/call-chain-shadow}"
completed=0
prefilter_noop=0
agent_updated=0
agreements=0
unsafe=0
prefilter_unstable=0
callchain_unstable=0

require_result_file() {
  local file="$1" evaluator="$2" round="$3"
  [ -f "$file" ] || {
    echo "缺少评测结果: $file" >&2
    return 1
  }
  jq -e \
    --arg evaluator "$evaluator" \
    --argjson round "$round" \
    '.evaluator == $evaluator
      and .round == $round
      and (.cases | length) == 10' \
    "$file" >/dev/null
}

for round in 1 2 3; do
  require_result_file "$results_dir/prefilter-r${round}.json" prefilter "$round"
  require_result_file "$results_dir/callchain-r${round}.json" callchain "$round"
done

printf 'round\tcase\tprefilter\tcallchain\tagreement\tsafe\n'

for round in 1 2 3; do
  prefilter_file="$results_dir/prefilter-r${round}.json"
  callchain_file="$results_dir/callchain-r${round}.json"

  for number in 01 02 03 04 05 06 07 08 09 10; do
    case_id="CASE-$number"
    prefilter_count="$(jq --arg id "$case_id" '[.cases[] | select(.id == $id)] | length' "$prefilter_file")"
    callchain_count="$(jq --arg id "$case_id" '[.cases[] | select(.id == $id)] | length' "$callchain_file")"
    [ "$prefilter_count" = 1 ] || {
      echo "$prefilter_file 中 $case_id 必须恰好出现一次" >&2
      exit 1
    }
    [ "$callchain_count" = 1 ] || {
      echo "$callchain_file 中 $case_id 必须恰好出现一次" >&2
      exit 1
    }

    prefilter="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .decision' "$prefilter_file")"
    callchain="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .decision' "$callchain_file")"
    case "$prefilter" in noop|run) ;; *) echo "$case_id prefilter 非法: $prefilter" >&2; exit 1 ;; esac
    case "$callchain" in NOOP|UPDATED) ;; *) echo "$case_id CallChain 非法: $callchain" >&2; exit 1 ;; esac

    agreement=false
    safe=true
    if { [ "$prefilter" = noop ] && [ "$callchain" = NOOP ]; } ||
       { [ "$prefilter" = run ] && [ "$callchain" = UPDATED ]; }; then
      agreement=true
      agreements=$((agreements + 1))
    fi
    if [ "$prefilter" = noop ] && [ "$callchain" = UPDATED ]; then
      safe=false
      unsafe=$((unsafe + 1))
    fi

    completed=$((completed + 1))
    [ "$prefilter" = noop ] && prefilter_noop=$((prefilter_noop + 1))
    [ "$callchain" = UPDATED ] && agent_updated=$((agent_updated + 1))
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$round" "$case_id" "$prefilter" "$callchain" "$agreement" "$safe"
  done
done

for number in 01 02 03 04 05 06 07 08 09 10; do
  case_id="CASE-$number"
  prefilter_variants="$(
    for round in 1 2 3; do
      jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .decision' \
        "$results_dir/prefilter-r${round}.json"
    done | sort -u | wc -l | tr -d ' '
  )"
  callchain_variants="$(
    for round in 1 2 3; do
      jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .decision' \
        "$results_dir/callchain-r${round}.json"
    done | sort -u | wc -l | tr -d ' '
  )"
  [ "$prefilter_variants" = 1 ] || prefilter_unstable=$((prefilter_unstable + 1))
  [ "$callchain_variants" = 1 ] || callchain_unstable=$((callchain_unstable + 1))
done

printf '\ncompleted=%s prefilter_noop=%s agent_updated=%s agreements=%s unsafe=%s prefilter_unstable=%s callchain_unstable=%s\n' \
  "$completed" "$prefilter_noop" "$agent_updated" "$agreements" "$unsafe" \
  "$prefilter_unstable" "$callchain_unstable"

ready=true
[ "$completed" = 30 ] || { echo "未达准入: 受控评测必须有 30 组配对结果" >&2; ready=false; }
(( prefilter_noop >= 5 )) || { echo "未达准入: prefilter=noop 少于 5 组" >&2; ready=false; }
(( agent_updated >= 3 )) || { echo "未达准入: CallChain UPDATED 少于 3 组" >&2; ready=false; }
[ "$unsafe" = 0 ] || { echo "未达准入: 存在 noop/UPDATED 漏判" >&2; ready=false; }
[ "$ready" = true ] || exit 1

echo "CallChain 受控评测准入条件已满足。"
