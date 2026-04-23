#!/bin/bash

# Harness CLI 安装脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_BIN="$SCRIPT_DIR/bin/harness"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Harness CLI 安装 ===${NC}"
echo ""

# 检查 shell
if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    SHELL_RC="$HOME/.bashrc"
else
    SHELL_RC="$HOME/.profile"
fi

# 添加 PATH
if ! grep -q "harness-project/bin" "$SHELL_RC" 2>/dev/null; then
    echo ""
    echo "正在添加 harness 到 PATH..."
    echo "" >> "$SHELL_RC"
    echo "# Harness CLI" >> "$SHELL_RC"
    echo "export PATH=\"$SCRIPT_DIR/bin:\$PATH\"" >> "$SHELL_RC"
    echo -e "${GREEN}✓ 已添加到 $SHELL_RC${NC}"
else
    echo -e "${GREEN}✓ PATH 已配置${NC}"
fi

# 创建软链接（可选）
read -p "是否创建 /usr/local/bin/harness 快捷方式? (需要 sudo) [y/N]: " create_symlink
if [[ "$create_symlink" =~ ^[Yy]$ ]]; then
    if sudo ln -sf "$HARNESS_BIN" /usr/local/bin/harness; then
        echo -e "${GREEN}✓ 快捷方式已创建${NC}"
    else
        echo "创建快捷方式失败，但不影响使用"
    fi
fi

echo ""
echo -e "${GREEN}安装完成!${NC}"
echo ""
echo "请运行以下命令使 PATH 生效:"
echo "  source $SHELL_RC"
echo ""
echo "然后可以在任意项目目录使用:"
echo "  harness backend    # 部署 backend harness"
echo "  harness fullstack  # 部署 fullstack harness"
echo "  harness status     # 检查状态"
echo ""
