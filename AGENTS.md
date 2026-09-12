# Repository Guidelines

## Project Structure & Module Organization

This repository packages Keel skills, custom agent manuals, and deployment scripts for Codex App. `bin/keel` is the deployment CLI. Root-level `common/`, `keel-plan/`, and `keel-dev/` are the Codex App runtime sources. Shared helpers live in each runtime's `common/scripts/`. Skills live in `keel-<mode>/skills/`, and related agents live in `keel-<mode>/agents/`.

## Build, Test, and Development Commands

- `./install.sh`: adds this repo's `bin/` directory to the shell rc file.
- `bin/keel dev --codex "$tmpdir"`: deploys the Codex App runtime with skills in `.agents/skills/` and custom agents/common state in `.codex/`.
- `bash -n bin/keel`: checks the deployment CLI syntax.
- `find common -type f -name '*.sh' -exec bash -n {} \;`: checks shell helper syntax.
- `scripts/check-runtime-contract.sh`: checks the Codex runtime and language-neutral development contract.
- `scripts/keel-metrics.sh`: reports current instruction and runtime size against `evals/keel/baseline-2.1.0.tsv`.
- `scripts/check-slimming-targets.sh`: enforces the approved Skill and Agent instruction-reduction targets.
- `scripts/check-call-chain-controlled-eval.sh`: validates the three-round controlled CallChain on-demand gate.
- `scripts/summarize-call-chain-shadow.sh`: reports historical CallChain prefilter shadow results.
There is no package-manager build step.

## Coding Style & Naming Conventions

Use Bash for scripts and keep `set -euo pipefail` on operational CLIs where practical. Quote variables, prefer local variables inside functions, and write clear stderr failures. New Codex modes should follow `keel-<mode>/skills/keel-<mode>/` plus `keel-<mode>/agents/`. Keep Markdown instructions concise and preserve the existing Chinese instructional tone.

## Testing Guidelines

Behavior eval cases and hard gates live in `evals/keel/`. For deployment tests, create a target with `mktemp -d`, run `bin/keel dev --codex "$tmpdir"`, inspect `.codex/.keel/installed-manifest`, `.agents/skills/`, `.codex/agents/`, and `.codex/common/`, then remove the temp directory. Do not run end-to-end tests inside this repository or another long-lived project. Finish with `git status --short`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative Chinese summaries, often scoped, for example `bin/keel: 简化为 Codex App 单 runtime 部署` or `keel-dev: 新增 CodeReview 子智能体`. Keep commits focused. PRs should state the affected mode, list validation commands, link related plans or issues, and include screenshots only for UI or rendered-documentation changes.

## Security & Configuration Tips

Deployment overwrites same-name files under the selected runtime target (`.codex/` plus `.agents/skills/`), and removes obsolete files only when tracked in that runtime's Keel manifest.
