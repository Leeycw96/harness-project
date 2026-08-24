#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "用法: render-plan-html.sh <plan.xml.md> <implementation.md> <output.html>" >&2
}

fail() {
  echo "错误: $*" >&2
  exit 1
}

if [ "$#" -ne 3 ]; then
  usage
  exit 1
fi

plan_path="$1"
implementation_path="$2"
output_path="$3"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_path="$script_dir/../assets/plan-view-template.html"

[ -f "$plan_path" ] || fail "需求计划不存在: $plan_path"
[ -f "$implementation_path" ] || fail "代码改造计划不存在: $implementation_path"
[ -f "$template_path" ] || fail "HTML 模板不存在: $template_path"
[ -s "$plan_path" ] || fail "需求计划为空: $plan_path"
[ -s "$implementation_path" ] || fail "代码改造计划为空: $implementation_path"

case "$plan_path" in
  *.md) ;;
  *) fail "需求计划必须使用 .md 扩展名: $plan_path" ;;
esac
case "$output_path" in
  *.html) ;;
  *) fail "输出文件必须使用 .html 扩展名: $output_path" ;;
esac

if ! command -v xmllint >/dev/null 2>&1; then
  fail "xmllint 未安装，无法验证需求计划"
fi
if ! xmllint --noout "$plan_path" 2>/dev/null; then
  fail "需求计划不是合法 XML: $plan_path"
fi

all_declaration_count="$(grep -Ec '<implementation-plan([[:space:]]|>)' "$plan_path" || true)"
valid_declaration_count="$(grep -Ec '^[[:space:]]*<implementation-plan path="\.harness/plans/[^"]+-implementation\.md"[[:space:]]*/>[[:space:]]*$' "$plan_path" || true)"
if [ "$all_declaration_count" -ne 1 ] || [ "$valid_declaration_count" -ne 1 ]; then
  fail "需求计划必须包含且仅包含一个合法的 .harness/plans/*-implementation.md 声明"
fi

declared_path="$(sed -nE 's/^[[:space:]]*<implementation-plan path="([^"]+)"[[:space:]]*\/>[[:space:]]*$/\1/p' "$plan_path")"
plan_dir="$(cd "$(dirname "$plan_path")" && pwd)"
if [ "$(basename "$plan_dir")" != "plans" ] || [ "$(basename "$(dirname "$plan_dir")")" != ".harness" ]; then
  fail "需求计划必须位于 <project>/.harness/plans/: $plan_path"
fi
project_dir="$(cd "$plan_dir/../.." && pwd)"

case "$declared_path" in
  /*) declared_absolute="$declared_path" ;;
  *) declared_absolute="$project_dir/$declared_path" ;;
esac

implementation_absolute="$(cd "$(dirname "$implementation_path")" && pwd)/$(basename "$implementation_path")"
declared_dir="$(dirname "$declared_absolute")"
if [ ! -d "$declared_dir" ]; then
  fail "需求计划声明的代码改造计划目录不存在: $declared_dir"
fi
declared_absolute="$(cd "$declared_dir" && pwd)/$(basename "$declared_absolute")"
if [ "$declared_absolute" != "$implementation_absolute" ]; then
  fail "代码改造计划路径与 XML 声明不一致: $declared_path"
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
  if ! grep -Fxq "## $heading" "$implementation_path"; then
    fail "代码改造计划缺少章节: $heading"
  fi
done

output_dir="$(dirname "$output_path")"
[ -d "$output_dir" ] || fail "输出目录不存在: $output_dir"
output_dir="$(cd "$output_dir" && pwd)"
if [ "$output_dir" != "$plan_dir" ]; then
  fail "HTML 输出必须与需求计划位于同一目录: $plan_dir"
fi
output_path="$output_dir/$(basename "$output_path")"
temporary_path="$(mktemp "$output_dir/.harness-plan-html.XXXXXX")"
cleanup() {
  rm -f "$temporary_path"
}
trap cleanup EXIT

plan_name="$(basename "$plan_path" .md)"
if [ "$(basename "$output_path")" != "$plan_name.html" ]; then
  fail "HTML 输出必须与需求计划使用同一文件名: $plan_name.html"
fi
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    __HARNESS_PLAN_NAME_BASE64__)
      printf '%s' "$plan_name" | base64 | tr -d '\n'
      printf '\n'
      ;;
    __HARNESS_PLAN_XML_BASE64__)
      base64 < "$plan_path" | tr -d '\n'
      printf '\n'
      ;;
    __HARNESS_IMPLEMENTATION_MARKDOWN_BASE64__)
      base64 < "$implementation_path" | tr -d '\n'
      printf '\n'
      ;;
    *)
      printf '%s\n' "$line"
      ;;
  esac
done < "$template_path" > "$temporary_path"

[ -s "$temporary_path" ] || fail "HTML 输出为空"
if grep -Eq '__HARNESS_[A-Z_]+__' "$temporary_path"; then
  fail "HTML 输出仍包含未替换占位符"
fi
for required_marker in \
  'id="requirements-tab"' \
  'id="implementation-tab"' \
  'id="plan-xml-source"' \
  'id="implementation-markdown-source"'; do
  if ! grep -Fq "$required_marker" "$temporary_path"; then
    fail "HTML 输出缺少必需标记: $required_marker"
  fi
done

chmod 0644 "$temporary_path"
mv "$temporary_path" "$output_path"
trap - EXIT
printf '%s\n' "$output_path"
