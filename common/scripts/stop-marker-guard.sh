#!/usr/bin/env bash
# stop-marker-guard.sh — Claude Code Stop hook 兜底脚本
#
# 检查本轮 LLM 输出末尾是否打了 <round-end status="..."/> 标记,按三态决定动作:
#   completed   → 若 LLM 未自行调 complete_and_notify,hook 替它向 partner 发通知
#   waiting-user→ 合法暂停,不动
#   continue    → 不动(一轮内自循环,正常该自动接续)
#   无标记      → stall 计数 +1;<3 时 send-keys 续命提示;≥3 时升级用户告警
#
# 输入(stdin):Claude Code 注入的 hook JSON,含 transcript_path
# 输出(stdout):可选 hookSpecificOutput JSON,把本次 hook 动作回写到当前会话上下文
# 退出码:始终 0(本脚本是兜底,任何异常都不应阻塞 LLM)

set -uo pipefail

# 自身身份从 env 读,launch_agent_pane 启动时已注入
AGENT_NAME="${HARNESS_AGENT_NAME:-}"
PROJECT_DIR="${HARNESS_PROJECT_DIR:-$(pwd)}"

# 不是 harness 编排出的 pane(用户裸跑 claude)→ hook 不做事
if [ -z "$AGENT_NAME" ]; then
  exit 0
fi

CONFIG="$PROJECT_DIR/.harness/config.json"
STATE_DIR="$PROJECT_DIR/.harness/.hook-state"
STALL_FILE="$STATE_DIR/${AGENT_NAME}-stall-count"
mkdir -p "$STATE_DIR"

# 读 hook 输入
HOOK_INPUT="$(cat)"
TRANSCRIPT_PATH=$(echo "$HOOK_INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || echo "")

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo "stop-marker-guard: 缺 transcript_path 或文件不存在,跳过" >&2
  exit 0
fi

# 加载通信函数(send_to_agent / get_agent_pane)
COMMON_SH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/harness-common.sh"
if [ ! -f "$COMMON_SH" ]; then
  echo "stop-marker-guard: 找不到 harness-common.sh: $COMMON_SH" >&2
  exit 0
fi
# shellcheck disable=SC1090
source "$COMMON_SH"

# 取末尾一段 transcript,先拿到最后一条 assistant 消息的文本
TAIL_RAW=$(tail -c 8000 "$TRANSCRIPT_PATH" 2>/dev/null || echo "")
LAST_TEXT=$(echo "$TAIL_RAW" \
  | grep -a '"type":"assistant"' \
  | tail -1 \
  | jq -r '.message.content // [] | map(select(.type=="text") | .text) | join("\n")' 2>/dev/null \
  || echo "")
# fallback:transcript 格式异变时直接用原始 tail 文本扫
[ -z "$LAST_TEXT" ] && LAST_TEXT="$TAIL_RAW"

# 匹配末尾出现的最后一个 round-end 标记(避免误中文内引用)
MARKER=$(echo "$LAST_TEXT" | grep -oE '<round-end[^/]*/>' | tail -1 || echo "")
STATUS=""
if [ -n "$MARKER" ]; then
  STATUS=$(echo "$MARKER" | grep -oE 'status="[^"]+"' | sed -E 's/status="(.+)"/\1/')
fi

emit_context() {
  # 把本次 hook 动作回写到当前会话上下文,LLM 下轮能看到
  local msg="$1"
  jq -n --arg m "$msg" '{hookSpecificOutput: {additionalContext: $m}}'
}

partner_of() {
  jq -r ".agents[\"$AGENT_NAME\"].partner // empty" "$CONFIG" 2>/dev/null
}

case "$STATUS" in
  completed)
    # 已自行通知 → 仅审计,重置 stall
    if echo "$TAIL_RAW" | grep -qE 'complete_and_notify|send_to_agent'; then
      rm -f "$STALL_FILE"
      emit_context "stop-marker-guard: 检测到 <round-end status=\"completed\"/> 且通知已发出,流程正常。"
      exit 0
    fi

    # 未通知 → 替它发
    SUMMARY=$(echo "$MARKER" | grep -oE 'summary="[^"]*"' | sed -E 's/summary="(.*)"/\1/' || echo "")
    PARTNER=$(partner_of)
    if [ -z "$PARTNER" ]; then
      echo "stop-marker-guard: 未找到 $AGENT_NAME 的 partner,无法兜底通知" >&2
      exit 0
    fi

    MESSAGE="[hook 兜底] ${AGENT_NAME} 本轮已完成: ${SUMMARY:-(无 summary)}。请按 SOP 接力。"
    if send_to_agent "$PARTNER" "$MESSAGE" 2>/dev/null; then
      rm -f "$STALL_FILE"
      emit_context "stop-marker-guard: 你打了 <round-end status=\"completed\"/> 但未调用 complete_and_notify,hook 已替你向 ${PARTNER} 发送通知: '${MESSAGE}'。下轮请记得自行调用 complete_and_notify,这次是兜底。"
    else
      echo "stop-marker-guard: 兜底通知 ${PARTNER} 失败" >&2
    fi
    exit 0
    ;;

  waiting-user)
    rm -f "$STALL_FILE"
    exit 0
    ;;

  continue)
    rm -f "$STALL_FILE"
    exit 0
    ;;

  "")
    # 无标记:可能卡住,可能忘了打
    COUNT=0
    [ -f "$STALL_FILE" ] && COUNT=$(cat "$STALL_FILE" 2>/dev/null || echo "0")
    [[ "$COUNT" =~ ^[0-9]+$ ]] || COUNT=0
    COUNT=$((COUNT + 1))
    echo "$COUNT" > "$STALL_FILE"

    if [ "$COUNT" -ge 3 ]; then
      touch "$PROJECT_DIR/.harness/stalled-${AGENT_NAME}"
      echo "stop-marker-guard: ${AGENT_NAME} 连续 ${COUNT} 次无 round-end 标记,已写 .harness/stalled-${AGENT_NAME},请用户介入" >&2
      emit_context "stop-marker-guard: 你已连续 ${COUNT} 轮没打 <round-end/> 标记,hook 升级到用户告警(已写 .harness/stalled-${AGENT_NAME})。立刻检查当前进度按 SOP 收尾,务必用 <round-end status=\"completed|waiting-user|continue\" ... /> 标记声明状态。"
      exit 0
    fi

    # 续命:发给自己的 pane,提醒按 SOP 收尾 + 打标记
    NUDGE="请按当前 phase SOP 继续未完成步骤,本轮收尾时务必用 <round-end status=\"completed|waiting-user|continue\" ... /> 标记声明状态。当前 stall 计数 ${COUNT}/3。"
    send_to_agent "$AGENT_NAME" "$NUDGE" 2>/dev/null || true
    exit 0
    ;;

  *)
    echo "stop-marker-guard: 未知 status=$STATUS,跳过" >&2
    exit 0
    ;;
esac
