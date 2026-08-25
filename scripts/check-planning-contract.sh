#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plan_skill="$repo_root/harness-plan/skills/harness-plan/SKILL.md"
xml_template="$repo_root/harness-plan/skills/harness-plan/assets/plan-template.xml"
implementation_template="$repo_root/harness-plan/skills/harness-plan/assets/implementation-plan-template.md"
html_template="$repo_root/harness-plan/skills/harness-plan/assets/plan-view-template.html"
html_renderer="$repo_root/harness-plan/skills/harness-plan/scripts/render-plan-html.sh"
work_dir="$(mktemp -d)"
trap 'find "$work_dir" -depth -delete' EXIT

for required_file in "$plan_skill" "$xml_template" "$implementation_template" "$html_template" "$html_renderer"; do
  if [ ! -f "$required_file" ]; then
    echo "缺少 Plan 契约文件: $required_file" >&2
    exit 1
  fi
done

bash -n "$html_renderer"

for required_marker in \
  'id="requirements-tab"' \
  'role="tablist"' \
  'id="implementation-tab"' \
  'id="requirements-panel"' \
  'id="implementation-panel"' \
  '__HARNESS_PLAN_NAME_BASE64__' \
  '__HARNESS_PLAN_XML_BASE64__' \
  '__HARNESS_IMPLEMENTATION_MARKDOWN_BASE64__'; do
  if ! grep -Fq "$required_marker" "$html_template"; then
    echo "HTML 审阅模板缺少标记: $required_marker" >&2
    exit 1
  fi
done

if rg -n 'innerHTML|outerHTML|insertAdjacentHTML|document\.write' "$html_template"; then
  echo "HTML 审阅模板不得把计划内容作为任意 HTML 写入" >&2
  exit 1
fi
if rg -n "(src|href)=[\"']https?://" "$html_template"; then
  echo "HTML 审阅模板不得加载远程资源" >&2
  exit 1
fi

if ! command -v xmllint >/dev/null 2>&1; then
  echo "错误: xmllint 未安装，无法验证 Plan XML" >&2
  exit 1
fi
xmllint --noout "$xml_template"

if [ "$(grep -Ec '^[[:space:]]*<implementation-plan path="\.harness/plans/[^"]+-implementation\.md"[[:space:]]*/>[[:space:]]*$' "$xml_template")" -ne 1 ]; then
  echo "Plan XML 必须且仅能包含一个合法的 implementation-plan 声明" >&2
  exit 1
fi

for heading in \
  "Purpose" \
  "Current Flow" \
  "Target Flow" \
  "Change Map" \
  "Interfaces and Data" \
  "Technical Decisions" \
  "Cross-cutting Constraints" \
  "Implementation Sequence" \
  "Validation" \
  "Risks and Recovery"; do
  if ! grep -Fxq "## $heading" "$implementation_template"; then
    echo "代码改造计划模板缺少章节: $heading" >&2
    exit 1
  fi
done

for required_pattern in \
  '\.harness/call-chain/\*\.md' \
  '真实用户决策' \
  '用户输入、代码、CallChain 和项目惯例' \
  '不得逐项询问用户确认' \
  '不存在真实用户决策时不发起澄清轮次' \
  '同步更新所有受影响章节' \
  '用户明确确认最终 HTML' \
  '\.harness/plans/<name>\.md' \
  '\.harness/plans/<name>-implementation\.md' \
  '\.harness/plans/<name>\.html' \
  'render-plan-html\.sh' \
  '禁止单独修改 HTML'; do
  if ! rg -q "$required_pattern" "$plan_skill"; then
    echo "Harness Plan Skill 缺少契约: $required_pattern" >&2
    exit 1
  fi
done

for forbidden_pattern in \
  '询问用户是否进行外部调研' \
  '用户拒绝且未指定方案时暂停' \
  '未确认范围、feature' \
  '让用户确认' \
  '确认清单' \
  '为每个 feature 确认' \
  '第一次生成 HTML 前，必须已经确认范围'; do
  if rg -q "$forbidden_pattern" "$plan_skill"; then
    echo "Harness Plan Skill 仍含逐段确认契约: $forbidden_pattern" >&2
    exit 1
  fi
done

if rg -n -i \
  'build-scope|scope.review|scope_review|build_scope|SCOPE_BUILD|SCOPE_REVIEW|scope_attempt' \
  "$repo_root/harness-plan" "$repo_root/harness-backend" "$repo_root/common"; then
  echo "Codex App runtime 仍含 build-scope 活跃引用" >&2
  exit 1
fi

mkdir -p "$work_dir/.harness/plans" "$work_dir/run-input"
cp "$implementation_template" "$work_dir/.harness/plans/example-implementation.md"
printf '\n安全文本：<script>alert("x")</script>、`inline-code` 与 [官方链接](https://example.com)。\n' \
  >> "$work_dir/.harness/plans/example-implementation.md"
sed \
  's#\.harness/plans/order-cancellation-implementation\.md#.harness/plans/example-implementation.md#' \
  "$xml_template" > "$work_dir/.harness/plans/example.md"

html_output="$work_dir/.harness/plans/example.html"
"$html_renderer" \
  "$work_dir/.harness/plans/example.md" \
  "$work_dir/.harness/plans/example-implementation.md" \
  "$html_output" >/dev/null

[ -s "$html_output" ] || { echo "HTML 审阅文件未生成" >&2; exit 1; }
if rg -q '__HARNESS_[A-Z_]+__' "$html_output"; then
  echo "HTML 审阅文件包含未替换占位符" >&2
  exit 1
fi
if grep -Fq '<script>alert("x")</script>' "$html_output"; then
  echo "HTML 审阅文件泄漏了未编码的可执行项目内容" >&2
  exit 1
fi

decode_base64() {
  if base64 --decode </dev/null >/dev/null 2>&1; then
    base64 --decode
  else
    base64 -D
  fi
}

extract_embedded_source() {
  local source_id="$1" html_file="$2"
  awk -v source_id="$source_id" '
    index($0, "id=\"" source_id "\"") { capture = 1; next }
    capture && /<\/script>/ { exit }
    capture { printf "%s", $0 }
  ' "$html_file" | tr -d '[:space:]' | decode_base64
}

extract_embedded_source "plan-xml-source" "$html_output" > "$work_dir/decoded-plan.md"
extract_embedded_source "implementation-markdown-source" "$html_output" > "$work_dir/decoded-implementation.md"
cmp "$work_dir/.harness/plans/example.md" "$work_dir/decoded-plan.md"
cmp "$work_dir/.harness/plans/example-implementation.md" "$work_dir/decoded-implementation.md"

assert_render_fails_without_overwrite() {
  local label="$1" plan_input="$2" implementation_input="$3"
  local protected_output="$work_dir/.harness/plans/protected.html"
  printf 'sentinel\n' > "$protected_output"
  if "$html_renderer" "$plan_input" "$implementation_input" "$protected_output" >/dev/null 2>&1; then
    echo "HTML 渲染器未拒绝错误输入: $label" >&2
    exit 1
  fi
  if ! grep -Fxq 'sentinel' "$protected_output"; then
    echo "HTML 渲染失败覆盖了已有文件: $label" >&2
    exit 1
  fi
}

printf '<plan>\n' > "$work_dir/.harness/plans/invalid.md"
sed '/^## Risks and Recovery$/d' \
  "$work_dir/.harness/plans/example-implementation.md" \
  > "$work_dir/.harness/plans/missing-section-implementation.md"
sed 's#example-implementation\.md#other-implementation.md#' \
  "$work_dir/.harness/plans/example.md" \
  > "$work_dir/.harness/plans/wrong-reference.md"

assert_render_fails_without_overwrite \
  "缺失需求计划" \
  "$work_dir/.harness/plans/missing.md" \
  "$work_dir/.harness/plans/example-implementation.md"
assert_render_fails_without_overwrite \
  "非法 XML" \
  "$work_dir/.harness/plans/invalid.md" \
  "$work_dir/.harness/plans/example-implementation.md"
assert_render_fails_without_overwrite \
  "缺失 Markdown 章节" \
  "$work_dir/.harness/plans/example.md" \
  "$work_dir/.harness/plans/missing-section-implementation.md"
assert_render_fails_without_overwrite \
  "错误 implementation-plan 引用" \
  "$work_dir/.harness/plans/wrong-reference.md" \
  "$work_dir/.harness/plans/example-implementation.md"

printf 'sentinel\n' > "$work_dir/.harness/plans/wrong-name.html"
if "$html_renderer" \
  "$work_dir/.harness/plans/example.md" \
  "$work_dir/.harness/plans/example-implementation.md" \
  "$work_dir/.harness/plans/wrong-name.html" >/dev/null 2>&1; then
  echo "HTML 渲染器未拒绝错误的输出文件名" >&2
  exit 1
fi
grep -Fxq 'sentinel' "$work_dir/.harness/plans/wrong-name.html"

if find "$work_dir/.harness/plans" -name '.harness-plan-html.*' -print -quit | grep -q .; then
  echo "HTML 渲染失败遗留临时文件" >&2
  exit 1
fi

cp "$work_dir/.harness/plans/example.md" "$work_dir/run-input/plan.md"
cp "$work_dir/.harness/plans/example-implementation.md" "$work_dir/run-input/implementation-plan.md"

(
  export PROJECT_DIR="$work_dir"
  source "$repo_root/common/scripts/harness-init.sh"

  resolved="$(resolve_implementation_plan_path "$work_dir/.harness/plans/example.md")"
  [ "$resolved" = "$work_dir/.harness/plans/example-implementation.md" ]

  if init_harness_run "$work_dir/missing-input" "$work_dir/run-input/plan.md" >/dev/null 2>&1; then
    echo "init_harness_run 未拒绝缺失的代码改造计划" >&2
    exit 1
  fi

  full_state="$(init_harness_run "$work_dir/full" "$work_dir/run-input/plan.md" "$work_dir/run-input/implementation-plan.md")"
  fast_state="$(init_harness_fast_run "$work_dir/fast" "$work_dir/run-input/plan.md" "$work_dir/run-input/implementation-plan.md")"

  jq -e '
    .implementation_plan_path != null
    and .artifacts.build_scope == null
    and .artifacts.scope_review == null
    and .limits.scope_attempts == null
    and .scope_attempt == null
  ' "$full_state" >/dev/null
  jq -e '
    .implementation_plan_path != null
    and (.fast.skipped | index("scope-review") | not)
  ' "$fast_state" >/dev/null
)

echo "Codex App Harness Plan Draft-first 三产物与 Backend 无 build-scope 契约检查通过。"
