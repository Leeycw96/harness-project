# Claude Code Runtime Design

> 历史设计记录：当前仅维护 Codex App runtime，部署和验证方式以根目录 README.md 为准。


Date: 2026-06-26

## Background

当前 Keel v2 只维护 Codex App runtime。`bin/keel` 默认部署根级
`common/`、`keel-plan/` 和 `keel-dev/` 到 Codex App 项目:

- skills -> `.agents/skills/`
- agents -> `.codex/agents/`
- common helpers -> `.codex/common/`
- manifest -> `.codex/.keel/installed-manifest`

现有 Codex 版使用 Codex App subagents、`.codex/agents/*.toml`、角色说明
Markdown 和 SOP Markdown 组成的三件套。用户现在需要一套专为 Claude Code
CLI 使用的 Keel plan/dev,并且不能影响现有 Codex 版。

Claude Code 当前项目级约定是:

- skills: `.claude/skills/<name>/SKILL.md`
- agents: `.claude/agents/<agent>.md`
- agent 文件是带 YAML frontmatter 的单个 Markdown 文件

本设计选择独立 Claude Code runtime 源码树,不恢复旧 tmux/pane runtime,也不把
Codex agent TOML 动态转换逻辑塞进部署脚本。

## Goals

- 新增完整 Claude Code 版 `/keel-plan`、`/keel-dev-fast`、
  `/keel-dev` 和 `/keel-dev-fix`。
- 支持显式 runtime 安装:
  `keel dev --codex` 和 `keel dev --claude-code`。
- 默认安装到当前目录,可在 runtime 参数后传入目标目录。
- 保持 Codex App 现有 skill/agent 语义不变。
- 保持 full/fast/fix 的 run 目录、profile/state 和 artifact 契约一致。
- 使用 Claude Code 原生 `.claude/skills` 和 `.claude/agents` 文件格式。

## Non-Goals

- 不恢复旧 Claude Code tmux、pane、send-keys 或 agent 间互聊流程。
- 不恢复 `--codex-cli` runtime。
- 不引入模板生成器或复杂部署期转换系统。
- 不在真实业务项目中跑端到端 Keel 构建验证。
- 不自动 merge、squash、push 或清理 Builder commits。

## Source Layout

保留现有 Codex 源码树:

```text
common/
keel-plan/
keel-dev/
```

新增 Claude Code 源码树:

```text
claude-code/
  common/
    refs/
    scripts/
  keel-plan/
    skills/keel-plan/
  keel-dev/
    skills/
      keel-dev/
      keel-dev-fast/
      keel-dev-fix/
    agents/
      keel-builder.md
      keel-qa.md
      keel-code-review.md
      keel-call-chain.md
      keel-feedback-triage.md
```

Codex 版仍从根级目录部署。Claude Code 版只从 `claude-code/` 部署。两套
runtime 的源码、目标目录和 manifest 互相隔离。

## CLI Design

唯一推荐格式:

```bash
keel dev --codex
keel dev --claude-code
keel dev --codex /path/to/project
keel dev --claude-code /path/to/project
```

规则:

- `keel dev` 不再默认安装,必须显式选择 `--codex` 或
  `--claude-code`。
- runtime 参数只能出现在 mode 后面,让用户入口保持简单。
- `target-dir` 可选,未提供时为当前目录。
- 不支持 `--runtime`、`--codex-cli` 或 runtime 参数放在 mode 前面的旧格式；
  旧参数应给出明确错误和迁移提示。
- `dev` 模式部署时仍自动包含 `keel-plan`。

部署目标:

```text
--codex:
  .agents/skills/
  .codex/agents/
  .codex/common/
  .codex/.keel/installed-manifest

--claude-code:
  .claude/skills/
  .claude/agents/
  .claude/common/
  .claude/.keel/installed-manifest
```

manifest 清理只处理当前 runtime 上一次记录过的文件,不得跨 `.codex` 和
`.claude` 删除文件。

## Claude Skills

Claude Code 版安装以下 skills:

```text
.claude/skills/keel-plan/SKILL.md
.claude/skills/keel-dev/SKILL.md
.claude/skills/keel-dev-fast/SKILL.md
.claude/skills/keel-dev-fix/SKILL.md
```

`/keel-plan` 保持 Codex 版等价流程:

- 读取项目上下文
- 一次一个问题澄清需求
- 确认本次边界、交互依赖和 out of scope
- 拆分 feature slug
- 定义具体可测验收标准
- 写入 `.keel/plans/<name>.md` XML plan

Claude 版模板路径改为:

```bash
cat .claude/skills/keel-plan/assets/plan-template.xml
```

dev 三个入口保持现有阶段和门禁:

- full: Scope Build -> Scope Review -> Build -> Parallel Review -> Fix ->
  CallChain -> Done
- fast: Build Fast -> Code Review Fast -> Fix Fast -> Done
- fix: Feedback Triage -> Post Review Fix -> Parallel Review -> CallChain

Claude 版技能说明里的 runtime 文案应改为 Claude Code subagents,并移除 Codex
专属 `close_agent` API 名称。生命周期要求表达为:每次 Claude agent invocation
只执行一个阶段,完成 artifact、调用 `complete_stage` 后停止并返回主会话。

## Claude Agents

Claude Code 版 agent 使用单文件 Markdown:

```markdown
---
name: keel-builder
description: Keel dev Builder. Use when the keel-dev orchestrator asks for SCOPE_BUILD, BUILD, BUILD_FAST, FIX, or FIX_FAST stages.
tools: Read, Write, Edit, Glob, Grep, Bash
model: inherit
---

# keel-builder
...
```

`model: inherit` 表示跟随当前 Claude Code 会话模型,避免 Keel 硬编码模型。

需要生成的 agents:

- `keel-builder`
- `keel-qa`
- `keel-code-review`
- `keel-call-chain`
- `keel-feedback-triage`

每个 Claude agent 文件由当前 Codex 的三类内容合并而来:

- `.toml` 中的 name/description/developer instructions
- 角色说明 `.md`
- SOP `*-AGENTS.md`

路径替换:

- `.codex/agents/...` -> `.claude/agents/...`
- `.codex/common/...` -> `.claude/common/...`

agent 间仍不直接通信。主会话是唯一 orchestrator,负责分发阶段、读取返回结果、
校验 artifact、更新 `state.json` 和决定下一阶段。

## Common Scripts And State

`claude-code/common/scripts/` 从当前 `common/scripts/` 派生。核心磁盘状态机不变,
只改 runtime 字段和路径:

- `runtime: "claude-code"`
- 默认 profile 路径使用 `.claude/common` 对应逻辑
- agent profile 从 Codex 三件套改为 Claude 单文件:

```json
{
  "agent_doc": ".claude/agents/keel-builder.md"
}
```

保留初始化函数:

```bash
init_keel_run
init_keel_fast_run
init_keel_fix_run
```

`keel-common.sh` 保留:

- `update_progress`
- `complete_stage`
- `validate_artifact`
- phase/state helper

run 目录继续使用:

```text
.keel/iterations/<branch>/run-N/
  plan.md
  profile.json
  state.json
  build-scope.md
  scope-review.md
  qa-feedback.md
  code-review.md
  fix-brief.md
  call-chain-review.md
  progress/
```

fast run 和 post-review fix run 保持当前最小 artifact 集合,以便两套 runtime
排查方式一致。

## Documentation Updates

更新:

- `README.md`: 双 runtime 介绍、安装命令、部署目录、使用入口和验证命令。
- `AGENTS.md`: 项目结构、测试命令和 deployment 行为改为双 runtime。
- `CLAUDE.md`: 不再声明不维护 `.claude/` runtime;改为说明 Claude Code runtime
  源码位于 `claude-code/`。

文档保持当前中文说明风格。commit 使用短中文 imperative。

## Validation

只做部署和脚本级验证:

```bash
bash -n bin/keel
find common claude-code/common -type f -name '*.sh' -exec bash -n {} \;

tmp=$(mktemp -d)
bin/keel dev --codex "$tmp"
bin/keel dev --claude-code "$tmp"

find "$tmp/.agents/skills" "$tmp/.codex" "$tmp/.claude" -maxdepth 4 -type f | sort
rm -rf "$tmp"
git status --short
```

关键存在性检查:

- Codex: `.agents/skills/keel-plan`, `.agents/skills/keel-dev-fast`,
  `.codex/agents/*.toml`, `.codex/common/scripts/*`
- Claude: `.claude/skills/keel-plan`, `.claude/skills/keel-dev-fast`,
  `.claude/agents/keel-builder.md`, `.claude/common/scripts/*`

## Risks And Mitigations

- 风险: Claude agent 合并文档时出现行为漂移。
  缓解: 以机械合并和路径替换为主,不重写阶段职责和门禁。
- 风险: CLI 恢复多种参数顺序导致复杂度回升。
  缓解: 只支持 `keel <mode> (--codex|--claude-code) [target-dir]` 形态。
- 风险: manifest 清理误删另一 runtime 文件。
  缓解: Codex 和 Claude manifest 分别位于 `.codex/.keel/` 和
  `.claude/.keel/`,清理只基于当前 manifest。
- 风险: 未来两套 runtime 文档同步成本增加。
  缓解: 当前优先隔离稳定性;后续如重复维护成本明显,再单独设计模板层。

## Approval

用户已确认:

- 采用独立 `claude-code/` runtime 源码树。
- CLI 使用 `keel dev --codex` 或 `keel dev --claude-code`。
- 默认安装到当前目录,目标目录可选。
- Claude 版覆盖 plan、dev、dev-fast 和 dev-fix 四个入口。
- 设计文档先提交,随后再进入 implementation plan。
