# 库存服务流程试验

Plan、Dev、Fix 的隔离试验已完成。主会话按当前 Skill 编排原生 Agent，Agent 实际加载部署角色与 Spec；没有改 Keel 规范或脚本绕过要求。

下表记录原始试验。当前 Plan 展示稿随后按新表达规则手工精简时序图，技术约束保留在功能 MD；历史计划快照、评分和日志未改，未重新运行 Agent 评估。简明验收表达样例见 [QA 摘要](.keel/eval/concise-output-example/qa-feedback.md)。

## 优先审阅

- [Plan HTML](.keel/plans/inventory-reservations.html)：三个目标、一个业务总览、状态机、ER 图和三个精简时序图，六张图全部真实渲染。
- [Fix HTML](.keel/bugs/BUG-001/bug.html)：问题、原因、改造点、影响点、建议验证点五章；HTML 正文约 211 个字符，源 Markdown 共 257 个字符，不展示证据代码。

## 实际结果

| 流程 | 结果 | 证据 |
| --- | --- | --- |
| Plan | 结构与渲染通过，正文约 2943 个字符 | [源文档](.keel/plans/inventory-reservations.md) |
| Dev | QA APPROVED，3/3 目标，100 分；30 项测试和 5 项独立验证通过 | [QA 报告](.keel/iterations/codex/inventory-e2e/run-1/qa-feedback.md) |
| 流程维护 | 用户下单业务流程文档 | [流程文档](.keel/call-chain/user-order.md) |
| Fix | QA APPROVED，1/1 目标，100 分；32 项测试和 3 项独立验证通过 | [QA 报告](.keel/bugs/BUG-001/runs/run-1/qa-feedback.md) |
| 原场景复验 | 10 件请求由 409 恢复为 200；主会话重放 12 个关联 HTTP 请求通过 | [重放记录](.keel/eval/original-scenario-retest.json) |

## 产物效果与发现

- Plan 首稿总览拆成三张，修订后合为一张；QA 首稿偏长，精简后约减少 52%。[首稿及反馈](.keel/eval/observations.md)已保留。仅输入简洁 Spec，第一次产出仍可能有冗余。
- QA 的其他检查组包含自身文档、评分格式等要求，不能都解释为 Builder 质量；本次业务目标完成率有独立验证支撑，不自动决定后续减检。
- 额外启用三个历史图表集成测试：两个通过，一个旧断言仍要求模板已删除的 refund_tasks，失败日志已保留，未在本次试验中修改框架测试。
- 后续规范与模板调整已将该旧断言同步为实际 orders 模型；原始失败日志仍作为历史证据保留。
- 8 路突发 HTTP 有连接重置，基线与修复版本各三轮对照均出现两轮，库存始终正确。QA 将其列为原有非阻断观察，详见 Fix 报告。

## 执行说明

故障由测试主动注入，明确标注为样本，不归因于原 Builder。自动推进用的是隔离测试确认；真实用户对两份 HTML 的审阅仍待确认。

原生协作接口由任务环境指定已部署角色配置，未验证 Codex App UI 自动选择注册角色。运行记录保留原临时路径和摘要，作为历史证据；源码可在本目录直接运行。提交历史保存在 evidence/history.bundle。

部署的 50 个文件均与源版本 6966d13 一致。初验 JSON、日志、首稿、批准快照及执行标识位于 .keel/，结果总览见 [评分总览](.keel/eval/qa-history-summary.json)。
