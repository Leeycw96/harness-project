#!/usr/bin/env bash
set -euo pipefail

# Harness 编排环境初始化脚本
# 由 SKILL.md 第零步 source 加载
# 参考 Claude Code Agent Team 的 tmux pane 管理方式

PROJECT_DIR=$(pwd)
HARNESS_SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p .harness

# 工具函数：将示例文件复制到目标项目的 .harness/examples/
# 由各模式的 SKILL.md 在初始化阶段调用，传入对应模式的 examples 目录路径
copy_examples() {
  local src_dir="$1"
  if [ -d "$src_dir" ]; then
    mkdir -p "$PROJECT_DIR/.harness/examples"
    cp -r "$src_dir"/* "$PROJECT_DIR/.harness/examples/" 2>/dev/null || true
  fi
}

# 检测 tmux
if ! command -v tmux &>/dev/null; then
  echo "错误：tmux 未安装，请先执行 brew install tmux"
  exit 1
fi

# Pane ID 持久化文件（解决跨 shell 调用状态丢失问题）
HARNESS_PANES_FILE="$PROJECT_DIR/.harness/agent-panes"

# Agent 注册表：AgentName=PaneID，供 Agent 之间通过 send-keys 直接通信
HARNESS_REGISTRY="$PROJECT_DIR/.harness/agent-registry"

# 主 pane ID 持久化文件
HARNESS_MAIN_PANE_FILE="$PROJECT_DIR/.harness/main-pane"

# 幂等初始化：只在首次运行时清理，后续 source 不再删除已有注册表
# 解决 cross-shell 问题——编排器每次 Bash 调用是新 shell，需要重新 source 本脚本
HARNESS_INIT_MARKER="$PROJECT_DIR/.harness/.initialized"
if [ ! -f "$HARNESS_INIT_MARKER" ]; then
  # 首次运行，正常初始化
  rm -f "$HARNESS_REGISTRY" "$HARNESS_PANES_FILE" "$HARNESS_MAIN_PANE_FILE"
  rm -f "$PROJECT_DIR/.harness/done"
  rm -rf "$PROJECT_DIR/.harness/signals"
  mkdir -p "$PROJECT_DIR/.harness/signals"
  echo "$TMUX_PANE" > "$HARNESS_MAIN_PANE_FILE"
  touch "$HARNESS_INIT_MARKER"
else
  # .initialized 已存在，检查上次的主 pane 是否仍然活着
  prev_main_pane=""
  if [ -f "$HARNESS_MAIN_PANE_FILE" ]; then
    prev_main_pane=$(cat "$HARNESS_MAIN_PANE_FILE")
  fi
  if [ -n "$prev_main_pane" ] && tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${prev_main_pane}$"; then
    # 主 pane 还活着 → 同一次运行的重复 source，跳过初始化
    :
  else
    # 主 pane 已死 → 上次迭代异常退出，残留了 .harness 状态
    # 输出警告信息供编排器读取，由编排器提示用户决策
    echo "HARNESS_STALE_SESSION_DETECTED"
    echo "上次迭代的 .harness 状态未正常清理（主 pane ${prev_main_pane:-未知} 已不存在）。"
    if [ -f "$HARNESS_PANES_FILE" ]; then
      echo "残留的 Agent pane："
      while IFS= read -r pane; do
        if [ -n "$pane" ] && tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -q "^${pane}$"; then
          echo "  ${pane} (仍在运行)"
        else
          echo "  ${pane} (已退出)"
        fi
      done < "$HARNESS_PANES_FILE"
    fi
    # 不自动清理，等待编排器根据用户决策调用 cleanup_stale_session
  fi
fi

# 从持久化文件读取主 pane ID，而不是每次动态获取
# 解决多 window 场景下焦点在其他 window 时 Agent 被 split 到错误 window 的问题
HARNESS_MAIN_PANE=$(cat "$HARNESS_MAIN_PANE_FILE")

# 工具函数：等待文件生成
wait_for_file() {
  local file="$1" timeout="${2:-1800}" elapsed=0
  while [ ! -f "$file" ] && [ $elapsed -lt $timeout ]; do
    sleep 5; elapsed=$((elapsed + 5))
  done
  [ -f "$file" ]
}

# 工具函数：在当前窗口中创建新 Pane 启动 Agent（交互模式）
# 关键设计：
#   -d: 不切换焦点，主 pane 保持 active
#   -t: 精确指定 split 目标 pane
#   -P -F: 捕获新 pane ID 用于后续 cleanup
#   交互模式：默认启动就是新会话（不继承对话历史），用户可直接与 Agent 对话
#   参考 Agent Teams 官方文档：队友加载项目 context 但不继承负责人的对话历史
launch_agent() {
  local name="$1" agent="$2" prompt="$3"
  local prompt_file="$PROJECT_DIR/.harness/${name}.prompt"
  printf '%s' "$prompt" > "$prompt_file"

  # 交互式启动，默认就是新会话（不继承对话历史）
  local cli_cmd="${HARNESS_CLI:-claude}"
  local new_pane
  new_pane=$(tmux split-window -d -v -l 30% -t "$HARNESS_MAIN_PANE" -P -F '#{pane_id}' \
    "export CLAUDE_CODE_NO_FLICKER=1 && cd $PROJECT_DIR && ${cli_cmd} --agent '$agent' --permission-mode bypassPermissions")

  # 写入注册表（覆盖同名 Agent 的旧条目）
  if [ -f "$HARNESS_REGISTRY" ]; then
    sed -i '' "/^${agent}=/d" "$HARNESS_REGISTRY"
  fi
  echo "${agent}=${new_pane}" >> "$HARNESS_REGISTRY"

  # 持久化 pane ID 到文件（追加模式，用于 cleanup）
  echo "$new_pane" >> "$HARNESS_PANES_FILE"
  tmux select-layout -t "$HARNESS_MAIN_PANE" main-vertical

  # 等待 Agent 启动就绪
  sleep 5

  # 通过 send-keys 发送初始 prompt（-l 逐字符发送，Enter 单独发送，与 send_to_agent 一致）
  tmux send-keys -t "$new_pane" -l "$(cat "$prompt_file")"
  tmux send-keys -t "$new_pane" Enter
}

# 工具函数：只关闭主 pane 所在 window 内的 Agent pane，不影响其他 window
cleanup_panes() {
  local main_window=""
  if [ -f "$HARNESS_MAIN_PANE_FILE" ]; then
    local main_pane
    main_pane=$(cat "$HARNESS_MAIN_PANE_FILE")
    main_window=$(tmux display-message -t "$main_pane" -p '#{window_id}' 2>/dev/null || echo "")
  fi
  if [ -f "$HARNESS_PANES_FILE" ]; then
    while IFS= read -r pane; do
      if [ -n "$pane" ] && [ -n "$main_window" ]; then
        local pane_window
        pane_window=$(tmux display-message -t "$pane" -p '#{window_id}' 2>/dev/null || echo "")
        [ "$pane_window" = "$main_window" ] && tmux kill-pane -t "$pane" 2>/dev/null || true
      fi
    done < "$HARNESS_PANES_FILE"
    rm -f "$HARNESS_PANES_FILE"
  fi
  rm -f "$HARNESS_REGISTRY"
  rm -f "$PROJECT_DIR/.harness/main-pane"
  rm -f "$PROJECT_DIR/.harness/.initialized"
  rm -f "$PROJECT_DIR/.harness/done"
}

# 工具函数：清理上次异常退出残留的 .harness 状态，然后重新初始化
# 由编排器在用户确认清理后调用
cleanup_stale_session() {
  # 尝试关闭残留 pane（仅限主 pane 所在 window 内，防止误杀其他 window）
  if [ -f "$HARNESS_PANES_FILE" ] && [ -f "$HARNESS_MAIN_PANE_FILE" ]; then
    local main_pane main_window
    main_pane=$(cat "$HARNESS_MAIN_PANE_FILE")
    main_window=$(tmux display-message -t "$main_pane" -p '#{window_id}' 2>/dev/null || echo "")
    if [ -n "$main_window" ]; then
      while IFS= read -r pane; do
        if [ -n "$pane" ]; then
          local pane_window
          pane_window=$(tmux display-message -t "$pane" -p '#{window_id}' 2>/dev/null || echo "")
          [ "$pane_window" = "$main_window" ] && tmux kill-pane -t "$pane" 2>/dev/null || true
        fi
      done < "$HARNESS_PANES_FILE"
    fi
  fi
  # 清理所有运行时文件
  rm -f "$HARNESS_REGISTRY" "$HARNESS_PANES_FILE" "$HARNESS_MAIN_PANE_FILE" "$HARNESS_INIT_MARKER"
  rm -rf "$PROJECT_DIR/.harness/signals"
  rm -f "$PROJECT_DIR/.harness/done"
  # 重新初始化
  mkdir -p "$PROJECT_DIR/.harness/signals"
  echo "$TMUX_PANE" > "$HARNESS_MAIN_PANE_FILE"
  touch "$HARNESS_INIT_MARKER"
}

# 工具函数：获取最新的 run 编号（不递增），无计数器文件时返回 0
get_latest_run_number() {
  local branch_dir="$1"
  local counter_file="${branch_dir}/.run-counter"
  if [ -f "$counter_file" ]; then
    cat "$counter_file"
  else
    echo "0"
  fi
}

# 工具函数：获取下一个 run 编号（递增并写回）
get_next_run_number() {
  local branch_dir="$1"
  local counter_file="${branch_dir}/.run-counter"
  local current=0
  if [ -f "$counter_file" ]; then
    current=$(cat "$counter_file")
  fi
  local next=$((current + 1))
  echo "$next" > "$counter_file"
  echo "$next"
}
