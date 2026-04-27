# Harness

Harness 是一组 Claude Code 的 skills + agents,用于多 Agent 编排。每个模式(如 `backend`)按统一的目录约定组织,通过 `harness` CLI 一键部署到目标项目。

## 目录结构

```
harness-project/
├── bin/harness                    # 部署 CLI
├── install.sh                     # 把 bin/ 写入 PATH
├── common/scripts/                # 通用脚本
│   ├── harness-init.sh            # 编排器初始化(launch_agent / wait_for_file 等)
│   └── harness-common.sh          # Agent 间通信(send_to_agent / complete_and_notify 等)
├── harness-plan/                  # 通用 plan 模块,所有模式都会自动带上
│   └── skills/harness-plan/       # /harness-plan
└── harness-backend/               # backend 模式
    ├── skills/harness-backend/    # /harness-backend
    └── agents/                    # 模式专属 agents
        ├── harness-builder.md
        └── harness-qa.md
```

## 安装 CLI

```bash
git clone <this-repo>
cd harness-project
./install.sh
source ~/.zshrc      # 或新开一个终端
```

`install.sh` 会把 `bin/` 写入你的 shell rc 文件。当前终端必须 `source` 一次或新开窗口,PATH 才会生效(shell 标准行为,无法绕过)。

## 使用

```bash
cd /path/to/your/project
harness backend
```

部署后目标项目下:

```
.claude/
├── common/scripts/                # 通用脚本
├── skills/
│   ├── harness-plan/              # 通用,自动带上
│   └── harness-backend/
└── agents/
    ├── harness-builder.md
    └── harness-qa.md
```

然后在 Claude Code 中:

- `/harness-plan` 引导式生成 plan 文件到 `.harness/plans/`
- `/harness-backend` 消费 plan 启动 builder/qa,完成构建与验收

## 模块约定

每个模式遵循统一目录布局:

```
harness-<mode>/
├── skills/harness-<mode>/         # 模式 skill,部署到 .claude/skills/
└── agents/                        # 模式专属 agents,部署到 .claude/agents/
```

新增 mode(如 `harness-solidity`)只需新建一个根目录,CLI 无需改动——`harness solidity` 会自动找到 `harness-solidity/` 并按同样规则部署。

## 部署行为

- `harness <mode>` 默认部署到当前目录,可附加目标路径:`harness backend /path/to/proj`
- 同名文件**直接覆盖**;目标项目已有的其他 skill / agent 不受影响
- 始终包含 `common/` 与 `harness-plan/`(无条件)

## Skill 说明

### harness-plan

扮演产品经理,通过对话把模糊想法逐步结构化为 XML 格式的 plan 文件,作为下游 builder/qa 的直接输入。详见 `harness-plan/skills/harness-plan/SKILL.md`。

### harness-backend

消费 `.harness/plans/<名称>.md`,驱动 builder/qa 两个 Agent 完成构建与验收闭环。详见 `harness-backend/skills/harness-backend/SKILL.md`。

## Agent 说明

- **harness-builder**:在已有后端项目中执行开发任务,产出代码与 `.harness/call-chain/` 调用链文件
- **harness-qa**:基于 plan 中的 `<acceptance-criteria>` 对实现进行验收,产出 `.harness/done` 完成标记
