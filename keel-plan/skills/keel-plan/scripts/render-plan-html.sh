#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "用法: render-plan-html.sh <plan.md> <output.html>" >&2
  exit 1
fi
command -v python3 >/dev/null 2>&1 || { echo "错误: 需要 Python 3" >&2; exit 1; }
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd "$script_dir/../../../.." && pwd)"
if [ "$(basename "$(dirname "$(dirname "$(dirname "$script_dir")")")")" = ".agents" ]; then
  renderer="$root_dir/.codex/common/scripts/keel-plan.py"
else
  renderer="$root_dir/common/scripts/keel-plan.py"
fi
[ -f "$renderer" ] || { echo "错误: 缺少 Keel Markdown 渲染器，请重新部署" >&2; exit 1; }
exec python3 "$renderer" render "$1" "$2" "$script_dir/../assets/plan-view-template.html"
