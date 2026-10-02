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
specs = {mode: f'common/refs/keel-{mode}-spec.md' for mode in ('plan', 'dev', 'qa', 'call-chain', 'fix')}
orchestration = 'keel-dev/skills/keel-dev/SKILL.md'
flow_spec = 'common/refs/keel-business-flow-spec.md'
measure('codex-plan-skill', 'keel-plan/skills/keel-plan/SKILL.md')
measure('codex-planner-instructions', 'keel-plan/agents/keel-planner.md')
measure('codex-planner-default-task-input', 'keel-plan/agents/keel-planner.md',
        'keel-plan/agents/keel-planner.toml', specs['plan'], flow_spec,
        'keel-plan/skills/keel-plan/SKILL.md#起草与修订')
measure('codex-plan-effective-input', 'keel-plan/skills/keel-plan/SKILL.md',
        'keel-plan/agents/keel-planner.md', 'keel-plan/agents/keel-planner.toml', specs['plan'], flow_spec)
measure('codex-plan-template', 'keel-plan/skills/keel-plan/assets/plan-template.md')
measure('codex-fix-skill', 'keel-dev/skills/keel-fix/SKILL.md')
measure('codex-builder-diagnosis-input', 'keel-dev/agents/keel-builder.md',
        'keel-dev/agents/keel-builder.toml', specs['dev'] + '#操作约束', specs['dev'] + '#问题定位',
        'keel-dev/skills/keel-fix/SKILL.md#接收与定位')
measure('codex-spec', *specs.values(), flow_spec)
measure('codex-business-flow-spec', flow_spec)
for mode, path in specs.items():
    measure(f'codex-{mode}-spec', path)
measure('codex-dev-skill', 'keel-dev/skills/keel-dev/SKILL.md')
measure('codex-dev-effective-input', orchestration)
for role, task, mode in (
    ('builder', '实现', 'dev'),
    ('qa', '验收', 'qa'),
    ('call-chain', '流程维护', 'call-chain'),
):
    agent = f'keel-dev/agents/keel-{role}'
    task_refs = [orchestration + '#运行衔接', orchestration + '#' + task]
    spec = specs[mode]
    measure(f'codex-{role}-instructions', agent + '.md')
    # The old Agent baseline excluded shared coding standards; retain the same comparison scope.
    scope = read(spec) + (read(flow_spec) if role == 'call-chain' else '')
    if role == 'builder':
        scope = scope[:scope.index('## 代码与测试标准\n')]
    measure_contents(f'codex-{role}-baseline-input', read(agent + '.md'), scope,
                     *(read(reference) for reference in task_refs))
    # QA uses the same development standard as implementation, plus its own operation constraints.
    spec_refs = [spec] + ([flow_spec] if role == 'call-chain' else []) + ([specs['dev'] + '#代码与测试标准'] if role == 'qa' else [])
    measure(f'codex-{role}-default-task-input', agent + '.md', agent + '.toml', *task_refs, *spec_refs)
for role, task, mode in (('builder', '修复', 'dev'), ('qa', '验收与返修', 'qa')):
    agent = f'keel-dev/agents/keel-{role}'
    fix_skill = 'keel-dev/skills/keel-fix/SKILL.md'
    extra = [specs['dev'] + '#代码与测试标准'] if role == 'qa' else []
    measure(f'codex-{role}-fix-task-input', agent + '.md', agent + '.toml',
            fix_skill + '#' + task, fix_skill + '#运行衔接', specs['fix'], specs[mode], *extra)
paths = [str(path.relative_to(root)) for directory in ('keel-plan', 'keel-dev', 'common')
         for path in sorted((root / directory).rglob('*')) if path.is_file()]
measure('codex-runtime', *paths)
PY_METRICS
