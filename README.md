# Keel

当前版本: **4.0.0**（见 `VERSION`）。

命令入口为 `keel`，开发模式为 `dev`，计划与运行数据使用 `.keel/`。本次更名直接使用新名称，不提供旧命令别名或自动迁移。

Keel 是一组面向 Codex App 的 skills + agent 手册，用于编排 Builder、QA 和 CallChain，完成从业务理解到代码交付的开发工作流。

## 目录结构

```text
keel-project/
├── bin/keel          # 部署 CLI
├── install.sh        # 把 bin/ 写入 PATH
├── common/           # 共享规则和脚本，部署到 .codex/common/
├── keel-plan/        # /keel-plan skill、模板与渲染入口
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

`keel dev` 会同时部署 `/keel-plan`、`/keel-dev-fast` 和 `/keel-dev`。

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
    └── keel-dev-fast/
.codex/
├── common/
│   ├── refs/
│   └── scripts/
├── agents/
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

借鉴 [Karpathy 启发的四项原则](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/README.zh.md)，按 Keel 阶段职责整合：Plan 在制定计划时核实假设、调研歧义并请用户完成关键取舍；Dev 和 fast 按已确认方案落实简洁优先、精准修改与目标驱动，Builder 实现，QA 对照目标与证据验收。仅实际代码偏差或关键遗漏返回 Plan，验证修复仍遵守既有次数上限。

## 使用

1. 在 Codex App 运行 `/keel-plan`，生成 `.keel/plans/<name>.md` 功能索引、`<name>.features/<slug>.md` 功能文档、`<name>.review.md` 审阅素材及同名 `.html` 用户审阅入口。
2. 日常小中型改动优先运行 `/keel-dev-fast <plan-path>`。
3. 高风险改动再运行 `/keel-dev <plan-path>` 走完整验收。

```text
/keel-dev-fast <plan-path>
```

Codex App 的 Plan 先读取相关 CallChain 和实际代码，列出带 slug 的功能目标，再让用户选择哪些功能生成 PlantUML 时序图（部分、全部或不生成）；已有明确选择时不重复询问。其余只询问必须由用户决定、且无法从需求、代码或项目惯例确定的事项，内容可推导时直接起草，不逐章确认。

执行文档按功能拆分。轻量索引保留各功能目标、逐项验收、依赖及文件链接；目标只说明技术上要达到的功能效果，不包含实现过程。每份功能 MD 固定包含数据模型、功能时序图、接口设计、代码改造点：模型写表结构和 SQL，时序图写重点逻辑，接口设计写请求/响应契约，改造点只定位文件与符号并用一句话描述改动。共享模型/接口由一个功能定义，其他功能引用其对应章节，SQL 不重复执行。Builder 读索引后仅加载当前功能和必要引用章节；QA 按功能逐份验收。

HTML 按背景、功能目标、业务流程总览、按需状态机、按需数据模型设计、选定时序图、按需 HTTP/RPC 接口设计、代码改造点展示。背景仅展示理解后的 User Story 列表，不按功能分类；功能目标单独展示技术上需要达到的效果，验收标准逐条列出，不混入 HTTP 契约或事务等实现细节。业务流程总览必选，参考 CallChain 并核对代码，以 PlantUML 展示当前关键环节。新增表或字段才展示 ER 图，只列本次相关表、关系和关键字段；仅索引、既有字段或数据回填的 SQL 仍保留在执行 MD。接口设计按 HTTP 方法与路径或 RPC 签名组织，不包含功能编号和功能名称。有状态调整时用绿/蓝/红区分新增/修改/删除，删除节点隔离展示。不增加技术约束、实施顺序、验证方案或“其他必要说明”章节。

HTML 从索引、功能文档和审阅素材共同生成，目标、验收、模型、时序图、接口及改造点直接复用执行文档；审阅素材只补充 User Stories、当前流程和状态图。下载文档包包含索引和全部功能 MD，保留相对链接，不重新合并成大 MD。用户反馈修改对应源文件后重新生成 HTML；未选画图的功能仍可保留文字执行说明。Dev 初始化将索引与关联文档一起快照到 run，后续按需读取该快照。旧格式须重新运行 Plan；最终 HTML 未确认或渲染失败时不能进入 Dev。

渲染依赖 Python 3 和本地 `plantuml` 命令，或通过 `KEEL_PLANTUML_JAR` 指定本地 jar 并提供 Java。图表使用 PlantUML 内置布局，无需 Graphviz；渲染后嵌入 HTML，可离线打开，不向远程服务发送计划。页面默认深色，可在顶部切换浅色，并在浏览器存储可用时记住选择；打印使用浅色。缺少审阅素材、依赖或图语法错误会明确失败并保留旧 HTML。命令行为参考 [PlantUML CLI](https://plantuml.com/command-line)。

```bash
bash .agents/skills/keel-plan/scripts/render-plan-html.sh .keel/plans/example.md .keel/plans/example.html
```

Codex App 的 fast run 只调度 Builder 和 QA，不运行 CallChain，适合小范围 bugfix、局部逻辑调整、简单校验或错误处理。Builder 与 QA 按需读取同一组已确认的功能文档。涉及业务状态节点、流转条件或状态变化入口调整时使用 full，让 CallChain 更新状态机。

```text
/keel-dev <plan-path>
```

Codex App 的 dev run 在 Preflight 后直接由 Builder 按 Markdown 计划构建，再由 QA 验收，最后按需维护 CallChain。复杂业务流程、数据库迁移、权限审计、事务/并发、跨模块状态流转等高风险改动使用它。Codex App 不再生成或审查 build-scope；方案和边界必须在 Plan 阶段完成确认。


CallChain 已启用按需调度：主会话明确判断没有外部入口、异步推进点、业务状态节点、流转条件或状态变更符号变化时记录 `noop` 并跳过 Agent；存在变化或不确定时记录 `run` 并保持独立 CallChain 评审。受控评测结果使用 `scripts/check-call-chain-controlled-eval.sh` 复核。

CallChain 在业务流程文件中维护当前 PlantUML 状态图与流转表，记录源/目标状态、事件、条件、业务入口符号和实际状态变更符号及代码路径。图表以验收后的实现为准，历史差异交由 git 保存。

full 和 fast 都会在本轮评审发现阻断问题时自动进入内部修复循环。run 完成后的新反馈使用新的 plan/dev run；范围变化重新运行 `/keel-plan`。

run 目录最小结构:

```text
.keel/iterations/<branch>/run-N/
  plan.md                    # 功能目标与文档索引
  <name>.features/            # 各功能的设计 MD
  state.json
  qa-feedback.md
  fix-brief.md
  call-chain-review.md
  progress.tsv
```

fast run 最小结构:

```text
.keel/iterations/<branch>/run-N/
  plan.md                    # 功能目标与文档索引
  <name>.features/            # 各功能的设计 MD
  state.json
  qa-feedback.md
  fix-brief.md
  progress.tsv
```

新 run 的静态契约和运行状态统一保存在 `state.json`，其中 `plan_path` 指向 run 内功能索引；所有 Agent 心跳追加到 `progress.tsv`。旧格式（包括单份大 MD）的 run 不兼容本流程，需要重新运行 `/keel-plan` 并新建 run；不自动拼接历史输入。

## 开发与验证

常用验证命令:

```bash
bash -n bin/keel
find common -type f -name '*.sh' -exec bash -n {} \;
bash -n keel-plan/skills/keel-plan/scripts/render-plan-html.sh
scripts/check-runtime-contract.sh
scripts/check-planning-contract.sh
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
