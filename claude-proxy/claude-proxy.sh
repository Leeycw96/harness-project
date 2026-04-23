#!/usr/bin/env bash
# claude-proxy: 按 plan 合并 common.json + plans/<plan>.json，
# 将 env 注入进程环境，合并后的 settings 通过 --settings 传给 claude。
# 用法: claude-proxy.sh <plan-name> [claude args...]

set -euo pipefail

PROXY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${CLAUDE_PROXY_COMMON:-$PROXY_DIR/common.json}"
PLANS_DIR="${CLAUDE_PROXY_PLANS_DIR:-$PROXY_DIR/plans}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") <plan-name> [claude args...]" >&2
  exit 2
fi

PLAN="$1"; shift
PLAN_FILE="$PLANS_DIR/$PLAN.json"

if ! command -v jq >/dev/null 2>&1; then
  echo "claude-proxy: jq is required (brew install jq)" >&2
  exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "claude-proxy: 'claude' CLI not found in PATH" >&2
  exit 1
fi
if [[ ! -f "$PLAN_FILE" ]]; then
  echo "claude-proxy: plan '$PLAN' not found at $PLAN_FILE" >&2
  echo "Available plans:" >&2
  find "$PLANS_DIR" -maxdepth 1 -name '*.json' -exec basename {} .json \; 2>/dev/null | sort | sed 's/^/  - /' >&2
  exit 1
fi

# common 可以不存在；不存在就用 {} 兜底
COMMON_SRC="{}"
[[ -f "$COMMON" ]] && COMMON_SRC="$(cat "$COMMON")"

# 深合并：plan 覆盖 common（jq 的 * 对 object 递归 merge）
MERGED="$(jq -n \
  --argjson a "$COMMON_SRC" \
  --slurpfile b "$PLAN_FILE" \
  '$a * $b[0]')"

# 注入 env（每行一条 KEY=VALUE；env 值不应含换行）
while IFS= read -r entry; do
  [[ -z "$entry" ]] && continue
  key="${entry%%=*}"
  val="${entry#*=}"
  export "$key=$val"
done < <(jq -r '(.env // {}) | to_entries[] | "\(.key)=\(.value)"' <<<"$MERGED")

# 写合并后的 settings 到临时目录里的 settings.json（剔除 _proxy 私有段）
SETTINGS_DIR="$(mktemp -d -t "claude-proxy-${PLAN}")"
trap 'rm -rf "$SETTINGS_DIR"' EXIT INT TERM HUP
SETTINGS_FILE="$SETTINGS_DIR/settings.json"
jq 'del(._proxy)' <<<"$MERGED" > "$SETTINGS_FILE"

# 非官方 plan 默认 bypass permissions
# 不用 exec，保留当前 shell 进程以便 trap 可靠清理 SETTINGS_DIR
claude --settings "$SETTINGS_FILE" --dangerously-skip-permissions "$@"
