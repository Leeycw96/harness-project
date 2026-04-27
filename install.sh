#!/usr/bin/env bash
# 把 harness CLI 加入 PATH

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_BIN_DIR="$SCRIPT_DIR/bin"

if [ ! -x "$HARNESS_BIN_DIR/harness" ]; then
  if [ -f "$HARNESS_BIN_DIR/harness" ]; then
    chmod +x "$HARNESS_BIN_DIR/harness"
  else
    echo "错误: 未找到 $HARNESS_BIN_DIR/harness" >&2
    exit 1
  fi
fi

# 选择 shell rc 文件
if [[ "${SHELL:-}" == *"zsh"* ]]; then
  RC="$HOME/.zshrc"
elif [[ "${SHELL:-}" == *"bash"* ]]; then
  RC="$HOME/.bashrc"
else
  RC="$HOME/.profile"
fi

EXPORT_LINE="export PATH=\"$HARNESS_BIN_DIR:\$PATH\""

if [ -f "$RC" ] && grep -Fq "$HARNESS_BIN_DIR" "$RC"; then
  echo "PATH 已在 $RC 中,跳过写入。"
else
  {
    echo ""
    echo "# Harness CLI"
    echo "$EXPORT_LINE"
  } >> "$RC"
  echo "已写入 $RC"
fi

echo ""
echo "PATH 在当前终端尚未生效,请执行:"
echo "  source $RC"
echo ""
echo "或新开一个终端窗口。之后可用:"
echo "  cd /path/to/your/project"
echo "  harness backend"
