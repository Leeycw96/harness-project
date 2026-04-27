# Harness 项目协作规范

本文件给后续协作的 Claude 实例使用,记录在当前仓库工作时必须遵守的约定。

## 测试 `bin/harness` 时的清理规则

对 `bin/harness` 做端到端测试时,必须严格遵守:

- **目标目录用 `mktemp -d` 创建**:不要在 harness-project 仓库内或其他长期目录跑测试
- **测试结束后用 `rm -rf "$test_dir"` 清理**临时目录,不要遗留
- **如果测试期间临时移走了仓库内文件**(例如 `mv harness-backend/skills/harness-backend-smoke /tmp/...` 模拟旧版部署),**务必把它恢复回原位置**
- **完成后跑 `git status` 确认工作区干净**,无未跟踪 / 已修改的测试遗留
- 端到端命令尽量在一行 `&&` 链中收尾(包含 `rm -rf`),避免中间步骤失败导致清理被跳过
