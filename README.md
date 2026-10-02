# Keel

当前版本: **4.0.0**（见 `VERSION`）。

命令入口为 `keel`，开发模式为 `dev`，计划与运行数据使用 `.keel/`。本次更名直接使用新名称，不提供旧命令别名或自动迁移。

Keel 是一组面向 Codex App 的 skills + agent 手册，用于编排 Planner、Builder、QA 和 CallChain，完成从业务理解到代码交付的开发工作流。

## 目录结构

```text
keel-project/
├── bin/keel          # 部署 CLI
├── install.sh        # 把 bin/ 写入 PATH
├── common/           # 共享规范、编排和脚本，部署到 .codex/common/
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
│   │   ├── keel-business-flow-spec.md # S：共用业务流程粒度
│   │   ├── keel-plan-spec.md          # S：方案格式、范围与图表规范
│   │   ├── keel-dev-spec.md           # S：开发约束及代码与测试标准
│   │   ├── keel-qa-spec.md            # S：验收约束
│   │   ├── keel-call-chain-spec.md    # S：流程文档规范
│   │   └── keel-dev-orchestration.md  # O：调度与任务执行要求
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

本项目按 **Agent、Spec、Orchestration** 组织能力。新增或调整 Plan、Dev、Fix 等流程时，先确定内容属于哪一层；职责分离不要求每条规则都拆一个文件。

| 层次 | 应包含 | 不应包含 |
| --- | --- | --- |
| **A（Agent）** | 角色、能力、原则：专业职责、擅长的工作、稳定的判断方式 | 固定项目规范路径、阶段步骤、状态字段、重试次数、完成命令 |
| **S（Spec）** | 项目或职责规范：操作边界、工程标准及其适用条件、必需产物、文档格式、图表表达和验收要求 | 调度哪个 Agent、什么时候问用户、阶段推进与恢复 |
| **O（Orchestration）** | 任务编排：选择 A/S，组织核实适用条件，提供目标与资料，应用标准并组织用户决策、产出、检查、交接与恢复 | 重写 Agent 的角色原则，重复维护 Spec 中的标准 |

### 编写与调整要求

1. Agent Markdown 固定为“角色、能力、原则”。原则用能直接指导行动的句子，如最小修改、不过度设计、先看已有实现、定位不出来就明说；TOML 只做必要注册并加载角色说明。
2. Spec 按职责组织，定义产物完整性与质量标准，也可规定标准的适用条件和必需产物；例如“涉及合约开发的方案必须包含合约清单和关系图”。条件属于哪层取决于约束对象：产物要求属于 S，任务调度和阶段控制属于 O。共享标准保持一个来源，通过编排下发引用；例如 QA 与 Builder 使用同一份代码和测试标准。Spec 是长期工作规范，本次需求与修复目标放在任务资料中。
3. 编排显式提供角色、Spec、任务说明、资料与输出范围，组织调研核实适用条件，按所选 Spec 落实必需内容并检查交付，不另维护一套产物标准。Agent 根据注入的规范执行，不自行寻找固定规约或承担主会话调度。子 Agent 提交待决问题，主会话向用户询问，已有明确决定不重复确认。
4. A/S 可以独立替换，O 核对能力、引用和交付接口。缺资料、规范冲突或超出授权时说明原因，不能静默回退或扩大任务。
5. 重组文件时保留原有目标、质量要求和门禁；同步调用方、部署、模板、校验与测试。统计完整任务实际读取的内容，不把搬文件当成上下文节省。

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

### 当前职责映射

| 工作 | A | S | O |
| --- | --- | --- | --- |
| 方案设计 | Planner | keel-plan-spec.md + 共用业务流程粒度 | keel-plan：调研、决策沟通、起草/修订、渲染与最终确认 |
| 开发 | Builder | keel-dev-spec.md | keel-dev 与共享开发编排 |
| 验收 | QA | keel-qa-spec.md + 本次开发质量标准 | 所属开发或修复编排 |
| 流程维护 | CallChain | keel-call-chain-spec.md + 共用业务流程粒度 | 开发编排按需调度 |
| 局部缺陷修复 | Builder、QA | 对应职责 Spec | keel-fix：定位、分流、独立审阅与修复验收 |

Spec 位于 `common/refs/`，各编排按职责下发文件或 `#二级标题` 引用。Plan 的主会话负责沟通和检查，调研与文档编写交给 Planner，避免重复工作。生成的 HTML 与执行 MD 使用同一份设计内容，不独立编造另一份方案。

开发 run 在 `state.json.aso_bindings` 中按 builder/qa/call_chain 记录 agent、spec_refs 和 task_ref；引用使用绝对路径，章节包含其子节，到下一二级标题结束。恢复沿用当前 run 的绑定并补全缺失职责。统一使用 BUILD、REVIEW、FIX、REVIEW_FIX，保留三轮修复上限、QA 门禁、按需 CallChain 和旧 profile 恢复。

## 使用

1. 在 Codex App 运行 `/keel-plan`，生成 `.keel/plans/<name>.md` 功能索引、`<name>.features/<slug>.md` 功能文档、`<name>.review.md` 审阅素材及同名 `.html` 用户审阅入口。
2. 已确认计划统一运行 `/keel-dev <plan-path>`，由编排决定实现切片与 CallChain 调用。
3. 新提交的 BUG 直接运行 `/keel-fix <问题描述或资料路径>`；定位阶段不要求预先生成 Plan。

```text
/keel-dev <plan-path>
```

`keel-fix` 编排 Builder 根据问题、代码、配置与日志定位根因，本地复现是可选证据来源。Builder 必须区分已定位、候选原因与暂未定位；主会话根据证据缺口向用户请求必要日志或现场验证，不能把日志语句当作本次运行记录，也不能靠猜测修改代码。

定位后由主会话分流：明确、局部且不改变既定设计的缺陷走独立 fix；需求变更或涉及业务状态/流程、接口、数据模型、迁移及高风险设计的修复，说明原因并提示用户走 `/keel-plan`。证据不足继续调查，不误判为需求。fix 只编排 Builder 和 QA，不调用 Plan/Dev Skill 或 CallChain。

`.keel/bugs/<id>/investigation.md` 记录调查过程，`bug.md` 仅保存“问题与根因、修复方案、影响与验证”三章。独立渲染脚本从该 MD 生成同名 HTML，复用现有明暗主题，无需完整 Plan。每个 BUG 经用户确认后，审批助手核对 MD/HTML、保存不可覆盖的 approved.md 快照和 fix state；派发与恢复先检查版本，修改方案须重新审阅确认。代码验收通过后仍待测试复验。

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py render .keel/bugs/<id>/bug.md
# 用户明确确认当前 HTML 后，才记录其确认原文：
python3 .agents/skills/keel-fix/scripts/keel-fix.py approve .keel/bugs/<id>/bug.md --decision '用户确认原文'
```

Codex App 的 Plan 编排 Planner 核对相关 CallChain 和实际代码，返回带 slug 的候选功能与证据，再由主会话让用户选择哪些功能生成 PlantUML 时序图（部分、全部或不生成）；已有明确选择时不重复询问。其余只询问必须由用户决定、且无法从需求、代码或项目惯例确定的事项，内容可推导时直接起草，不逐章确认。

Planner 按本期变化设计方案：未改动步骤在时序图中合并简述，关键条件、事务、异常与联动仍须保留；确实无模型/接口变更时在 MD 写“本期不涉及变更，沿用现有实现”，HTML 继续省略对应可选栏目。仅增加内部状态的完整小方案见 `keel-plan/skills/keel-plan/assets/incremental-example.md` 及关联文件。合约开发的完整示例见 `keel-plan/skills/keel-plan/assets/contract-example.md` 及关联文件。主会话检查范围与简洁程度，负责渲染和最终用户确认，不重复 Planner 的调研与文档编写。

执行文档按功能拆分。轻量索引保留各功能目标、逐项验收、依赖及文件链接；目标只说明技术上要达到的功能效果，不包含实现过程。每份功能 MD 保留数据模型、功能时序图、接口设计、代码改造点四章；涉及智能合约开发时，在数据模型之前增加合约设计，先列合约、简要说明及本期变化，再用 PlantUML 展示关系和实例基数（1:1、1:N、N:M，按需细化零或多个）。模型写数据库表结构和 SQL，时序图写重点逻辑，接口设计写 HTTP/RPC 请求/响应契约，改造点只定位文件与符号并用一句话描述改动。共享合约设计、模型或接口由一个功能定义，其他功能引用其对应章节，SQL 不重复执行。全部计划 MD 与 HTML 不包含开发自测内容，不列测试文件、用例、命令、操作步骤、验证安排或记录；验收标准仅保留可观察的功能结果，Builder 与 QA 按开发规范自行组织测试。Builder 读索引后仅加载当前功能和必要引用章节；QA 按功能逐份验收。

HTML 按背景、功能目标、业务流程总览、按需状态机、按需合约设计、按需数据模型设计、选定时序图、按需 HTTP/RPC 接口设计、代码改造点展示。背景仅展示理解后的 User Story 列表，不按功能分类；功能目标单独展示技术上需要达到的效果，验收标准逐条列出，不混入 HTTP 契约或事务等实现细节。业务流程总览按共用粒度有变化时必需，无变化可省略；审阅素材标题下记录业务流程变化判定和依据，渲染器拒绝有变化却缺总览的文档。总览参考流程索引并核对现状，以 PlantUML 展示本次方案完成后的目标业务阶段、关键分支和结果，标明新增/修改并简述沿用部分；全新业务也要画出目标流程，不能只展示当前缺少能力。判定字段不另展示为 HTML 栏目。流程图和状态图前只标业务流程或实体名称，如“订单取消流程”“订单状态机”，不另加图表复述、图例解说或设计历史。新增表或字段才展示 ER 图，只列本次相关表、关系和关键字段；仅索引、既有字段或数据回填的 SQL 仍保留在执行 MD。接口设计按 HTTP 方法与路径或 RPC 签名组织，不包含功能编号和功能名称。有状态调整时用绿/蓝/红区分新增/修改/删除，删除节点隔离展示。不增加技术约束、实施顺序、验证方案或“其他必要说明”章节。

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

新 run 的静态契约和运行状态统一保存在 `state.json`，其中 `plan_path` 指向 run 内功能索引；所有 Agent 心跳追加到 `progress.tsv`。旧格式（包括单份大 MD）的 run 不兼容本流程，需要重新运行 `/keel-plan` 并新建 run；不自动拼接历史输入。

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
