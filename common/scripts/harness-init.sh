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

# 工具函数：把相对路径转为绝对路径（基准 PROJECT_DIR）；已绝对则原样返回
# 目的：launch_agent_pane / write_config 内部统一把传入路径转绝对，
# 这样 config.json 里的 output_dir / plan_path、注入到子进程的 HARNESS_CONFIG
# 都是无歧义的绝对路径——Agent 切 cwd 也能正确解析，不会错读旧 run 的 plan.md
_abs_path() {
  local p="$1"
  case "$p" in
    /*) printf '%s\n' "$p" ;;
    *)  printf '%s/%s\n' "$PROJECT_DIR" "$p" ;;
  esac
}

# 检测 tmux
if ! command -v tmux &>/dev/null; then
  echo "错误：tmux 未安装，请先执行 brew install tmux"
  exit 1
fi

# 检测 jq（用于解析 config.json）
if ! command -v jq &>/dev/null; then
  echo "错误：jq 未安装，请先执行 brew install jq"
  exit 1
fi

# Pane ID 持久化文件（解决跨 shell 调用状态丢失问题）
HARNESS_PANES_FILE="$PROJECT_DIR/.harness/agent-panes"

# Agent 注册表路径：env 优先（由 launch_agent_pane 注入到 Agent 进程），
# 未注入时回退到旧的固定路径 .harness/config.json（向后兼容裸跑场景）
# 新方案下 write_config 会把真实 config.json 写到 ${output_dir}/config.json，
# Agent 通过继承的 HARNESS_CONFIG env 找到自己那次 run 的 config
HARNESS_CONFIG="${HARNESS_CONFIG:-$PROJECT_DIR/.harness/config.json}"

# 主 pane ID 持久化文件
HARNESS_MAIN_PANE_FILE="$PROJECT_DIR/.harness/main-pane"

# 幂等初始化：只在首次运行时清理，后续 source 不再删除已有注册表
# 解决 cross-shell 问题——编排器每次 Bash 调用是新 shell，需要重新 source 本脚本
HARNESS_INIT_MARKER="$PROJECT_DIR/.harness/.initialized"
if [ ! -f "$HARNESS_INIT_MARKER" ]; then
  # 首次运行，正常初始化
  rm -f "$HARNESS_PANES_FILE" "$HARNESS_MAIN_PANE_FILE"
  rm -f "$PROJECT_DIR/.harness/.pending-agents"
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
          echo "  ${pane} (仍在运行)"
        else
          echo "  ${pane} (已退出)"
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

# 工具函数：在当前窗口创建新 Pane 启动 Agent（交互模式），不发送初始 prompt
# 关键设计：
#   -d: 不切换焦点，主 pane 保持 active
#   -P -F: 捕获新 pane ID 用于后续 cleanup
# 布局策略：
#   - 第一个 agent: 在主会话 pane 右侧水平分割（占主会话区域 30% 宽度）
#   - 后续 agent: 在前一个 agent pane 内垂直分割（各占 50% 高度）
#   - 不调用 select-layout，避免动用户已有的其他 pane 布局
# 启动后将 (agent, pane) 追加到 .pending-agents，供 write_config 拼装 config.json
# 用法：launch_agent_pane <name> <agent> <config_path>
#   config_path：本次 run 的 config.json 绝对路径（如 .harness/iterations/{branch}/run-{N}/config.json）
#   通过 env 注入到 Agent 进程
launch_agent_pane() {
  local name="$1" agent="$2" config_path="${3:-}"
  if [ -z "$config_path" ]; then
    echo "错误：launch_agent_pane 缺少第 3 个参数 config_path" >&2
    return 1
  fi
  # 注入到子进程 env 的 HARNESS_CONFIG 必须是绝对路径
  # Agent 在自己的会话里随时可能切 cwd,相对路径会失效
  config_path=$(_abs_path "$config_path")
  local pending="$PROJECT_DIR/.harness/.pending-agents"
  local existing=0
  [ -f "$pending" ] && existing=$(wc -l < "$pending" | tr -d ' ')

  local target_pane split_args
  if [ "$existing" -eq 0 ]; then
    target_pane="$HARNESS_MAIN_PANE"
    split_args="-h -l 30%"
  else
    target_pane=$(sed -n "${existing}p" "$pending" | cut -f2)
    split_args="-v -l 50%"
  fi

  local cli_cmd="${HARNESS_CLI:-claude}"
  local new_pane
  # HARNESS_CONFIG: 本次 run 的 config.json 绝对路径，Agent 进程通过该 env 找到 config
  # HARNESS_AGENT_NAME: 当前 Agent 自己的名字,send_to_agent 落盘消息时用作 frontmatter.from
  new_pane=$(tmux split-window -d $split_args -t "$target_pane" -P -F '#{pane_id}' \
    "export CLAUDE_CODE_NO_FLICKER=1 HARNESS_CONFIG='$config_path' HARNESS_AGENT_NAME='$agent' && cd $PROJECT_DIR && ${cli_cmd} --agent '$agent' --permission-mode bypassPermissions")

  # 记录待写入 config 的 (agent, pane) 映射
  printf '%s\t%s\n' "$agent" "$new_pane" >> "$pending"

  # 持久化 pane ID 用于 cleanup
  echo "$new_pane" >> "$HARNESS_PANES_FILE"

  # 等待 Agent 启动就绪
  sleep 5
}

# 工具函数：基于 .pending-agents 生成 config.json
# 当前假设恰好 2 个 agent，互为搭档；以后扩展再改
# 用法：write_config <output_dir> <plan_path>
#   output_dir：本次 run 的产出目录，config.json 会写到 ${output_dir}/config.json
#   plan_path：plan.md 的完整路径，可传空字符串（如 smoke 模式无 plan）
write_config() {
  local output_dir="$1"
  local plan_path="${2:-}"
  if [ -z "$output_dir" ]; then
    echo "错误：write_config 需要非空 output_dir（新方案下 config.json 写在该目录下）" >&2
    return 1
  fi
  # 写到 config.json 的 output_dir / plan_path 必须是绝对路径,
  # Agent Read 它们时不依赖 cwd——避免读到错的 plan.md
  output_dir=$(_abs_path "$output_dir")
  [ -n "$plan_path" ] && plan_path=$(_abs_path "$plan_path")
  local pending="$PROJECT_DIR/.harness/.pending-agents"
  if [ ! -f "$pending" ]; then
    echo "错误：没有待写入 config 的 agent，请先调用 launch_agent_pane" >&2
    return 1
  fi

  local count
  count=$(wc -l < "$pending" | tr -d ' ')
  if [ "$count" -ne 2 ]; then
    echo "错误：write_config 当前只支持 2 个 agent，实际 $count" >&2
    return 1
  fi

  local agent_a pane_a agent_b pane_b
  agent_a=$(sed -n '1p' "$pending" | cut -f1)
  pane_a=$(sed -n '1p' "$pending" | cut -f2)
  agent_b=$(sed -n '2p' "$pending" | cut -f1)
  pane_b=$(sed -n '2p' "$pending" | cut -f2)

  mkdir -p "$output_dir"
  # 预建 conversation 目录:send_to_agent 落盘消息时写在这里
  mkdir -p "$output_dir/conversation"
  local config_file="$output_dir/config.json"
  cat > "$config_file" <<EOF
{
  "project_dir": "$PROJECT_DIR",
  "output_dir": "$output_dir",
  "plan_path": "$plan_path",
  "agents": {
    "$agent_a": { "pane": "$pane_a", "partner": "$agent_b" },
    "$agent_b": { "pane": "$pane_b", "partner": "$agent_a" }
  }
}
EOF

  # 让本 shell 后续 dispatch_initial_prompt 能找到新写的 config
  HARNESS_CONFIG="$config_file"
  export HARNESS_CONFIG

  rm -f "$pending"
}

# 工具函数：向已启动的 agent pane 发送初始 prompt
# 用法：dispatch_initial_prompt <name> <prompt>
dispatch_initial_prompt() {
  local name="$1" prompt="$2"
  local pane
  pane=$(jq -r ".agents[\"$name\"].pane // \"\"" "$HARNESS_CONFIG")
  if [ -z "$pane" ]; then
    echo "错误：agent '$name' 在 $HARNESS_CONFIG 中未找到，请先 write_config" >&2
    return 1
  fi

  local prompt_file="$PROJECT_DIR/.harness/${name}.prompt"
  printf '%s' "$prompt" > "$prompt_file"

  # 通过 send-keys 发送初始 prompt（-l 逐字符发送，Enter 单独发送）
  tmux send-keys -t "$pane" -l "$(cat "$prompt_file")"
  # 等待对方 TUI 把字符消化进输入框,再回车提交;不 sleep 时 Enter 常被吃掉
  sleep 0.3
  tmux send-keys -t "$pane" Enter
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
  # 不删 $HARNESS_CONFIG：新方案下它在 ${output_dir}/config.json，保留作为本次 run 的历史快照
  rm -f "$PROJECT_DIR/.harness/.pending-agents"
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
  # 清理所有运行时文件（不删 $HARNESS_CONFIG：新方案下它在 ${output_dir}/config.json，保留作为历史快照）
  rm -f "$HARNESS_PANES_FILE" "$HARNESS_MAIN_PANE_FILE" "$HARNESS_INIT_MARKER"
  rm -f "$PROJECT_DIR/.harness/.pending-agents"
  rm -rf "$PROJECT_DIR/.harness/signals"
  rm -f "$PROJECT_DIR/.harness/done"
  # 重新初始化
  mkdir -p "$PROJECT_DIR/.harness/signals"
  echo "$TMUX_PANE" > "$HARNESS_MAIN_PANE_FILE"
  touch "$HARNESS_INIT_MARKER"
}

# 工具函数：获取最新的 run 编号（不递增），目录为空时返回 0
# 真相来源是 ${branch_dir}/run-N 子目录本身——避免外部计数器与实际目录不同步的 bug
# （例如计数器文件丢失 / 跨机器同步缺漏 / 历史 run-N 目录是手工拷贝来的）
# 用 find 而不是 glob：跨 shell（bash/zsh）行为一致，不依赖 nullglob 选项
get_latest_run_number() {
  local branch_dir="$1"
  [ -d "$branch_dir" ] || { echo "0"; return; }
  local max=0
  local d n
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    n="${d##*/run-}"
    # 只接受纯数字目录名，run-abc / run-x 之类的非法目录忽略
    [[ "$n" =~ ^[0-9]+$ ]] || continue
    (( n > max )) && max=$n
  done < <(find "$branch_dir" -mindepth 1 -maxdepth 1 -type d -name 'run-*' 2>/dev/null)
  echo "$max"
}

# 工具函数：获取下一个 run 编号（latest + 1，不写回计数器文件——目录本身就是真相）
get_next_run_number() {
  local branch_dir="$1"
  local latest
  latest=$(get_latest_run_number "$branch_dir")
  echo $((latest + 1))
}

# 自动加载 agent 间通信函数（send_to_agent / complete_and_notify 等）
# 这样 SKILL 一次 source init.sh 就能拿到所有公共函数
source "$(dirname "${BASH_SOURCE[0]}")/harness-common.sh"
