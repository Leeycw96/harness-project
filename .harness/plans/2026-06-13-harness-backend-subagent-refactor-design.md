# Harness Backend Subagent Refactor Design

Date: 2026-06-13

## Background

`harness-backend` started as a long-running Builder + QA workflow. Production use
has improved it, but four problems remain:

- Builder and QA coordinate inefficiently and can forget to notify each other
  after context compression.
- The user-adjustment phase adds process cost without the same rigor as the
  original planned build path.
- Existing strong Codex capabilities are underused, especially planning-style
  requirement clarification and code review.
- The main session has poor visibility into Builder and QA progress and often
  depends on the user saying "continue" after a subagent stalls.

This refactor changes `harness-backend` into a Codex App only, subagent-only
workflow. The user interacts only with the main session. The main session owns
state, scheduling, progress reporting, recovery, and final decisions.

## Goals

- Remove tmux, pane, send-keys, Claude Code CLI, and Codex CLI workflows.
- Make the root-level directories the only source of truth:
  `common/`, `harness-plan/`, and `harness-backend/`.
- Keep Builder, QA, and CodeReview isolated behind explicit main-session
  orchestration.
- Improve throughput by avoiding direct Builder <-> QA chatter.
- Keep quality high with both business QA and code review gates.
- Make progress visible to the user through main-session monitoring.
- Make stalled work recoverable through disk state and subagent restart.
- Reduce run-directory noise so users and subagents read only current artifacts.

## Non-Goals

- No user-adjustment phase in this refactor. After QA and CodeReview pass, the
  run ends. New changes should start a new plan/backend run.
- No support for `claude-code`, `codex-cli`, tmux, or pane-based execution.
- No full audit log of every intermediate scope/review version.
- No automatic merge, squash, push, or final history cleanup.
- No review of user-unrelated uncommitted changes.

## Runtime And Source Layout

`bin/harness` will become a Codex App deployment CLI. It will no longer accept
`--claude-code`, `--codex-cli`, or `--runtime`.

Deployment targets:

- skills -> `.agents/skills/`
- agents -> `.codex/agents/`
- common helpers -> `.codex/common/`
- manifest -> `.codex/.harness/installed-manifest`

Repository source layout after the refactor:

```text
harness-project/
  bin/harness
  common/
  harness-plan/
  harness-backend/
```

Runtime-specific source directories such as `claude-code/`, `codex/`, and
`codex-cli/` will be removed. The old `harness-solidity/` mode is outside the
new backend workflow and will also be removed from the deployable surface.

## Architecture

The main session is the only orchestrator. It receives the plan, initializes the
run, dispatches subagents by stage, monitors progress, validates artifacts, and
updates state.

Roles:

- `harness-builder`: creates scope, implements feature slices, fixes blocking
  feedback, and commits Builder changes.
- `harness-qa`: reviews scope and validates business behavior. It produces the
  business verification package and QA verdict.
- `harness-code-review`: reviews the Builder commit diff for correctness,
  maintainability, architecture boundaries, test quality, and anti-stub rules.

Subagents do not message each other and do not wait for each other. They receive
one stage assignment from the orchestrator, read the current files, write their
artifact, update progress, return a concise result, and stop.

High-level flow:

```text
plan.md
  -> Builder creates build-scope.md
  -> QA reviews scope-review.md
  -> Builder builds slices and commits
  -> QA and CodeReview run in parallel
  -> If any blocking feedback exists, Builder fixes once from fix-brief.md
  -> QA and CodeReview re-review in parallel
  -> Done when both pass, paused when limits are reached
```

## Run Directory Contract

Each run creates:

```text
.harness/iterations/<branch>/run-N/
  plan.md
  profile.json
  state.json
  build-scope.md
  scope-review.md
  qa-feedback.md
  code-review.md
  fix-brief.md
  progress/
    builder.md
    qa.md
    code-review.md
    events.tsv
```

Only `plan.md`, `profile.json`, and `state.json` are mandatory at run
initialization. Other artifacts appear when their stage produces them.

Artifact rules:

- Artifacts are current-state files, not history files.
- Scope and review files are overwritten with the latest valid version.
- Subagents must read only the artifact paths named in `state.json` or the
  stage prompt. They must not scan the run directory for older context.
- `fix-brief.md` exists only when the orchestrator has merged blocking feedback.
- `progress/` is the only directory because progress is needed for liveness and
  user visibility.

Removed from the current design:

- `conversation/`: no direct agent-to-agent communication.
- `signals/`: the orchestrator validates returned artifacts and updates
  `state.json`; separate signal files are unnecessary.
- `baseline/`: preflight results live as summaries in `state.json`.
- `scope/`, `qa/`, `code-review/`, and `fixes/`: directory nesting adds lookup
  cost without improving the core workflow.

## State Contract

`profile.json` stores static run configuration:

- `project_dir`
- `output_dir`
- `plan_path`
- agent document paths
- progress thresholds
- fix and scope retry limits
- deployment/runtime marker: `codex-app`

`state.json` is the single source of truth for orchestration:

- `phase`: `INIT`, `PREFLIGHT`, `SCOPE_BUILD`, `SCOPE_REVIEW`, `BUILD`,
  `PARALLEL_REVIEW`, `FIX`, `DONE`, or `PAUSED`
- `preflight`: main/test compile status and short summaries
- `scope_attempt`
- `build`: current slice, completed slices, Builder commit SHAs
- `review`: QA and CodeReview status, artifact paths, blocking issue counts
- `fix_round`: current fix round, maximum 3
- `retries`: per stage and per role recovery counts
- `next_action`: the orchestrator's next intended step

`state.json` may include a compact event list, but only as short summaries. It
must not become a conversation log.

## Stage Flow

### PREFLIGHT

The main session runs preflight before starting subagents.

- Main code compile failure hard-stops the run.
- Test compile failure asks the user whether to continue.
- When the user continues after test compile failure, `state.json.preflight`
  stores a short summary. QA and CodeReview treat those known failures as
  pre-existing unless Builder changes clearly caused them.

### SCOPE_BUILD

Builder reads `plan.md`, project guidance, and existing call-chain files. It
writes `build-scope.md`.

Builder may list unclear requirements, but must not silently invent acceptance
criteria or expand scope.

### SCOPE_REVIEW

QA reads `plan.md` and `build-scope.md`, then writes `scope-review.md`.

If scope is incomplete or not testable, the orchestrator sends the QA adjustment
points back to Builder. Builder overwrites `build-scope.md`. Scope alignment is
limited to 3 attempts. If it still fails, the run becomes `PAUSED`.

### BUILD

The orchestrator chooses build granularity:

- Small scope: one Builder pass.
- Larger scope: one feature slug or a small batch of related slugs per pass.

Builder writes progress, implements using the existing coding rules, updates
call-chain files, runs relevant tests plus test compile, and creates commits.
The orchestrator records Builder commit SHAs in `state.json`.

### PARALLEL_REVIEW

QA and CodeReview run in parallel after Builder finishes the current build.

QA responsibilities:

- Validate business completeness against `plan.md` and `build-scope.md`.
- Run relevant tests and inspect changed business behavior.
- Produce `qa-feedback.md` with a business verification package.
- Return `APPROVED` or `REJECTED`.

CodeReview responsibilities:

- Review only the Builder commit diff recorded in `state.json`.
- Prioritize correctness, regressions, architecture boundary violations, test
  quality, and stub/fake behavior.
- Produce `code-review.md` with P0/P1/P2 findings.
- Treat P0/P1 as blocking and P2 as non-blocking.

The final review gate is strict: any QA rejection or CodeReview P0/P1 finding
means the run enters `FIX`.

### FIX

The orchestrator merges QA blocking feedback and CodeReview P0/P1 findings into
`fix-brief.md`.

Builder reads `fix-brief.md`, fixes root causes, runs relevant tests, commits,
and updates progress. Then QA and CodeReview re-run in parallel and overwrite
their current feedback files.

Fixing is limited to 3 rounds. If both gates do not pass after 3 rounds, the run
becomes `PAUSED` and the main session summarizes unresolved blocking issues for
the user.

### DONE

The run is complete when QA passes and CodeReview has no P0/P1 findings.

The main session summarizes:

- final status
- Builder commits
- QA verification package path
- CodeReview result path
- any non-blocking P2 recommendations

It does not stage, merge, squash, push, or clean up commits.

## Progress And Recovery

Subagents must update progress at stage start and at meaningful milestones.

Progress thresholds:

- `SCOPE_BUILD`, `SCOPE_REVIEW`, and `PARALLEL_REVIEW`: 5 minutes without a
  progress update triggers inspection.
- `BUILD` and `FIX`: 15 minutes without a progress update triggers inspection.

Recovery sequence:

1. The orchestrator checks whether the subagent is still alive.
2. If alive, it sends a recovery prompt to the same subagent. The prompt tells
   the agent to re-read `profile.json`, `state.json`, the current artifact, git
   diff, and its own progress file before continuing.
3. If the subagent is not alive, cannot receive input, or still fails to update
   progress, the orchestrator starts a new subagent with the same role.
4. The new subagent resumes only from disk state and git diff.
5. Each recovery attempt updates `state.json.retries` and appends an event to
   `progress/events.tsv`.

Each stage can be recovered automatically at most 2 times. After that, the run
is `PAUSED` and the main session asks the user to continue, restart that role,
or stop.

Artifact validation failures are treated as recoverable once. If the same role
returns an invalid artifact again, it counts against the stage retry budget.

## Code Review Reuse

Codex has official code review behavior in the local `/review` flow and GitHub
PR review flow. Those features establish the intended review semantics:
high-signal findings, repository guidance, and P0/P1 focus for blocking risks.

The design uses those semantics but implements a `harness-code-review` custom
agent because the UI `/review` command is not a stable internal stage API for
the Harness orchestrator.

The CodeReview agent must:

- follow repository `AGENTS.md` review guidance
- review only the Builder commit diff
- report findings with file and line references when possible
- classify each finding as P0, P1, or P2
- block only P0/P1

## Harness Plan Reuse

`/harness-plan` remains the entry point for creating machine-readable XML
plans. It should adopt the useful parts of `brainstorming`:

- read project context first
- ask one focused question at a time
- identify in-scope work and out-of-scope dependencies
- define concrete, testable acceptance criteria
- get user confirmation before writing the final plan

The output contract stays `.harness/plans/<name>.md` in the existing XML
format. Builder and QA continue to consume the XML plan rather than a free-form
brainstorming spec.

## Files To Change

Expected implementation targets:

- `bin/harness`
- `README.md`
- `AGENTS.md`
- `common/scripts/harness-init.sh`
- `common/scripts/harness-common.sh`
- `harness-plan/skills/harness-plan/SKILL.md`
- `harness-backend/skills/harness-backend/SKILL.md`
- `harness-backend/agents/harness-builder.md`
- `harness-backend/agents/harness-builder-AGENTS.md`
- `harness-backend/agents/harness-qa.md`
- `harness-backend/agents/harness-qa-AGENTS.md`
- `harness-backend/agents/harness-code-review.md`
- `harness-backend/agents/harness-code-review-AGENTS.md`
- `harness-backend/agents/harness-builder.toml`
- `harness-backend/agents/harness-qa.toml`
- `harness-backend/agents/harness-code-review.toml`

Expected removals:

- `claude-code/`
- `codex/`
- `codex-cli/`
- tmux/pane/send-keys helpers
- old backend smoke skill from the deployable surface; a future smoke workflow
  should be designed separately for the subagent-only model
- obsolete solidity mode files from the deployable surface

## Validation

Required checks:

```bash
bash -n bin/harness
find common -type f -name '*.sh' -exec bash -n {} \;
tmp=$(mktemp -d)
bin/harness backend "$tmp"
find "$tmp/.agents/skills" "$tmp/.codex" -maxdepth 4 -type f | sort
rm -rf "$tmp"
git status --short
```

Deployment validation must confirm:

- no `.claude/` tree is created
- no Codex CLI tmux files are deployed
- `.agents/skills/` contains `harness-plan` and `harness-backend`
- `.codex/agents/` contains Builder, QA, and CodeReview agent files
- `.codex/common/` contains only subagent-compatible helper scripts
- `.codex/.harness/installed-manifest` tracks deployed files

Workflow validation should use a temporary fake project and verify that
`profile.json`, `state.json`, current artifacts, and `progress/` follow the run
contract. The fake project should not be this repository or any long-lived
project.

## References

- Codex app review: https://developers.openai.com/codex/app/review
- Codex GitHub code review: https://developers.openai.com/codex/integrations/github
- Codex subagents: https://developers.openai.com/codex/subagents
