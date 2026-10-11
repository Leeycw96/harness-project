# BUG-001 独立验收

APPROVED，仅适用于本次隔离评估修复。阻断项：无。

Builder：`keel-builder`（原生 `/root/inventory_fix_builder`）；提交：`68e10818b5172db30a3bc2cd082ff8beab516436`。范围与依据为 [approved.md](approved.md)、[approved-investigation.md](approved-investigation.md)；完整检查明细见 [qa-score.json](qa-score.json)。QA 未改业务实现、部署文件或提交代码。

## 代码验收

修复目标完成：库存恰好足够和申请最后一件均成功；不足仍拒绝，失败不改变库存。重复申请不重复占用，订单冲突仍拒绝；确认只扣减一次，取消只释放一次，终态不能反向操作。关联并发、异常回滚及保存后重启通过。

`inventory/service.py:86` 仅把不足条件改为“大于可用库存”。两项新增测试有响应、状态和库存断言；没有改变状态、流程、接口、模型或事务设计。项目测试 32/32 通过，独立探针 3/3 通过（[项目日志](qa-suite-http.log)、[探针日志](qa-probes.log)）。

## 原场景复验

通过隔离环境的真实 HTTP 进程复放原 `boundary-order` 请求。基线可用 10 申请 10 返回 409，完整结果与原证据一致；修复后返回 200、`RESERVED`，账面库存 10、预占 10、可用 0。重启后重复申请不新增占用；取消恢复 10，新订单预占全部库存后确认归零。证据见 [qa-http-evidence.json](qa-http-evidence.json)。

## 实际验证与遗留

命令均在本项目根目录执行；完整目录及语法、启动参数、提交差异检查结果见 [qa-checks.log](qa-checks.log)。

- `python3 -m compileall -q inventory tests`、`python3 -m inventory.http --help`、提交间 `git diff --check`：退出 0。无独立构建或类型检查。
- `python3 -m unittest discover -s tests -v`：32/32。首次默认沙箱有 9 项端口绑定错误；获准放开本地端口后通过，属环境限制（[首次日志](qa-suite.log)）。
- `python3 .keel/bugs/BUG-001/runs/run-1/qa-probes.py`：3/3，含基线复现、原请求生命周期及 4 路全库存并发。
- `python3 .keel/bugs/BUG-001/runs/run-1/qa-transport-probe.py`：对照退出 0。8 路突发连接重置在基线和修复版各 3 轮中的 2 轮出现；6 轮库存均正确，属于已有问题，未纳入本次边界修复（[对照证据](qa-transport-evidence.json)、[首次 8 路探针](qa-probes-first.log)）。

真实用户对 HTML 的审阅仍待确认，本报告和评分不代表用户批准。8 路连接承载问题如需解决，应另行调查；无本次新增失败。工作区状态检查为空。
