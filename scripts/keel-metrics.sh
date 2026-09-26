#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_root" <<'PY_METRICS'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])


def read(reference):
    relative, _, heading = reference.partition('#')
    text = (root / relative).read_text()
    if not heading:
        return text
    matches = re.findall(r'^## ' + re.escape(heading) + r'\n.*?(?=^## |\Z)', text, re.M | re.S)
    if len(matches) != 1:
        raise SystemExit('缺失或重复的章节: ' + reference)
    return matches[0]


def measure_contents(label, *contents):
    print(label, sum(text.count('\n') for text in contents), sum(map(len, contents)), sep='\t')


def measure(label, *references):
    measure_contents(label, *(read(reference) for reference in references))


print('component\tlines\tchars')
specs = {mode: f'common/refs/keel-{mode}-spec.md' for mode in ('dev', 'qa', 'call-chain')}
orchestration = 'common/refs/keel-dev-orchestration.md'
measure('codex-plan-skill', 'keel-plan/skills/keel-plan/SKILL.md')
measure('codex-plan-template', 'keel-plan/skills/keel-plan/assets/plan-template.md')
measure('codex-spec', *specs.values())
for mode, path in specs.items():
    measure(f'codex-{mode}-spec', path)
measure('codex-orchestration-contract', orchestration)
measure('codex-orchestration-dispatch', orchestration + '#主会话编排')
for mode, skill in (('full', 'keel-dev'), ('fast', 'keel-dev-fast')):
    path = f'keel-dev/skills/{skill}/SKILL.md'
    measure(f'codex-{mode}-skill', path)
    measure(f'codex-{mode}-effective-input', path, orchestration + '#主会话编排')
for role, task, mode in (
    ('builder', '实现任务', 'dev'),
    ('qa', '验收任务', 'qa'),
    ('call-chain', '流程维护任务', 'call-chain'),
):
    agent = f'keel-dev/agents/keel-{role}'
    task_refs = [orchestration + '#通用任务要求', orchestration + '#' + task]
    spec = specs[mode]
    measure(f'codex-{role}-instructions', agent + '.md')
    # The old Agent baseline excluded shared coding standards; retain the same comparison scope.
    scope = read(spec)
    if role == 'builder':
        scope = scope[:scope.index('## 代码与测试标准\n')]
    measure_contents(f'codex-{role}-baseline-input', read(agent + '.md'), scope,
                     *(read(reference) for reference in task_refs))
    # QA uses the same development standard as implementation, plus its own operation constraints.
    spec_refs = [spec] + ([specs['dev'] + '#代码与测试标准'] if role == 'qa' else [])
    measure(f'codex-{role}-default-task-input', agent + '.md', agent + '.toml', *task_refs, *spec_refs)
paths = [str(path.relative_to(root)) for directory in ('keel-plan', 'keel-dev', 'common')
         for path in sorted((root / directory).rglob('*')) if path.is_file()]
measure('codex-runtime', *paths)
PY_METRICS
