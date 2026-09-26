# Eval Cases

每个 case 在隔离仓库快照中运行，baseline 与 candidate 使用相同输入。

| ID | 入口 | 场景 | 必须满足 |
|----|------|------|----------|
| PLAN-01 | keel-plan | 明确的小型变更 | 索引含目标与逐项验收，功能文件含时序图选择和简洁改造点；HTML 背景仅列 User Stories、不按功能分类，单独展示技术功能效果及验收、不混入 HTTP 契约或实现步骤，并包含当前流程总览 |
| PLAN-02 | keel-plan | 需求同时包含本次范围、交互依赖和未来能力 | 只把确认项写入 feature；其余进入依赖或 out-of-scope |
| PLAN-03 | keel-plan | 缺少会改变方案的关键条件 | 一次只问一个关键问题，不自行补全 |
| PLAN-04 | keel-plan | 事务、幂等、权限和未就绪外部依赖 | 约束与依赖状态准确进入 plan |
| PLAN-05 | keel-plan | 现有复杂流程已有 CallChain | 先用 CallChain 定位入口和生命周期，再核对代码与测试；HTML 在状态图之前展示当前业务 PlantUML 流程总览 |
| PLAN-06 | keel-plan | 登录能力未指定 token 或 session，项目也无既定方案 | 先询问是否外部调研；同意后比较 2–3 个方案并等待用户选择；拒绝且未授权代选时暂停 |
| PLAN-07 | keel-plan | 跨模块业务流程改造 | 索引按目标关联多个 MD，各功能仅数据模型、时序图、接口设计和简洁改造点；Builder 只读指定功能及引用章节，改造点保持定位加一句话 |
| PLAN-08 | keel-plan | 用户最终确认前仍有关键选型或 TBD | 不报告 Plan 完成，不把关键决策交给 Builder |
| PLAN-09 | keel-plan | 订单表只新增一个字段 | HTML 在时序图前展示 ER 图，突出新增字段及必要关联，省略无关既有字段；MD 有一致 SQL |
| PLAN-10 | keel-plan | 仅索引调整或数据回填 | SQL 保留在 MD 数据模型，HTML 不增加数据模型章节 |
| PLAN-11 | keel-plan | 用户反馈修改验收或重点逻辑 | 修改源文件并重渲染；HTML 共享内容与 MD 一致，不产生重复维护的验收列表 |
| PLAN-12 | keel-plan | 多功能共享模型和接口 | 只在所属功能定义 SQL/接口，其他功能直接引用章节；HTML 仅展示一次，接口无功能分类；下载包含可独立验证的索引与功能文件 |
| PLAN-13 | keel-dev | 初始化后源计划被修改或移除 | full/fast 快照包含全部关联功能文件，state 指向 run 内索引；恢复不重新读取源计划，缺文件阻断 |
| PLAN-14 | keel-plan | 在既有流程中仅增加内部校验状态，表结构与对外契约不变 | Planner 详述新增状态与入出条件，合并未改动步骤，保留超时等必要联动；MD 标注本期不涉及模型/接口变更，HTML 省略对应栏目及未变更的业务总览，保留状态机和选中时序图 |
| PLAN-15 | keel-plan | 新增状态由现有响应字段返回，或数据库枚举约束需扩展 | 没有新增接口/字段也须列出现有接口枚举或 SQL 的变化；不能标本期不涉及，必要模型/接口引用保留 |
| PLAN-16 | keel-plan | 原已有校验阶段，仅新增校验中状态；或新增人工审核阶段 | 按同一业务粒度判断：前者可省总览，后者必须有总览；有变化却缺图、未提供省略依据或判定未知均拒绝渲染 |
| ASO-06 | plan / full | 同一业务由 HTTP、消息消费者和定时任务推进 | Planner 与 CallChain 均获得同一份粒度规范，按业务目标和阶段聚合；总览未变也不跳过状态及入口维护 |
| ASO-05 | keel-plan | 更换 Planner 或项目方案规范 | 不改另一方即可下发同一任务；主会话处理用户问题、检查和渲染，Planner 只调研或修改源文档，不直接询问用户、改 HTML 或重复实现开发职责 |
| ASO-01 | full / fast | 更换实现 Agent，沿用当前规范 | 不修改 Spec 即可下发相同目标与任务协议；阶段、tag、artifact 与提交范围保持一致 |
| ASO-02 | full / fast | 更换项目 Spec，沿用三个角色定义 | A 文件不变；实现与验收使用同一份开发标准，缺失引用阻断，不暗自回退固定规范 |
| ASO-03 | keel-dev | QA 通过后的独立流程审查 | 按 S 维护标准判定；不读取 prefilter 预判，NOOP/UPDATED 及独立 docs commit 与旧流程一致 |
| ASO-04 | full / fast | 任务中断后恢复 | 沿用当前 run 的角色/规范绑定、计划快照和进度；旧 profile 可恢复，旧 run 无绑定时补默认 |
| BUG-01 | keel-fix | 缺少本地运行条件，有匹配版本的代码和现场日志 | Builder 依据证据定位，不要求先有 Plan 或本地复现；说明原因与现象的关联、可验证行为及现场验证缺口 |
| BUG-02 | keel-fix | 代码中有错误日志语句，用户未提供运行日志 | 不将该语句当作本次执行证据；请求能区分原因的日志或检查结果，不猜测提交补丁 |
| BUG-03 | keel-fix | 两个候选原因均符合现象，暂不能定位 | 列出各自依据、反对证据和区分方法；主会话询问用户，待补充证据，不强选根因或空转 |
| BUG-04 | keel-fix | 用户补充日志或确认预期，但未批准修复方案 | 每个局部 BUG 的独立 HTML 均须确认后再编码；补证据不算批准，确认与 MD/HTML 版本绑定 |
| BUG-05 | keel-fix | 现有日志不足，需要新增诊断日志 | 说明观测能力改造需求并提示走 Plan，原 BUG 仍待定位；不在证据不足时猜测补丁 |
| BUG-06 | keel-fix | 用户确认方案后出现关键流程变化或根因被推翻 | 根因不成立回到定位；设计变化暂停 fix 并提示转 Plan，不调度 CallChain；局部方案变化重新渲染确认，旧快照不得修改 |
| BUG-07 | keel-fix | 本地回归测试通过，原故障只在测试环境出现 | 明确验证范围和现场缺口；保持待测试复验，收到原场景明确验证结果后才记完成 |
| BUG-08 | keel-fix | 已定位的局部金额计算缺陷，无设计变化 | 不执行 keel-plan/dev/fast；从 bug.md 生成三栏 HTML，用户确认后仅 Builder 与 QA 完成修复，HTML 与执行快照一致 |
| BUG-09 | keel-fix | 漏实现了原需求中的新接口，或需新增状态/调整业务流程 | 缺陷标签不豁免设计评审；保留定位证据，提示用户走 keel-plan 并停止 fix，不先制作重复方案 |
| FAST-01 | keel-dev-fast | 局部校验 bugfix | Builder 和 QA 仅消费执行 MD，不读取 HTML 或审阅素材；只改相关代码；相关测试通过；QA 覆盖本轮 commit |
| FULL-01 | keel-dev | 跨模块多阶段状态流转 | Preflight 后直接 BUILD；不存在 build-scope 阶段；QA 门禁通过；CallChain 为 UPDATED |
| REVIEW-01 | keel-dev | 预埋 stub、遗漏副作用、入口层业务逻辑和缺失测试 | P0/P1 召回不低于 baseline |
| REVIEW-02 | keel-dev | 工作区包含用户无关改动 | Builder 不提交、QA 不阻断无关改动 |
| CHAIN-01 | keel-dev | 简单查询或同步 CRUD | CallChain 为 NOOP |
| CHAIN-02 | keel-dev | shadow 主会话预判 NOOP、独立 Agent 判 UPDATED | 记录 `safe=false`，禁止启用真实跳过 |
| CHAIN-03 | keel-dev | shadow 主会话保守预判 RUN、独立 Agent 判 NOOP | 记录安全误报，不阻断准入 |
| RECOVERY-01 | keel-dev | Agent 中断或 artifact 缺失 | 从磁盘状态恢复；超过限制进入 PAUSED |
| PREFLIGHT-01 | keel-dev | 主编译失败 | 不启动 Agent，run 记录失败摘要 |
| PREFLIGHT-02 | keel-dev | 测试编译存在基线失败 | 询问用户；允许继续时 QA 不误判为本轮回归 |

## Seeded QA Defects

`REVIEW-01` 至少放入以下四类缺陷：

- 返回硬编码成功结果但没有真实持久化。
- 成功响应后缺少 plan 要求的状态或事件副作用。
- Controller、RPC、MQ 或 Scheduler 入口包含业务分支。
- Service public 契约缺少关键正常或异常测试。

评估报告必须逐项记录发现证据，不能只记录最终 APPROVED/REJECTED。
