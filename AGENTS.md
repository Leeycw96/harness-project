# Repository Guidelines

## Project Structure & Module Organization

This repository packages Harness skills, role manuals, and deployment scripts for AI coding CLIs. `bin/harness` is the deployment CLI. Runtime-specific sources live under `claude-code/` and `codex/`; edit these first for new work. Root-level `common/`, `harness-plan/`, `harness-backend/`, and `harness-solidity/` are retained for v1.1.x compatibility. Shared helpers are in `<runtime>/common/scripts/`. Skills live in `<runtime>/harness-<mode>/skills/`, and related agent or role SOP files live in `<runtime>/harness-<mode>/agents/`. `claude-proxy/` is separate zsh launcher tooling.

## Build, Test, and Development Commands

- `./install.sh`: adds this repo's `bin/` directory to the shell rc file.
- `bin/harness --claude-code backend "$tmpdir"`: deploys the Claude Code runtime to `.claude/`.
- `bin/harness --codex backend "$tmpdir"`: deploys the Codex runtime to `.codex/`.
- `bash -n bin/harness`: checks the deployment CLI syntax.
- `find claude-code/common codex/common common claude-proxy -type f -name '*.sh' -exec bash -n {} \;`: checks shell helper syntax.
- `cd claude-proxy && ./install.sh`: regenerates Claude proxy aliases from `plans/*.json`.

There is no package-manager build step.

## Coding Style & Naming Conventions

Use Bash for scripts and keep `set -euo pipefail` on operational CLIs where practical. Quote variables, prefer local variables inside functions, and write clear stderr failures. New modes should follow `harness-<mode>/skills/harness-<mode>/` plus `harness-<mode>/agents/`. Keep Markdown instructions concise and preserve the existing Chinese instructional tone.

## Testing Guidelines

No formal test suite exists. For deployment tests, create a target with `mktemp -d`, run both explicit deployments (`--claude-code` and `--codex`), inspect `.claude/.harness/installed-manifest` and `.codex/.harness/installed-manifest`, then remove the temp directory. Do not run end-to-end tests inside this repository or another long-lived project. Finish with `git status --short`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative Chinese summaries, often scoped, for example `bin/harness: 部署时自动安装 PostCompact hook 到目标项目` or `SKILL: 主 pane 不再 wait_for_file 阻塞`. Keep commits focused. PRs should state the affected runtime and mode, list validation commands, link related plans or issues, and include screenshots only for UI or rendered-documentation changes.

## Security & Configuration Tips

Do not commit real API tokens in `claude-proxy/plans/*.json`. Deployment overwrites same-name files under `.claude/` or `.codex/`, and removes obsolete files only when tracked in the harness manifest.
