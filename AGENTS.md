# Repository Guidelines

## Project Structure & Module Organization

This repository packages Harness skills, custom agent manuals, and deployment scripts for Codex App. `bin/harness` is the deployment CLI. Root-level `common/`, `harness-plan/`, and `harness-backend/` are the only supported runtime sources. Shared helpers live in `common/scripts/`. Skills live in `harness-<mode>/skills/`, and related custom agents or SOP files live in `harness-<mode>/agents/`. `claude-proxy/` is separate zsh launcher tooling.

## Build, Test, and Development Commands

- `./install.sh`: adds this repo's `bin/` directory to the shell rc file.
- `bin/harness backend "$tmpdir"`: deploys the Codex App runtime with skills in `.agents/skills/` and custom agents/common state in `.codex/`.
- `bash -n bin/harness`: checks the deployment CLI syntax.
- `find common -type f -name '*.sh' -exec bash -n {} \;`: checks shell helper syntax.
- `cd claude-proxy && ./install.sh`: regenerates Claude proxy aliases from `plans/*.json`.

There is no package-manager build step.

## Coding Style & Naming Conventions

Use Bash for scripts and keep `set -euo pipefail` on operational CLIs where practical. Quote variables, prefer local variables inside functions, and write clear stderr failures. New modes should follow `harness-<mode>/skills/harness-<mode>/` plus `harness-<mode>/agents/`. Keep Markdown instructions concise and preserve the existing Chinese instructional tone.

## Testing Guidelines

No formal test suite exists. For deployment tests, create a target with `mktemp -d`, run `bin/harness backend "$tmpdir"`, inspect `.codex/.harness/installed-manifest`, `.agents/skills/`, `.codex/agents/`, and `.codex/common/`, then remove the temp directory. Do not run end-to-end tests inside this repository or another long-lived project. Finish with `git status --short`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative Chinese summaries, often scoped, for example `bin/harness: 简化为 Codex App 单 runtime 部署` or `harness-backend: 新增 CodeReview 子智能体`. Keep commits focused. PRs should state the affected mode, list validation commands, link related plans or issues, and include screenshots only for UI or rendered-documentation changes.

## Security & Configuration Tips

Do not commit real API tokens in `claude-proxy/plans/*.json`. Deployment overwrites same-name files under `.codex/` or `.agents/skills/`, and removes obsolete files only when tracked in the Harness manifest.
