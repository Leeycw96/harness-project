# 库存预占初验

**APPROVED**。隔离评估实现的三个功能全部完成，未发现阻断项。真实用户对 Plan HTML 的审阅仍待确认，本结论不表示用户批准。

## 范围与依据

- Builder：`keel-builder`，原生执行角色 `/root/inventory_builder`。
- 实现提交：`54433356b72081445ef6b0d82804d37a38ae1ffe`；基线：`fbad27c`。
- 目标来源：[plan.md](plan.md) 及其三个功能文档。目标总数为 3。
- 适用规范：当前部署的 delivery、acceptance、code-quality、document-writing、qa-scoring Spec。
- 检查 `inventory/`、`tests/`、新增迁移和相关 README。QA 仅在本交付目录保存补充测试与报告，未修改业务实现、方案或部署文件，未提交代码。

## 功能完成情况

全部条件都有实际结果。下表中的测试均已重跑；完整结果见 [qa-suite.log](qa-suite.log)，QA 补充结果见 [qa-probes.log](qa-probes.log)。

| 功能 | 验收条件及结果 | 可定位证据 |
| --- | --- | --- |
| reserve-stock | 数量小于和恰好等于可用量均成功；超出拒绝 | `tests/test_reservations.py:35`、`:89`；suite:72、82 |
| reserve-stock | 相同申请返回原记录；换商品或数量冲突，冲突优先于商品存在性判断 | `tests/test_reservations.py:43`；suite:83；probes:5 |
| reserve-stock | 已确认或已取消订单重试不重新预占 | `tests/test_reservations.py:89`、`:101`；suite:67、72；probes:1 |
| reserve-stock | 未知商品、无效标识或数量、不足库存拒绝且数据不变；包括布尔值、小数、字符串及整数上限 | `tests/test_reservations.py:50`、`:66`、`:80`；suite:77、79、85；HTTP suite:11–31、50–58 |
| reserve-stock | 多订单竞争不超卖，同订单竞争仅创建一次；重启保留库存与全部状态 | `tests/test_reservations.py:121`、`:137`、`:168`；suite:69、70、81；`qa-probes.py:135`、probes:1 |
| reserve-stock | 查询保留原字段，同时返回 stock、仅 RESERVED 的 reserved 和 available；多商品各自统计 | `tests/test_reservations.py:20`、`:32`；suite:78；`qa-probes.py:61`、probes:5；`inventory/service.py:17` 为单条汇总查询 |
| confirm-reservation | 首次确认 stock、reserved 同减，available 不变 | `tests/test_reservations.py:89`；suite:72；HTTP suite:1–10 |
| confirm-reservation | 顺序及 8 路同时重复确认只扣一次，均返回已确认记录 | suite:72；`qa-probes.py:55`、probes:4 |
| confirm-reservation | 已取消、未知预占无法确认且库存不变；状态更新异常和条件更新失败整体回滚 | suite:67、71、73、76、84；HTTP suite:32–43、55 |
| confirm-reservation | 同一预占并发确认与取消仅一个成功、另一返回冲突 | `tests/test_reservations.py:149`；suite:68 |
| cancel-reservation | 首次取消不改 stock，reserved 减少且 available 恢复相同数量 | `tests/test_reservations.py:101`；suite:67；probes:5 |
| cancel-reservation | 顺序及 8 路同时重复取消只释放一次 | suite:67；`qa-probes.py:58`、probes:3 |
| cancel-reservation | 已确认、未知预占无法取消且库存不变；取消更新异常或未影响行时也不改变记录 | suite:72、84；HTTP suite:6、56；`qa-probes.py:74`、probes:2 |
| cancel-reservation | 取消后重复创建原订单保留 CANCELLED，不重新占用 | suite:67；HTTP suite:37–43；probes:1 |

## 代码、测试与关联影响

通过。三个操作真实调用 SQLite；无固定成功结果、业务替身或 TODO。业务规则位于 `inventory/service.py:65`、`:96`、`:119`，HTTP 只解析输入、选择业务操作并生成响应（`inventory/http.py:24`）。

写事务先取 SQLite 写锁，提交后才返回；业务异常和数据库异常回滚，连接关闭（`inventory/service.py:39`）。数据库错误映射为 503 或 500（`:32`），已实际验证 10 秒写锁超时、确认异常回滚和 HTTP 500 JSON 响应。取消异常补测也通过。

迁移保留原商品并落实订单唯一、外键、正整数数量、状态和索引约束（`inventory/migrations/002_reservations.sql:1`；suite:80）。现有查询及 health 检查通过。HTTP 编码路径、JSON 对象、缺字段、类型、错误体和不允许的请求体已覆盖（`tests/test_http.py:76` 至 `:124`）。

实现与 QA 补测均沿用标准库、SQLite、unittest 及临时数据库。测试断言实际响应、库存数字和记录状态，无空测试。新增内容均被调用；本轮没有缺陷修复根因项，因此该项不适用。

## 实际验证

工作目录：`/private/var/folders/4y/0v4n5r7d5pz0xlp9s1kt81j40000gn/T/keel-backend-e2e-1xrmqpy4/project`。

| 命令 | 结果与证据 |
| --- | --- |
| `python3 -m compileall -q inventory tests` | 退出码 0 |
| `python3 -m py_compile .keel/iterations/codex/inventory-e2e/run-1/qa-probes.py` | 退出码 0，QA 补测语法检查通过 |
| `python3 -m unittest discover -s tests -v` | 获准本地端口后退出码 0，30 项通过，15.374 秒；suite:89–91 |
| `python3 .keel/iterations/codex/inventory-e2e/run-1/qa-probes.py` | 退出码 0，5 项通过，0.251 秒；probes:8–10 |
| `python3 -m inventory.http --help` | 退出码 0；实际启动由 QA 进程重启测试验证 |
| `git diff --check fbad27c..54433356b72081445ef6b0d82804d37a38ae1ffe` | 退出码 0 |
| `git diff --name-status fbad27c..54433356b72081445ef6b0d82804d37a38ae1ffe` | 仅 inventory、tests 和相关 README，共 7 个文件 |
| `git status --short --untracked-files=all` | 空输出；报告目录按项目约定忽略 |
| `python3 .codex/common/scripts/keel-qa-score.py record .keel/iterations/codex/inventory-e2e/run-1/qa-score-input.json --output-dir .keel/iterations/codex/inventory-e2e/run-1 --plan .keel/iterations/codex/inventory-e2e/run-1/plan.md` | 退出码 0，生成初验记录及来源、内容摘要 |
| `python3 .codex/common/scripts/keel-qa-score.py history .keel/iterations/codex/inventory-e2e/run-1 --last 1 --json` | 退出码 0；目标 3/3，五个检查组均通过，errors 为空 |

项目无独立构建、类型检查或测试编译步骤，采用项目规定的 Python 语法检查、测试与实际启动检查。

## 阻断、观察与待确认事项

- 阻断项：无。
- 环境观察：首次默认沙箱测试有 8 个 HTTP 初始化错误，均为 `PermissionError: [Errno 1] Operation not permitted`（绑定 127.0.0.1）。其余 22 项通过；获准重跑后全部通过。属于已解除的环境限制，不是本次回归。
- 非阻断观察：外部直接修改库存可形成不一致数据；方案要求的确认保护已验证返回 409 并保持原数据，未把外部破坏场景当作有效库存。
- 未验证/待确认：真实用户对 Plan HTML 的审阅仍待确认，超出本次隔离实现验收；没有本次实现必需的验证缺口。

## 评分记录

初验记录：[qa-score.json](qa-score.json)。目标 3/3 完成；分数由当前快照及检查明细计算。记录与报告结论一致，补充测试保存在 [qa-probes.py](qa-probes.py)。
