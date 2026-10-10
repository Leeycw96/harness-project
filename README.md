# Keel

当前版本: **4.0.3**（见 `VERSION`）。

版本更新记录见 [CHANGE_LOG.md](CHANGE_LOG.md)。

命令入口为 `keel`，开发模式为 `dev`，计划与运行数据使用 `.keel/`。本次更名直接使用新名称，不提供旧命令别名或自动迁移。

Keel 是一组面向 Codex App 的 skills + agent 手册，用于编排 Planner、Builder、QA 和 CallChain，完成从业务理解到代码交付的开发工作流。

## 目录结构

```text
keel-project/
├── bin/keel          # 部署 CLI
├── install.sh        # 把 bin/ 写入 PATH
├── common/           # 共享规范和脚本，部署到 .codex/common/
├── keel-plan/        # /keel-plan 编排、Planner、模板与渲染入口
└── keel-dev/         # dev skills 与 Codex custom agents
```

模式目录使用 `keel-<mode>/skills/` 和 `keel-<mode>/agents/`。

## 安装 CLI

```bash
git clone <this-repo>
cd keel-project
./install.sh
source ~/.zshrc      # 或新开一个终端
```

`install.sh` 只把 `bin/` 加入 PATH,不会部署任何 skill。

## 部署

使用 `--codex` 部署。默认目标为当前目录:

```bash
cd /path/to/your/project
keel dev --codex
```

也可以指定目标目录:

```bash
keel dev --codex /path/to/your/project
```

`keel dev` 会同时部署 `/keel-plan`、`/keel-dev` 和 `/keel-fix`。

旧格式不再支持:

- `keel dev`
- `keel dev /path/to/project`
- `keel --codex dev`
- `keel --runtime ...`
- `keel ... --codex-cli`

## Codex App 部署结果

```text
.agents/
└── skills/
    ├── keel-plan/
    │   ├── SKILL.md
    │   ├── assets/
    │   │   ├── plan-template.md
    │   │   ├── plan-template.features/  # 按功能拆分的文档示例
    │   │   ├── plan-review-template.md
    │   │   └── plan-view-template.html
    │   └── scripts/
    │       └── render-plan-html.sh
    ├── keel-dev/
    └── keel-fix/
.codex/
├── common/
│   ├── refs/
│   │   ├── keel-work-spec.md          # S：通用工作要求
│   │   ├── keel-code-quality-spec.md  # S：代码与测试质量
│   │   ├── keel-investigation-spec.md # S：问题调查
│   │   ├── keel-proposal-spec.md      # S：方案设计与编写
│   │   ├── keel-fix-review-spec.md    # S：修复说明编写
│   │   ├── keel-implementation-spec.md # S：代码实施
│   │   ├── keel-acceptance-spec.md    # S：交付验收
│   │   ├── keel-flow-index-spec.md    # S：流程文档维护
│   │   ├── keel-bug-scope-spec.md     # S：局部修复边界
│   │   ├── keel-code-change-spec.md   # S：改造点表达
│   │   ├── keel-business-flow-spec.md # S：业务流程表达
│   │   └── ...                         # 5 份旧名称兼容 Spec
│   └── scripts/
├── agents/
│   ├── keel-planner.md
│   ├── keel-planner.toml
│   ├── keel-builder.md
│   ├── keel-builder.toml
│   ├── keel-qa.md
│   ├── keel-qa.toml
│   ├── keel-call-chain.md
│   └── keel-call-chain.toml
└── .keel/
    └── installed-manifest
```

## 语言与项目适配

业务开发规则与语言无关：先识别项目既有语言、架构、测试和 CI 配置，再选择代码落点与验证命令。业务契约可由模块、函数或类方法承载，不强制 Controller/Service 分层、Java 测试后缀或 Maven。多语言仓库按受影响模块分别验证；没有独立编译阶段时使用适用的类型/语法、加载和测试检查，不把未执行记录为通过。

模板保留明确标注的 Java/PostgreSQL 示例用于说明写法，实际计划必须替换为项目事实。Python 3 和 PlantUML/Java 是 Keel HTML 渲染工具的依赖，不要求业务项目采用 Python 或 Java。

## 阶段职责

借鉴 [Karpathy 启发的四项原则](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/README.zh.md)，按 Keel 阶段职责整合：Plan 在制定计划时核实假设、调研歧义并请用户完成关键取舍；Dev 按已确认方案落实简洁优先、精准修改与目标驱动，Builder 实现，QA 对照目标与证据验收。仅实际代码偏差或关键遗漏返回 Plan，验证修复仍遵守既有次数上限。

## ASO 设计规范

本项目按 **Agent、Spec、Orchestration** 组织能力。A 定义角色，S 定义使用场景的规范，O 由对应 Skill 的 `SKILL.md` 说明流程。Skill 选择执行者、给清任务与规范，Agent 自主完成本职工作。新增或调整流程时，先确定内容属于哪一层；职责分离不要求每条规则都拆一个文件。

| 层次 | 应包含 | 不应包含 |
| --- | --- | --- |
| **A（Agent）** | 角色、能力、原则：专业职责、擅长的工作、稳定的判断方式 | 固定项目规范路径、阶段步骤、状态字段、重试次数、完成命令 |
| **S（Spec）** | 按场景组织的工作规范：操作边界、质量标准及其适用条件、必需产物、文档与图表格式、验收要求 | 调度哪个 Agent、什么时候问用户、阶段推进与恢复 |
| **O（Orchestration）** | `SKILL.md` 中的高层编排：主要步骤及顺序、执行者、任务与 Spec、必要的用户决策和步骤衔接 | 重写 Agent 的角色原则，重复维护 Spec 中的标准，细管 Agent 的执行方法，堆叠限制，将编排主线拆到独立编排文档 |

### 编写与调整要求

1. Agent Markdown 固定为“角色、能力、原则”。原则用能直接指导行动的句子，如最小修改、不过度设计、先看已有实现、定位不出来就明说；TOML 只做必要注册并加载角色说明。
2. Spec 按使用场景组织，定义工作边界、质量要求、必需产物及适用条件；共享标准保持一个来源，Builder 与 QA 使用同一份代码和测试标准。本次需求与修复目标放在任务中，Spec 保留长期规则。
3. 每个 `SKILL.md` 说明从接收输入到最终交付的主要步骤及顺序，包括主会话承担的沟通、检查和交付。涉及 subagent 时，明确调用哪个 Agent、这一步要完成什么、依据什么 Spec，并提供必要的任务资料；仅在影响步骤衔接时补充输出、分支或恢复说明，不要求每一步套用完整字段模板。
4. 信任 Agent 的专业能力，由其依据任务、Spec 和项目事实自主选择调研路径、工具与局部执行方法。编排聚焦目标和协作，不逐项规定模型能够自主完成的操作，不重复角色原则或 Spec，不堆叠禁止事项。仅保留授权边界、关键用户决策、必要质量门禁和跨步骤交接要求；主会话依据结果推进，已有明确决定直接沿用。
5. 编排流程、A/S 绑定及必要的推进和恢复规则统一维护在所属 `SKILL.md`，不另设 `keel-dev-orchestration.md` 一类独立编排文件。可引用场景 Spec、模板和可执行脚本；共享脚本提供机制，`SKILL.md` 只说明必要调用及结果衔接，不展开脚本内部实现，不以外部引用代替流程主线。
6. A/S 可以独立替换，O 核对能力、引用和交付接口。缺资料、规范冲突或超出授权时说明原因，不能静默回退或扩大任务。
7. 重组文件时保留原有目标、质量要求和门禁；同步调用方、部署、模板、校验与测试。体量统计区分主会话编排、Agent 固定输入和动态任务资料，不把搬文件当成上下文节省。

### 方案从简设计

- **只设计本期必要改动**：沿用现有架构与能力，不顺带重做整个功能，不为未来需求增加抽象或配置。
- **变化点讲清楚**：写明新增或修改的条件、状态、数据和行为；未改动部分只说明沿用哪些已有步骤及依据。
- **图表按变化展开**：时序图可合并未改动步骤，但保留受影响的前置条件、重要分支、事务边界、异常补偿与联动；不能用“其他逻辑不变”代替关键设计。
- **明确本期不涉及的内容**：MD 保留固定章节，无模型或接口变化时标注“本期不涉及变更，沿用现有实现”；HTML 省略无变更的可选栏目；按共用粒度判定业务流程有变化时必须有总览，无变化可省略。
- **先核实影响再标注**：新增状态可能改变接口枚举、数据库约束或失败重试逻辑；未新增接口/字段不等于没有契约或 SQL 变化。引用本次其他功能的共享设计仍属于本期涉及。

### 共用业务流程粒度

`common/refs/keel-business-flow-spec.md` 由 Plan 和开发编排分别下发给 Planner、CallChain。一个流程围绕独立业务目标，从业务触发到明确结果；节点按业务阶段或决策划分，HTTP/RPC、MQ 消费、定时任务和回调是技术触发点，不能直接当作业务节点或按入口数量分文件。

比较当前与目标流程时使用同一粒度：触发场景、结果类型、阶段、先后关系、业务分支或责任交接变化，才算业务流程变化。内部实现、规则细节或状态表达变化，若业务阶段与路径不变，则总览可省略；需要用户查看整体流程时仍可提供。

CallChain 仍按原维护条件检查入口、异步推进、状态及流转变化，记录真正的状态变更位置；省略 Plan 总览不等于跳过索引维护。普通内部调用栈不展开，两个角色共用粒度，但 Plan 设计本次目标流程，CallChain 记录验收后代码实际具备的流程，各自职责和门禁不变。

Plan 与 Fix 的改造点共用 `common/refs/keel-code-change-spec.md`：按真实类、模块或文件列出一句话改动，避免展开方法、行号和测试细节。Plan 起草/修订时下发给 Planner，Fix 编写/修订说明时由主会话加载，执行者依目标和调查依据自主定位。

### 职责与文件归属

各职责的文件归属如下：

| 工作 | A | S | O |
| --- | --- | --- | --- |
| 方案设计 | Planner | 方案编写 + 通用工作 + 业务流程/改造点表达 | keel-plan 的 SKILL.md：调研、决策沟通、起草/修订、渲染与最终确认 |
| 开发 | Builder | 代码实施 + 通用工作 + 代码与测试质量 | keel-dev 的 SKILL.md：初始化、实现、验收、返修与交付 |
| 验收 | QA | 交付验收 + 通用工作 + 同一代码与测试质量 | 所属 keel-dev 或 keel-fix 的 SKILL.md |
| 流程维护 | CallChain | 流程文档维护 + 通用工作 + 业务流程表达 | keel-dev 的 SKILL.md：判断是否需要维护、调度与结果处理 |
| 局部缺陷修复 | Builder、QA | 按步选择调查/实施/验收规范 + 局部修复边界；说明编写另用修复说明与改造点表达 | keel-fix 的 SKILL.md：定位、分流、独立审阅、修复验收与现场复验 |

Plan 的主会话负责沟通和检查，调研与文档编写交给 Planner。生成的 HTML 与执行 MD 使用同一份设计内容。

### Spec 格式与引用

Spec 位于 `common/refs/`，按使用场景和共享标准分类，完整清单见 [Spec 目录](docs/specs/README.md)。每份文件开头用 YAML 声明 `name` 和 `description`：`name` 全局唯一，当前采用文件名去掉 `.md`；`description` 简述用途和使用场景。

正文直接列出简短易懂的规则，正确或错误示例按需添加并保留前缀。旧名称保留原章节和规范引用，供已有文件使用；当前 Skill 直接选择场景规范。

### Skill 与 Agent 协议

Plan、Dev、Fix 给 Agent 的业务输入只有两段：

- **任务**：本步目标、范围、必要资料引用（含项目手册）和交付要求。
- **Spec**：所选规范的 name 与绝对路径列表；`#二级标题` 引用包含子节，到下一二级标题结束。

调用层加载注册角色配置并提供项目环境，工具支持时使用独立上下文、关闭完整历史继承。Agent 依据任务与 Spec 工作，返回业务结论、产物、commits、验证证据和遗留项；QA 使用 APPROVED/REJECTED，流程维护使用 NOOP/UPDATED。

主会话选择 Agent/Spec，负责用户确认、阶段、进度与恢复；根据当前执行的新消息记录进度，核对产物、提交和证据后记录完成，再推进状态。运行字段、内部完成标记和 Skill 不下发给 Agent；Agent 不调用运行助手或修改运行状态，现有脚本也没有自动进度采集器。

开发 run 的 `state.json.aso_bindings` 按 builder/qa/call_chain 记录 agent、spec_refs；旧 task_ref 保留但忽略。恢复先结束旧执行，再启动新任务，晚到的旧进展和结果不用于新执行。审查五分钟、实现或返修十五分钟无进展时检查，轮询、重复摘要或仅 running 不重置计时。保留三轮返修、每阶段每角色两次恢复、QA 门禁、按需 CallChain、批准快照与旧 profile 恢复。

## 使用

1. 在 Codex App 运行 `/keel-plan`，生成 `.keel/plans/<name>.md` 功能索引、`<name>.features/<slug>.md` 功能文档、`<name>.review.md` 审阅素材及同名 `.html` 用户审阅入口。
2. 已确认计划统一运行 `/keel-dev <plan-path>`，由编排决定实现切片与 CallChain 调用。
3. 新提交的 BUG 直接运行 `/keel-fix <问题描述或资料路径>`；定位阶段不要求预先生成 Plan。

```text
/keel-dev <plan-path>
```

`keel-fix` 编排 Builder 根据问题、代码、配置与日志定位根因，本地复现是可选证据来源。Builder 必须区分已定位、候选原因与暂未定位；主会话根据证据缺口向用户请求必要日志或现场验证，不能把日志语句当作本次运行记录，也不能靠猜测修改代码。

定位后由主会话分流：明确、局部且不改变既定设计的缺陷走独立 fix；需求变更或涉及业务状态/流程、接口、数据模型、迁移及高风险设计的修复，说明原因并提示用户走 `/keel-plan`。证据不足继续调查，不误判为需求。fix 只编排 Builder 和 QA，不调用 Plan/Dev Skill 或 CallChain。

`.keel/bugs/<id>/bug.md` 与同名 HTML 仅简述“问题、原因、改造点、影响点、建议验证点”五章，影响和建议回归按业务流程表达。调查证据、预期依据、分流结论与设计边界保留在同目录 `investigation.md` 的“修复资格”章节，其他章节记录调查进展；HTML 不展示证据代码或重复的完整源文档，保留 Markdown 下载。

用户确认后，审批脚本核对 MD、HTML 和修复资格，保存 approved.md、approved-investigation.md 快照及独立 fix state，供 Builder/QA 执行与验收。派发、恢复及记录完成前复核批准版本；仅补充调查日志无需重新批准，资格或审阅内容实质变化须重渲染并重新确认。旧三章文档继续兼容，既有已批准任务沿用原快照与 HTML，无需迁移或重新渲染；代码验收通过后仍待原场景复验。

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py render .keel/bugs/<id>/bug.md
# 用户明确确认当前 HTML 后，才记录其确认原文：
python3 .agents/skills/keel-fix/scripts/keel-fix.py approve .keel/bugs/<id>/bug.md --decision '用户确认原文'
```

Codex App 的 Plan 编排 Planner 核对相关 CallChain 和实际代码，返回带 slug 的候选功能与证据，再由主会话让用户选择哪些功能生成 PlantUML 时序图（部分、全部或不生成）；已有明确选择时不重复询问。其余只询问必须由用户决定、且无法从需求、代码或项目惯例确定的事项，内容可推导时直接起草，不逐章确认。

Planner 按本期变化设计方案：时序图聚焦本期核心变化，仅合并保留理解改动所必需的旧步骤，直接受影响的条件、事务、异常与联动仍须表达；确实无模型/接口变更时在 MD 写“本期不涉及变更，沿用现有实现”，HTML 继续省略对应可选栏目。仅增加内部状态的完整小方案见 `keel-plan/skills/keel-plan/assets/incremental-example.md` 及关联文件。合约开发的完整示例见 `keel-plan/skills/keel-plan/assets/contract-example.md` 及关联文件。主会话检查范围与简洁程度，负责渲染和最终用户确认，不重复 Planner 的调研与文档编写。

执行文档按功能拆分。轻量索引保留各功能目标、逐项验收、依赖及文件链接；目标只说明技术上要达到的功能效果，不包含实现过程。每份功能 MD 保留数据模型、功能时序图、接口设计、代码改造点四章；涉及智能合约开发时，在数据模型之前增加合约设计，先列合约、简要说明及本期变化，再用 PlantUML 展示关系和实例基数（1:1、1:N、N:M，按需细化零或多个）。模型写实际表/列或 JSON 结构差异，SQL 按迁移需要提供；时序图写本期核心逻辑，MD 图外仅补必要执行差异，接口设计写 HTTP/RPC 请求/响应契约，改造点按共用规范列实际类、模块或文件与一句话改动。共享合约设计、模型或接口由一个功能定义，其他功能引用其对应章节，SQL 不重复执行。全部计划 MD 与 HTML 不包含开发自测内容，不列测试文件、用例、命令、操作步骤、验证安排或记录；验收标准仅保留可观察的功能结果，Builder 与 QA 按开发规范自行组织测试。Builder 读索引后仅加载当前功能和必要引用章节；QA 按功能逐份验收。

HTML 按背景、功能目标、业务流程总览、按需状态机、按需合约设计、按需数据模型设计、选定时序图、按需 HTTP/RPC 接口设计、代码改造点展示。背景仅展示理解后的 User Story 列表，不按功能分类；功能目标单独展示技术上需要达到的效果，验收标准逐条列出，不混入 HTTP 契约或事务等实现细节。业务流程总览按共用粒度有变化时必需，无变化可省略；审阅素材标题下记录业务流程变化判定和依据，渲染器拒绝有变化却缺总览的文档。总览参考流程索引并核对现状，以 PlantUML 展示本次方案完成后的目标业务阶段、关键分支和结果，标明新增/修改并简述沿用部分；全新业务也要画出目标流程，不能只展示当前缺少能力。判定字段不另展示为 HTML 栏目。流程图和状态图前只标业务流程或实体名称，如“订单取消流程”“订单状态机”，不另加图表复述、图例解说或设计历史。新增实际表/列时展示 ER 图，JSON 结构调整展示精简字段差异；仅索引、既有字段或数据回填的 SQL 仍保留在执行 MD。时序图栏目只展示功能标题和已选图，不附图外实现文字。接口设计按 HTTP 方法与路径或 RPC 签名组织，不包含功能编号和功能名称。有状态调整时用绿/蓝/红区分新增/修改/删除，删除节点隔离展示。不增加技术约束、实施顺序、验证方案或“其他必要说明”章节。

HTML 从索引、功能文档和审阅素材共同生成，目标、验收、合约设计、模型、时序图、接口及改造点直接复用执行文档；审阅素材只补充 User Stories、本次目标业务流程和状态图。下载文档包包含索引和全部功能 MD，保留相对链接，不重新合并成大 MD。用户反馈修改对应源文件后重新生成 HTML；未选画图的功能仍可保留文字执行说明。Dev 初始化将索引与关联文档一起快照到 run，后续按需读取该快照。旧格式须重新运行 Plan；最终 HTML 未确认或渲染失败时不能进入 Dev。

渲染依赖 Python 3 和本地 `plantuml` 命令，或通过 `KEEL_PLANTUML_JAR` 指定本地 jar 并提供 Java。图表使用 PlantUML 内置布局，无需 Graphviz；渲染后嵌入 HTML，可离线打开，不向远程服务发送计划。页面默认深色，可在顶部切换浅色，并在浏览器存储可用时记住选择；打印使用浅色。缺少审阅素材、依赖或图语法错误会明确失败并保留旧 HTML。命令行为参考 [PlantUML CLI](https://plantuml.com/command-line)。

```bash
bash .agents/skills/keel-plan/scripts/render-plan-html.sh .keel/plans/example.md .keel/plans/example.html
```

开发只保留 `/keel-dev` 一个入口。小任务一次实现并创建聚焦提交，大任务按依赖分片；两者使用相同的 Builder、QA 和质量规范。QA 通过后按实际改动决定是否需要 CallChain，不按任务大小或是否展示业务总览直接跳过。

```text
/keel-dev <plan-path>
```

Codex App 的 dev run 在 Preflight 后直接由 Builder 按 Markdown 计划构建，再由 QA 验收，最后按需维护 CallChain。局部调整与复杂业务流程、数据库迁移、权限、事务/并发、跨模块状态流转都由此入口执行。Codex App 不再生成或审查 build-scope；方案和边界必须在 Plan 阶段完成确认。


CallChain 已启用按需调度：主会话明确判断没有外部入口、异步推进点、业务状态节点、流转条件或状态变更符号变化时记录 `noop` 并跳过 Agent；存在变化或不确定时记录 `run` 并保持独立 CallChain 评审。受控评测结果使用 `scripts/check-call-chain-controlled-eval.sh` 复核。

CallChain 在业务流程文件中维护当前 PlantUML 状态图与流转表，记录源/目标状态、事件、条件、业务入口符号和实际状态变更符号及代码路径。图表以验收后的实现为准，历史差异交由 git 保存。

本轮评审发现阻断问题时自动进入内部修复循环，最多三轮。run 完成后的新反馈使用新的 plan/dev run；范围变化重新运行 `/keel-plan`。

run 目录最小结构:

```text
.keel/iterations/<branch>/run-N/
  plan.md                    # 功能目标与文档索引
  <name>.features/            # 各功能的设计 MD
  state.json
  qa-feedback.md
  fix-brief.md
  call-chain-review.md        # 实际调用 CallChain 时才生成
  progress.tsv
```

旧 `keel-dev-fast` 已合并；重新部署会按 manifest 清理其旧 Skill 文件，不删除未被跟踪的用户文件。运行数据的 `mode: full` 保留为兼容值，不再代表多个开发入口。

恢复未完成的旧 fast run 时，先结束旧执行并调用 `resume_keel_run`，核对已有提交、报告和历史完成标记后续作。转换保留计划快照、Preflight、返修/恢复次数、用户规范绑定及进度，不重置执行记录；已完成的旧任务保持原样。旧 `profile.json` 配置的进度文件仍可使用。

新 run 的静态契约和运行状态统一保存在 `state.json`，其中 `plan_path` 指向 run 内功能索引；主会话将当前 Agent 执行的新进展和经核验的完成结果追加到 `progress.tsv`。旧格式（包括单份大 MD）的 run 不兼容本流程，需要重新运行 `/keel-plan` 并新建 run；不自动拼接历史输入。

## 开发与验证

常用验证命令:

```bash
bash -n bin/keel
find common -type f -name '*.sh' -exec bash -n {} \;
bash -n keel-plan/skills/keel-plan/scripts/render-plan-html.sh
scripts/check-runtime-contract.sh
scripts/check-planning-contract.sh
# check-runtime-contract 已包含 ASO 边界、部署和运行协议验证
scripts/keel-metrics.sh
scripts/check-slimming-targets.sh
scripts/check-call-chain-controlled-eval.sh
scripts/summarize-call-chain-shadow.sh --help
tmp=$(mktemp -d)
bin/keel dev --codex "$tmp"
find "$tmp/.agents/skills" "$tmp/.codex" -maxdepth 4 -type f | sort
rm -rf "$tmp"
git status --short
```

对 `bin/keel` 做端到端测试时,目标目录必须用 `mktemp -d` 创建,测试结束后清理,避免污染真实项目。

输入体量按 Agent 实际加载的角色配置和场景 Spec 统计；动态任务、项目资料和真实模型用量由行为评估记录，见 [评估说明](evals/keel/README.md)。

## 部署行为

- Codex skills 部署到 `.agents/skills/`
- Codex agents 部署到 `.codex/agents/`
- Codex common 部署到 `.codex/common/`
- Codex manifest 写入 `.codex/.keel/installed-manifest`
- 同名文件直接覆盖
- 只删除当前 runtime 上次由 manifest 记录、但本次源里已不存在的旧文件

## 安全

- Keel 不会自动 merge、squash、push 或清理 Builder commits。
- Deployment 会覆盖目标项目中的同名 Keel 文件。
