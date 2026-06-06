#!/usr/bin/env bash
set -euo pipefail

# Harness Codex App 初始化脚本。
# 不启动 tmux；只创建 run 目录、config.json、conversation/ 和 signals/。

SCRIPT_PATH="${BASH_SOURCE[0]-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
mkdir -p "$PROJECT_DIR/.harness"

if ! command -v jq >/dev/null 2>&1; then
  echo "错误：jq 未安装，请先执行 brew install jq" >&2
  exit 1
fi

_abs_path() {
  local p="$1"
  case "$p" in
    /*) printf '%s\n' "$p" ;;
    *)  printf '%s/%s\n' "$PROJECT_DIR" "$p" ;;
  esac
}

copy_examples() {
  local src_dir="$1"
  if [ -d "$src_dir" ]; then
    mkdir -p "$PROJECT_DIR/.harness/examples"
    cp -R "$src_dir"/. "$PROJECT_DIR/.harness/examples/" 2>/dev/null || true
  fi
}

get_latest_run_number() {
  local branch_dir="$1"
  [ -d "$branch_dir" ] || { echo "0"; return; }
  local max=0 d n
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    n="${d##*/run-}"
    [[ "$n" =~ ^[0-9]+$ ]] || continue
    (( n > max )) && max=$n
  done < <(find "$branch_dir" -mindepth 1 -maxdepth 1 -type d -name 'run-*' 2>/dev/null)
  echo "$max"
}

get_next_run_number() {
  local branch_dir="$1"
  local latest
  latest=$(get_latest_run_number "$branch_dir")
  echo $((latest + 1))
}

init_harness_run() {
  local output_dir="$1"
  local plan_path="$2"
  if [ -z "$output_dir" ] || [ -z "$plan_path" ]; then
    echo "用法：init_harness_run <output_dir> <plan_path>" >&2
    return 2
  fi

  output_dir=$(_abs_path "$output_dir")
  plan_path=$(_abs_path "$plan_path")
  mkdir -p "$output_dir/conversation" "$output_dir/signals" "$output_dir/baseline"

  local config_file="$output_dir/config.json"
  jq -n \
    --arg project_dir "$PROJECT_DIR" \
    --arg output_dir "$output_dir" \
    --arg plan_path "$plan_path" \
    '{
      runtime: "codex-app",
      project_dir: $project_dir,
      output_dir: $output_dir,
      plan_path: $plan_path,
      agents: {
        "harness-builder": {
          type: "codex-subagent",
          config: ".codex/agents/harness-builder.toml",
          role_doc: ".codex/agents/harness-builder.md",
          sop_doc: ".codex/agents/harness-builder-AGENTS.md",
          partner: "harness-qa"
        },
        "harness-qa": {
          type: "codex-subagent",
          config: ".codex/agents/harness-qa.toml",
          role_doc: ".codex/agents/harness-qa.md",
          sop_doc: ".codex/agents/harness-qa-AGENTS.md",
          partner: "harness-builder"
        }
      }
    }' > "$config_file"

  export HARNESS_CONFIG="$config_file"
  printf '%s\n' "$config_file"
}

# 兼容旧 skill 文案中可能残留的函数名；Codex App 版只写 config。
write_config() {
  init_harness_run "$@"
}

source "$SCRIPT_DIR/harness-common.sh"
