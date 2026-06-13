# Harness 项目协作规范

本文件保留给旧工具读取。当前仓库以 `AGENTS.md` 为主要协作规范,并且只维护 Codex App subagent runtime。

## 测试 `bin/harness` 时的清理规则

对 `bin/harness` 做端到端测试时,必须严格遵守:

- **目标目录用 `mktemp -d` 创建**:不要在 harness-project 仓库内或其他长期目录跑测试
- **测试结束后用 `rm -rf "$test_dir"` 清理**临时目录,不要遗留
- **如果测试期间临时移走了仓库内文件**,务必恢复回原位置
- 完成后跑 `git status --short` 确认没有测试遗留

推荐验证:

```bash
bash -n bin/harness
find common -type f -name '*.sh' -exec bash -n {} \;
tmp=$(mktemp -d)
bin/harness backend "$tmp"
rm -rf "$tmp"
git status --short
```

## Runtime 边界

- 不再维护 `.claude/` agent runtime。
- 不再维护 Codex CLI tmux runtime。
- 新工作应修改根级 `common/`、`harness-plan/`、`harness-backend/`。
