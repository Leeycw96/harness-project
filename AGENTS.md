# Repository Guidelines

## Project Structure & Module Organization

This repository packages Harness skills, custom agent manuals, and deployment scripts for Codex App and Claude Code. `bin/harness` is the deployment CLI. Root-level `common/`, `harness-plan/`, and `harness-backend/` are the Codex App runtime sources. `claude-code/common/`, `claude-code/harness-plan/`, and `claude-code/harness-backend/` are the Claude Code runtime sources. Shared helpers live in each runtime's `common/scripts/`. Skills live in `harness-<mode>/skills/`, and related agents live in `harness-<mode>/agents/`.

## Build, Test, and Development Commands

- `./install.sh`: adds this repo's `bin/` directory to the shell rc file.
- `bin/harness backend --codex "$tmpdir"`: deploys the Codex App runtime with skills in `.agents/skills/` and custom agents/common state in `.codex/`.
- `bin/harness backend --claude-code "$tmpdir"`: deploys the Claude Code runtime with skills, agents, and common state in `.claude/`.
- `bash -n bin/harness`: checks the deployment CLI syntax.
- `find common claude-code/common -type f -name '*.sh' -exec bash -n {} \;`: checks shell helper syntax.
- `scripts/check-runtime-parity.sh`: checks normalized Skill, shared-contract, coding-rule, and Agent semantics across runtimes.
- `scripts/harness-metrics.sh`: reports current instruction and runtime size against `evals/harness/baseline-2.1.0.tsv`.
- `scripts/check-slimming-targets.sh`: enforces the approved Skill and Agent instruction-reduction targets.
- `scripts/summarize-call-chain-shadow.sh`: reports CallChain prefilter shadow results and checks the phase-two activation gate.
There is no package-manager build step.

## Coding Style & Naming Conventions

Use Bash for scripts and keep `set -euo pipefail` on operational CLIs where practical. Quote variables, prefer local variables inside functions, and write clear stderr failures. New Codex modes should follow `harness-<mode>/skills/harness-<mode>/` plus `harness-<mode>/agents/`. New Claude Code modes should follow the same layout under `claude-code/`. Keep Markdown instructions concise and preserve the existing Chinese instructional tone.

## Testing Guidelines

Behavior eval cases and hard gates live in `evals/harness/`. For deployment tests, create a target with `mktemp -d`, run `bin/harness backend --codex "$tmpdir"` and `bin/harness backend --claude-code "$tmpdir"`, inspect `.codex/.harness/installed-manifest`, `.claude/.harness/installed-manifest`, `.agents/skills/`, `.codex/agents/`, `.codex/common/`, `.claude/skills/`, `.claude/agents/`, and `.claude/common/`, then remove the temp directory. Do not run end-to-end tests inside this repository or another long-lived project. Finish with `git status --short`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative Chinese summaries, often scoped, for example `bin/harness: 简化为 Codex App 单 runtime 部署` or `harness-backend: 新增 CodeReview 子智能体`. Keep commits focused. PRs should state the affected mode, list validation commands, link related plans or issues, and include screenshots only for UI or rendered-documentation changes.

## Security & Configuration Tips

Deployment overwrites same-name files under the selected runtime target (`.codex/` plus `.agents/skills/`, or `.claude/`), and removes obsolete files only when tracked in that runtime's Harness manifest.
