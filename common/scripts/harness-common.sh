#!/usr/bin/env bash
# harness-common.sh — Agent 间通信工具函数
# 无副作用的纯函数库，供任何 Agent 在 Bash 工具中 source 后使用
# 用法：source .claude/common/scripts/harness-common.sh

# 通过脚本自身路径推导项目根目录，避免 Agent cd 子目录后 $(pwd) 漂移
if [ -n "${BASH_SOURCE[0]:-}" ]; then
  PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
else
  PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
fi
# Agent 注册表路径：env 优先（由 launch_agent_pane 注入到 Agent 进程），
# 未注入时回退到旧的固定路径 .harness/config.json（向后兼容裸跑场景）
HARNESS_CONFIG="${HARNESS_CONFIG:-$PROJECT_DIR/.harness/config.json}"

# 查询 Agent 的 tmux pane ID（从 config.json 读）
get_agent_pane() {
  local agent="$1"
  [ -f "$HARNESS_CONFIG" ] && jq -r ".agents[\"$agent\"].pane // empty" "$HARNESS_CONFIG"
}

# 检查 Agent 的 pane 是否仍然存活
is_agent_alive() {
  local pane
  pane=$(get_agent_pane "$1")
  [ -n "$pane" ] && tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${pane}$"
}

# 内部函数：把消息落盘到 ${output_dir}/conversation/{timestamp}-{from}-to-{to}.md
# 用 frontmatter (YAML) 承载 from/to/timestamp/artifact,正文是消息原文
# 失败不阻塞主流程(发消息比存档更重要)——任何落盘异常静默吞掉
_persist_conversation() {
  local to="$1" message="$2" artifact="${3:-}"
  local from="${HARNESS_AGENT_NAME:-unknown}"
  local output_dir
  output_dir=$(jq -r '.output_dir // empty' "$HARNESS_CONFIG" 2>/dev/null) || return 0
  [ -z "$output_dir" ] && return 0

  # output_dir 可能是相对路径(.harness/iterations/...),拼到 PROJECT_DIR 之下
  local conv_dir
  if [[ "$output_dir" = /* ]]; then
    conv_dir="$output_dir/conversation"
  else
    conv_dir="$PROJECT_DIR/$output_dir/conversation"
  fi
  mkdir -p "$conv_dir" 2>/dev/null || return 0

  local ts_compact ts_iso
  ts_compact=$(date +%Y%m%dT%H%M%S)
  ts_iso=$(date +%FT%T%z)
  local file="$conv_dir/${ts_compact}-${from}-to-${to}.md"

  {
    printf -- "---\n"
    printf "from: %s\n" "$from"
    printf "to: %s\n" "$to"
    printf "timestamp: %s\n" "$ts_iso"
    [ -n "$artifact" ] && printf "artifact: %s\n" "$artifact"
    printf -- "---\n\n"
    printf "%s\n" "$message"
  } > "$file" 2>/dev/null || return 0
}

# 向已注册的 Agent 发送消息（通过 tmux send-keys）
# 用法：send_to_agent "Builder" "消息内容" [artifact]
# 副作用：落盘消息存档到 ${output_dir}/conversation/,然后发 send-keys
send_to_agent() {
  local agent="$1" message="$2" artifact="${3:-}"
  local pane
  pane=$(get_agent_pane "$agent")

  if [ -z "$pane" ]; then
    echo "错误：Agent '${agent}' 未注册" >&2
    return 1
  fi

  if ! tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${pane}$"; then
    echo "错误：Agent '${agent}' 的 pane ${pane} 已不存在" >&2
    return 1
  fi

  # 先落盘存档(失败不阻塞),再 send-keys
  _persist_conversation "$agent" "$message" "$artifact"

  tmux send-keys -t "$pane" -l "$message"
  # 等待对方 TUI 把字符消化进输入框,再回车提交;不 sleep 时 Enter 常被吃掉
  sleep 0.3
  tmux send-keys -t "$pane" Enter
}

# 阶段完成通知：验证产出文件存在后通知对方
# 用法：complete_and_notify "harness-qa" "消息内容" [产出文件路径]
complete_and_notify() {
  local target="$1" message="$2" artifact="${3:-}"
  if [ -n "$artifact" ] && [ ! -f "$artifact" ]; then
    echo "错误：产出文件 ${artifact} 不存在，请先完成产出再通知" >&2
    return 1
  fi
  send_to_agent "$target" "$message" "$artifact"
}
