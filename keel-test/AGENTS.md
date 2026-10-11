# Keel 后端试验目录

- 本目录是用户指定的测试工程，只修改本目录授权文件，不修改父项目 Keel 源码。
- 沿用父仓库 Git，不建立嵌套仓库；只暂存当前目录的任务文件，保留父仓库无关改动。
- Python 标准库、SQLite、unittest；适用检查 `python3 -m compileall -q inventory tests`，测试 `python3 -m unittest discover -s tests -v`。
- 角色、Skill 和 Spec 已部署在 .codex/ 与 .agents/；按“任务＋Spec”分派，主会话负责确认及运行记录。
- 既有 .keel/ 运行记录来自隔离临时项目，保留原始路径和摘要作为证据；新增执行另建 run，不改历史成绩或批准快照。
- 本次自动测试确认不等于用户已批准 Plan/Fix HTML，真实用户审阅仍待确认。
