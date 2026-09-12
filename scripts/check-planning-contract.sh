#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "$repo_root/keel-plan/skills/keel-plan/scripts/render-plan-html.sh"
python3 "$repo_root/scripts/test-markdown-plan.py"

if rg -n 'implementation-plan|implementation_plan|plan-template\.xml|<plan>|xmllint' \
  "$repo_root/keel-plan" "$repo_root/keel-dev" "$repo_root/common"; then
  echo "Codex runtime 仍有旧 XML/双计划输入依赖" >&2
  exit 1
fi
for source_file in \
  "$repo_root/keel-dev/agents/keel-call-chain.md"; do
  for marker in 'PlantUML' '状态流转表' '实际执行状态变化' '流转条件' '证据路径'; do
    grep -Fq "$marker" "$source_file" || { echo "CallChain 缺少状态机契约: $marker" >&2; exit 1; }
  done
done
for runtime in "$repo_root/keel-dev"; do
  grep -Fq '状态变更符号变化' "$runtime/skills/keel-dev/SKILL.md"
done

echo "Markdown 单计划、HTML 图表审阅与 CallChain 状态机契约检查通过。"
