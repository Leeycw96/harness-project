#!/usr/bin/env python3
"""Check ASO dependency boundaries, deployed resources and the existing run protocol."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / 'keel-dev/agents'
REFS = ROOT / 'common/refs'
ROLE_TASKS = {'builder': '实现任务', 'qa': '验收任务', 'call-chain': '流程维护任务'}
ROLE_SPECS = {'builder': 'keel-dev-spec.md', 'qa': 'keel-qa-spec.md', 'call-chain': 'keel-call-chain-spec.md'}
TAGS = {
    'BUILD_SLICE_DONE': ('builder', 'BUILD', 'plan.md'),
    'BUILD_DONE': ('builder', 'BUILD', 'plan.md'),
    'BUILD_FAST_DONE': ('builder', 'BUILD_FAST', 'plan.md'),
    'FIX_DONE': ('builder', 'FIX', 'fix-brief.md'),
    'FIX_FAST_DONE': ('builder', 'FIX_FAST', 'fix-brief.md'),
    'APPROVED': ('qa', 'REVIEW', 'qa-feedback.md'),
    'REJECTED': ('qa', 'REVIEW_FAST_FIX', 'qa-feedback.md'),
    'CALL_CHAIN_NOOP': ('call-chain', 'CALL_CHAIN', 'call-chain-review.md'),
    'CALL_CHAIN_UPDATED': ('call-chain', 'CALL_CHAIN', 'call-chain-review.md'),
}


class AsoContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix='keel-aso-')
        cls.project = Path(cls.workspace.name).resolve()
        result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(cls.project)], capture_output=True, text=True)
        if result.returncode:
            cls.workspace.cleanup()
            raise RuntimeError(result.stderr)
        cls.refs = cls.project / '.codex/common/refs'
        cls.init = cls.project / '.codex/common/scripts/keel-init.sh'
        cls.helpers = cls.project / '.codex/common/scripts/keel-common.sh'
        cls.plan = cls.project / '.agents/skills/keel-plan/assets/plan-template.md'

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def shell(self, script, *args, success=True):
        result = subprocess.run(['bash', '-c', 'set -euo pipefail\n' + script, 'aso-test', *map(str, args)], capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def init_run(self, mode, name):
        output = self.project / name
        function = 'init_keel_run' if mode == 'full' else 'init_keel_fast_run'
        self.shell('export PROJECT_DIR="$1"\nsource "$2"\n' + function + ' "$3" "$4"', self.project, self.init, output, self.plan)
        return output / 'state.json'

    def helper(self, state, command, *args, success=True):
        return self.shell('export KEEL_PROFILE="$1"\nsource "$2"\n' + command, state, self.helpers, *args, success=success)

    def test_role_definitions_do_not_import_spec_or_workflow(self):
        # Stable professional methods such as TDD belong to A; concrete runtime dependencies do not.
        forbidden = r'KEEL_PROFILE|state\.json|profile\.json|\.keel/|\.codex/common|plan\.md|fix-brief|qa-feedback|call-chain-review|complete_stage|update_progress|\b(?:BUILD|REVIEW|FIX|CALL_CHAIN|PREFLIGHT|APPROVED|REJECTED|NOOP|UPDATED|PAUSED)(?:_[A-Z]+)*\b|\b(?:full|fast)\b'
        for role in ROLE_TASKS:
            with self.subTest(role=role):
                source = (AGENTS / f'keel-{role}.md').read_text()
                self.assertNotRegex(source, forbidden)
                config = tomllib.loads((AGENTS / f'keel-{role}.toml').read_text())
                self.assertNotRegex(config['developer_instructions'], forbidden)
                self.assertNotRegex(config['description'], forbidden)
                paths = re.findall(r'\.codex/[\w/.-]+\.md', config['developer_instructions'])
                self.assertEqual(paths, [f'.codex/agents/keel-{role}.md'])
                self.assertEqual(config['name'], f'keel-{role}')

    def read_reference(self, reference):
        relative, _, heading = reference.partition('#')
        path = self.project / relative
        self.assertTrue(path.is_file(), reference)
        manifest = (self.project / '.codex/.keel/installed-manifest').read_text().splitlines()
        self.assertIn(relative, manifest)
        text = path.read_text()
        if heading:
            matches = re.findall(r'^## ' + re.escape(heading) + r'\n.*?(?=^## |\Z)', text, re.M | re.S)
            self.assertEqual(len(matches), 1, reference)
            return matches[0]
        return text

    def test_spec_has_no_agent_registration_or_orchestration_dependencies(self):
        for name in ROLE_SPECS.values():
            with self.subTest(spec=name):
                text = (REFS / name).read_text()
                self.assertNotRegex(text, r'keel-builder|keel-qa\.md|keel-call-chain\.md|\.codex/agents/|KEEL_PROFILE|state\.json|complete_stage|update_progress|\b(?:BUILD|REVIEW|FIX|PAUSED|PREFLIGHT|NOOP|UPDATED)(?:_[A-Z]+)*\b')

    def test_deployed_orchestration_resource_graph_is_complete(self):
        roots = ['.agents/skills/keel-dev/SKILL.md', '.agents/skills/keel-dev-fast/SKILL.md',
                 '.agents/skills/keel-fix/SKILL.md']
        seen = set()
        while roots:
            reference = roots.pop()
            if reference in seen:
                continue
            seen.add(reference)
            text = self.read_reference(reference)
            for linked in re.findall(r'\.(?:codex|agents)/[\w/.-]+\.(?:md|sh|py)(?:#[\w-]+)?', text):
                roots.append(linked)
        for task in ROLE_TASKS.values():
            self.assertIn('.codex/common/refs/keel-dev-orchestration.md#' + task, seen)
        self.assertIn('.codex/common/refs/keel-dev-orchestration.md#通用任务要求', seen)
        for name in ROLE_SPECS.values():
            self.assertIn('.codex/common/refs/' + name, seen)
        self.assertIn('.codex/common/refs/keel-dev-spec.md#代码与测试标准', seen)
        self.assertIn('.codex/common/refs/keel-dev-spec.md#问题定位', seen)
        self.assertIn('.agents/skills/keel-fix/SKILL.md#定位任务', seen)
        self.assertIn('.agents/skills/keel-fix/scripts/keel-fix.py', seen)
        self.assertIn('.agents/skills/keel-fix/assets/bug-template.md', seen)
        self.assertEqual({p.name for p in self.refs.iterdir()}, {*ROLE_SPECS.values(), 'keel-dev-orchestration.md'})

    def test_default_bindings_route_each_role_to_spec_and_task(self):
        main = self.read_reference('.codex/common/refs/keel-dev-orchestration.md#主会话编排')
        rows = re.findall(r'^\| (实现|验收|流程维护) \| (keel-[\w-]+) \| (\.codex/[^ ]+) \| (\.codex/[^ ]+) \|$', main, re.M)
        self.assertEqual(len(rows), 3)
        for _, agent, spec_ref, task in rows:
            role = agent.removeprefix('keel-')
            self.assertEqual(task.partition('#')[2], ROLE_TASKS[role])
            self.assertEqual(spec_ref, '.codex/common/refs/' + ROLE_SPECS[role])
            self.read_reference(spec_ref)
            self.read_reference(task)
            self.assertTrue((self.project / '.codex/agents' / (agent + '.toml')).is_file())
        tables = {'实现任务': {'BUILD', 'BUILD_FAST', 'FIX', 'FIX_FAST'},
                  '验收任务': {'REVIEW', 'REVIEW_FAST', 'REVIEW_FIX', 'REVIEW_FAST_FIX'}}
        for task, expected in tables.items():
            text = self.read_reference('.codex/common/refs/keel-dev-orchestration.md#' + task)
            actual = set(re.findall(r'^\| ([A-Z_]+) \|', text, re.M))
            self.assertEqual(actual, expected)
        for tag, (role, _, _) in TAGS.items():
            self.assertIn(tag, self.read_reference('.codex/common/refs/keel-dev-orchestration.md#' + ROLE_TASKS[role]))

    def test_redeployment_removes_retired_files_but_preserves_user_files(self):
        with tempfile.TemporaryDirectory(prefix='keel-upgrade-') as work:
            project = Path(work)
            retired = ['keel-dev-coding-rules.md', 'keel-call-chain-rules.md',
                       'keel-dev-environment.md', 'keel-dev-task-protocol.md',
                       'tasks/implement.md', 'tasks/verify.md', 'tasks/maintain-flow.md']
            manifest = project / '.codex/.keel/installed-manifest'
            manifest.parent.mkdir(parents=True)
            entries = ['.codex/common/refs/' + name for name in retired]
            for entry in entries:
                path = project / entry
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('previous deployed instructions')
            manifest.write_text('\n'.join(entries) + '\n')
            user_file = project / '.codex/common/refs/project-notes.md'
            user_file.write_text('project-owned instructions')
            result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(project)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for entry in entries:
                self.assertFalse((project / entry).exists())
                self.assertNotIn(entry, manifest.read_text().splitlines())
            for name in (*ROLE_SPECS.values(), 'keel-dev-orchestration.md'):
                self.assertEqual((project / '.codex/common/refs' / name).read_bytes(), (REFS / name).read_bytes())
                self.assertIn('.codex/common/refs/' + name, manifest.read_text().splitlines())
            self.assertEqual(user_file.read_text(), 'project-owned instructions')

    def test_full_fast_initialization_preserves_gates_and_artifacts(self):
        for mode in ('full', 'fast'):
            state = self.init_run(mode, 'init-' + mode)
            data = json.loads(state.read_text())
            self.assertEqual(data['mode'], mode)
            self.assertEqual(data['phase'], 'INIT')
            self.assertEqual(data['limits'], {'fix_rounds': 3, 'stage_recoveries': 2})
            self.assertEqual(data['thresholds'], {'short_stage_no_progress_seconds':300,'long_stage_no_progress_seconds':900})
            self.assertTrue(Path(data['plan_path']).is_file())
            self.assertEqual(set(data['review']), {'qa'})
            self.assertEqual('call_chain_review' in data['artifacts'], mode == 'full')
            self.assertEqual(data['preflight']['test_compile']['user_decision'], None)
            if mode == 'fast':
                self.assertEqual(data['fast']['skipped'], ['call-chain'])

    def test_injected_progress_and_completion_protocol_keeps_all_public_tags(self):
        state = self.init_run('full', 'events')
        log = state.parent / 'progress.tsv'
        for tag, (role, stage, artifact_name) in TAGS.items():
            artifact = state.parent / artifact_name
            if not artifact.exists():
                artifact.write_text('current task evidence')
            self.helper(state, 'update_progress "$3" "$4" "正在执行" "$5"\ncomplete_stage "$3" "$6" "已完成" "$5"', 'keel-' + role, stage, artifact, tag)
        events = [line.split('\t') for line in log.read_text().splitlines()]
        self.assertEqual({event[3] for event in events if event[1] == 'complete'}, set(TAGS))
        self.assertEqual(len(events), 2 * len(TAGS))
        before = log.read_text()
        self.helper(state, 'complete_stage keel-qa APPROVED "不能通过" "$3"', state.parent / 'missing.md', success=False)
        self.assertEqual(log.read_text(), before)

    def test_replaceable_bindings_survive_state_updates_without_role_edits(self):
        state = self.init_run('full', 'replaceable')
        role_paths = list((self.project / '.codex/agents').glob('*'))
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in role_paths}
        spec = self.project / 'alternate-spec.md'
        spec.write_text('使用本项目配置的验证工具，遵守已授权的交付范围。')
        (self.project / '.codex/agents/alternate-builder.toml').write_text(
            'name = "alternate-builder"\ndeveloper_instructions = "依据注入目标与规范完成实现并报告证据。"\n')
        bindings = {'builder': {'agent': 'alternate-builder', 'spec_refs':[str(spec)],
                               'task_ref':str(self.refs / 'keel-dev-orchestration.md') + '#实现任务'}}
        self.helper(state, '_keel_state_jq --argjson bindings "$3" \'.aso_bindings = $bindings\'\nrecord_call_chain_prefilter noop "仅局部校验"\nrecord_call_chain_skip', json.dumps(bindings))
        self.assertEqual(json.loads(state.read_text())['aso_bindings'], bindings)
        self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in role_paths}, hashes)

    def test_call_chain_dispatch_guards_and_shadow_remain_compatible(self):
        state = self.init_run('full', 'callchain')
        self.helper(state, 'record_call_chain_skip', success=False)
        self.helper(state, 'record_call_chain_prefilter run "新增状态流转"')
        self.helper(state, 'record_call_chain_skip', success=False)
        (state.parent / 'call-chain-review.md').write_text('UPDATED\n状态及其证据')
        self.helper(state, 'record_call_chain_result updated "$3"', 'a' * 40)
        data = json.loads(state.read_text())
        self.assertEqual(data['phase'], 'DONE')
        self.assertEqual(data['call_chain']['action'], 'updated')
        self.assertEqual(data['call_chain']['commit'], 'a' * 40)
        shadow = self.init_run('full', 'shadow')
        self.helper(shadow, '_keel_state_jq \'.call_chain.prefilter.mode = "shadow"\'\nrecord_call_chain_prefilter noop "影子预判"\nrecord_call_chain_shadow_result updated')
        self.assertFalse(json.loads(shadow.read_text())['call_chain']['prefilter']['safe'])
        self.helper(shadow, 'record_call_chain_skip', success=False)

    def test_legacy_profile_uses_its_configured_progress_and_state(self):
        state = self.init_run('full', 'legacy')
        profile = state.parent / 'profile.json'
        old = json.loads(state.read_text())
        old['progress'] = {'events':str(state.parent / 'progress.events')}
        profile.write_text(json.dumps(old))
        result = self.helper(profile, 'keel_state_file\nupdate_progress keel-builder BUILD "恢复"\nrecord_call_chain_prefilter noop "无变化"')
        self.assertIn(str(state), result.stdout)
        self.assertTrue((state.parent / 'progress.events').is_file())
        self.assertEqual(json.loads(state.read_text())['call_chain']['prefilter']['decision'], 'noop')


if __name__ == '__main__':
    unittest.main(verbosity=2)
