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


def expand_contents(contents, excluded=(), root_refs=()):
    """Include shared standards reached through Spec references, once per reference."""
    result = list(contents)
    seen = set(root_refs)
    complete_files = {reference for reference in root_refs if '#' not in reference}

    def visit(content):
        for reference in re.findall(r'\.codex/common/refs/[\w.-]+\.md(?:#[\w -]+)?', content):
            reference = reference.replace('.codex/common/refs/', 'common/refs/', 1).strip()
            path, _, heading = reference.partition('#')
            if reference in seen or path in excluded or path in complete_files:
                continue
            seen.add(reference)
            if not heading:
                complete_files.add(path)
            text = read(reference)
            result.append(text)
            visit(text)

    for content in contents:
        visit(content)
    return result


def measure(label, *references):
    # Follow shared Spec references; a Skill mentioning a delegated Spec does not read it itself.
    contents = [read(reference) for reference in references]
    rule_contents = [content for reference, content in zip(references, contents)
                     if reference.startswith('common/refs/')]
    expanded = expand_contents(rule_contents, root_refs=references)
    measure_contents(label, *contents, *expanded[len(rule_contents):])


def spec_references(text):
    references = [reference.replace('.codex/common/refs/', 'common/refs/', 1).strip()
                  for reference in re.findall(r'\.codex/common/refs/[\w.-]+\.md(?:#[\w -]+)?', text)]
    complete_files = {reference for reference in references if '#' not in reference}
    return list(dict.fromkeys(reference for reference in references
                              if '#' not in reference or reference.partition('#')[0] not in complete_files))


def required_rules(references, excluded=()):
    references = [reference for reference in references if reference.partition('#')[0] not in excluded]
    return expand_contents([read(reference) for reference in references], excluded=excluded, root_refs=references)


def fixed_agent_input(label, agent, references):
    # The dynamic task and project evidence are measured by behavior evals, not this inventory.
    measure(label, agent + '.md', agent + '.toml', *references)


print('component\tlines\tchars')
plan_skill = 'keel-plan/skills/keel-plan/SKILL.md'
dev_skill = 'keel-dev/skills/keel-dev/SKILL.md'
fix_skill = 'keel-dev/skills/keel-fix/SKILL.md'
quality_spec = 'common/refs/keel-code-quality-spec.md'
all_specs = [str(path.relative_to(root)) for path in sorted((root / 'common/refs').glob('*.md'))]

planner = 'keel-plan/agents/keel-planner'
research_refs = spec_references(read(plan_skill + '#调研'))
proposal_refs = spec_references(read(plan_skill + '#调研') + read(plan_skill + '#起草与修订'))
measure('codex-plan-skill', plan_skill)
measure('codex-planner-instructions', planner + '.md')
fixed_agent_input('codex-planner-research-input', planner, research_refs)
fixed_agent_input('codex-planner-default-task-input', planner, proposal_refs)
measure('codex-plan-effective-input', plan_skill, planner + '.md', planner + '.toml', *proposal_refs)
measure('codex-plan-template', 'keel-plan/skills/keel-plan/assets/plan-template.md')
measure('codex-fix-skill', fix_skill)
fixed_agent_input('codex-builder-diagnosis-input', 'keel-dev/agents/keel-builder',
                  spec_references(read(fix_skill + '#接收与定位').split('\n\n')[1]))
measure('codex-spec', *all_specs)
for path in all_specs:
    suffix = Path(path).stem.removeprefix('keel-')
    measure('codex-' + suffix, path)

measure('codex-dev-skill', dev_skill)
measure('codex-dev-effective-input', dev_skill)
rows = re.findall(r'^\| (实现|验收|流程维护) \| (keel-[\w-]+) \| ([^|]+) \|$',
                  read(dev_skill + '#角色与规范'), re.M)
if len(rows) != 3:
    raise SystemExit('开发职责绑定须包含实现、验收和流程维护')
for _, name, cell in rows:
    role = name.removeprefix('keel-')
    agent = 'keel-dev/agents/' + name
    references = spec_references(cell)
    measure(f'codex-{role}-instructions', agent + '.md')
    # The historical role baseline excluded shared coding standards; keep that comparison scope.
    # Skill steps and runtime instructions now stay with the main session and are not Agent input.
    measure_contents(f'codex-{role}-baseline-input', read(agent + '.md'),
                     *required_rules(references, excluded={quality_spec}))
    fixed_agent_input(f'codex-{role}-default-task-input', agent, references)
    measure(f'codex-{role}-fixed-input', agent + '.md', agent + '.toml', *references)

for role, step in (('builder', '修复'), ('qa', '验收与返修')):
    dispatch = read(fix_skill + '#' + step).split('\n\n')[1]
    references = spec_references(dispatch)
    fixed_agent_input(f'codex-{role}-fix-task-input', 'keel-dev/agents/keel-' + role, references)

paths = [str(path.relative_to(root)) for directory in ('keel-plan', 'keel-dev', 'common')
         for path in sorted((root / directory).rglob('*')) if path.is_file()]
measure('codex-runtime', *paths)

PY_METRICS
