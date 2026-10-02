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
AGENT_DIRS = {role: AGENTS for role in ROLE_TASKS} | {'planner': ROOT / 'keel-plan/agents'}
SPEC_FILES = {*ROLE_SPECS.values(), 'keel-plan-spec.md', 'keel-business-flow-spec.md'}
TAGS = {
    'BUILD_SLICE_DONE': ('builder', 'BUILD', 'plan.md'),
    'BUILD_DONE': ('builder', 'BUILD', 'plan.md'),
    'FIX_DONE': ('builder', 'FIX', 'fix-brief.md'),
    'APPROVED': ('qa', 'REVIEW', 'qa-feedback.md'),
    'REJECTED': ('qa', 'REVIEW_FIX', 'qa-feedback.md'),
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

    def init_run(self, name):
        output = self.project / name
        self.shell('export PROJECT_DIR="$1"\nsource "$2"\ninit_keel_run "$3" "$4"', self.project, self.init, output, self.plan)
        return output / 'state.json'

    def helper(self, state, command, *args, success=True):
        return self.shell('export KEEL_PROFILE="$1"\nsource "$2"\n' + command, state, self.helpers, *args, success=success)

    def test_role_definitions_do_not_import_spec_or_workflow(self):
        # Stable professional methods such as TDD belong to A; concrete runtime dependencies do not.
        forbidden = r'KEEL_PROFILE|state\.json|profile\.json|\.keel/|\.codex/common|plan\.md|fix-brief|qa-feedback|call-chain-review|complete_stage|update_progress|\b(?:BUILD|REVIEW|FIX|CALL_CHAIN|PREFLIGHT|APPROVED|REJECTED|NOOP|UPDATED|PAUSED)(?:_[A-Z]+)*\b|\b(?:full|fast)\b'
        for role, directory in AGENT_DIRS.items():
            with self.subTest(role=role):
                source = (directory / f'keel-{role}.md').read_text()
                self.assertNotRegex(source, forbidden)
                config = tomllib.loads((directory / f'keel-{role}.toml').read_text())
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
        for name in SPEC_FILES:
            with self.subTest(spec=name):
                text = (REFS / name).read_text()
                self.assertNotRegex(text, r'keel-builder|keel-qa\.md|keel-call-chain\.md|\.codex/agents/|KEEL_PROFILE|state\.json|complete_stage|update_progress|\b(?:BUILD|REVIEW|FIX|PAUSED|PREFLIGHT|NOOP|UPDATED)(?:_[A-Z]+)*\b')

    def reachable_references(self, roots):
        roots = list(roots)
        seen = set()
        while roots:
            reference = roots.pop()
            if reference in seen:
                continue
            seen.add(reference)
            text = self.read_reference(reference)
            roots.extend(re.findall(r'\.(?:codex|agents)/[\w/.-]+\.(?:md|sh|py)(?:#[\w-]+)?', text))
        return seen

    def test_deployed_orchestration_resource_graph_is_complete(self):
        roots = ['.agents/skills/keel-dev/SKILL.md',
                 '.agents/skills/keel-fix/SKILL.md', '.agents/skills/keel-plan/SKILL.md']
        seen = self.reachable_references(roots)
        for entry in ('.agents/skills/keel-plan/SKILL.md', '.agents/skills/keel-dev/SKILL.md'):
            self.assertIn('.codex/common/refs/keel-business-flow-spec.md', self.reachable_references([entry]))
        for task in ROLE_TASKS.values():
            self.assertIn('.codex/common/refs/keel-dev-orchestration.md#' + task, seen)
        self.assertIn('.codex/common/refs/keel-dev-orchestration.md#通用任务要求', seen)
        for name in SPEC_FILES:
            self.assertIn('.codex/common/refs/' + name, seen)
        self.assertIn('.codex/common/refs/keel-dev-spec.md#代码与测试标准', seen)
        self.assertIn('.codex/common/refs/keel-dev-spec.md#问题定位', seen)
        self.assertIn('.agents/skills/keel-fix/SKILL.md#定位任务', seen)
        self.assertIn('.agents/skills/keel-fix/scripts/keel-fix.py', seen)
        self.assertIn('.agents/skills/keel-fix/assets/bug-template.md', seen)
        self.assertIn('.agents/skills/keel-plan/SKILL.md#调研任务', seen)
        self.assertIn('.agents/skills/keel-plan/SKILL.md#起草与修订任务', seen)
        self.assertIn('.agents/skills/keel-plan/assets/incremental-example.md', seen)
        self.assertEqual({p.name for p in self.refs.iterdir()}, {*SPEC_FILES, 'keel-dev-orchestration.md'})

    def test_planner_is_deployed_with_its_role_and_spec_in_both_modes(self):
        for mode in ('plan', 'dev'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='keel-planner-') as work:
                project = Path(work)
                result = subprocess.run([str(ROOT / 'bin/keel'), mode, '--codex', str(project)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                manifest = (project / '.codex/.keel/installed-manifest').read_text().splitlines()
                config = tomllib.loads((project / '.codex/agents/keel-planner.toml').read_text())
                self.assertEqual(config['name'], 'keel-planner')
                for relative, original in (
                    ('.codex/agents/keel-planner.md', 'keel-plan/agents/keel-planner.md'),
                    ('.codex/agents/keel-planner.toml', 'keel-plan/agents/keel-planner.toml'),
                    ('.codex/common/refs/keel-plan-spec.md', 'common/refs/keel-plan-spec.md'),
                ):
                    self.assertIn(relative, manifest)
                    self.assertEqual((project / relative).read_bytes(), (ROOT / original).read_bytes())
                assets = Path('keel-plan/skills/keel-plan/assets')
                for source in (ROOT / assets).glob('contract-example*'):
                    files = source.rglob('*.md') if source.is_dir() else [source]
                    for original in files:
                        relative = Path('.agents/skills/keel-plan/assets') / original.relative_to(ROOT / assets)
                        self.assertIn(str(relative), manifest)
                        self.assertEqual((project / relative).read_bytes(), original.read_bytes())
                checked = subprocess.run([
                    'python3', str(project / '.codex/common/scripts/keel-plan.py'), 'validate',
                    str(project / '.agents/skills/keel-plan/assets/contract-example.md'),
                ], capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stderr)

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
        tables = {'实现任务': {'BUILD', 'FIX'},
                  '验收任务': {'REVIEW', 'REVIEW_FIX'}}
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
            entries += ['.agents/skills/keel-dev-fast/SKILL.md', '.agents/skills/keel-dev-fast/agents/openai.yaml']
            for entry in entries:
                path = project / entry
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('previous deployed instructions')
            manifest.write_text('\n'.join(entries) + '\n')
            user_file = project / '.codex/common/refs/project-notes.md'
            user_file.write_text('project-owned instructions')
            user_notes = project / '.agents/skills/keel-dev-fast/user-notes.md'
            user_notes.write_text('keep untracked user notes')
            result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(project)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for entry in entries:
                self.assertFalse((project / entry).exists())
                self.assertNotIn(entry, manifest.read_text().splitlines())
            for name in (*SPEC_FILES, 'keel-dev-orchestration.md'):
                self.assertEqual((project / '.codex/common/refs' / name).read_bytes(), (REFS / name).read_bytes())
                self.assertIn('.codex/common/refs/' + name, manifest.read_text().splitlines())
            self.assertEqual(user_file.read_text(), 'project-owned instructions')
            self.assertEqual(user_notes.read_text(), 'keep untracked user notes')

    def test_unified_initialization_preserves_gates_and_conditional_call_chain(self):
        state = self.init_run('init-dev')
        data = json.loads(state.read_text())
        self.assertEqual(data['mode'], 'full')  # Preserve the existing storage value, not a second entrypoint.
        self.assertEqual(data['phase'], 'INIT')
        self.assertEqual(data['limits'], {'fix_rounds': 3, 'stage_recoveries': 2})
        self.assertEqual(data['thresholds'], {'short_stage_no_progress_seconds': 300, 'long_stage_no_progress_seconds': 900})
        self.assertTrue(Path(data['plan_path']).is_file())
        self.assertEqual(set(data['review']), {'qa'})
        self.assertIn('call_chain_review', data['artifacts'])
        self.assertEqual(data['call_chain']['prefilter']['mode'], 'on-demand')
        self.assertIsNone(data['call_chain']['prefilter']['decision'])
        self.assertIsNone(data['preflight']['test_compile']['user_decision'])
        self.assertNotIn('fast', data)
        self.assertFalse((self.project / '.agents/skills/keel-dev-fast/SKILL.md').exists())
        self.shell('export PROJECT_DIR="$1"\nsource "$2"\nif declare -F init_keel_fast_run >/dev/null; then exit 1; fi', self.project, self.init)

    def legacy_fast(self, name, phase):
        state = self.init_run(name)
        data = json.loads(state.read_text())
        data.update(mode='fast', phase=phase, fast={'skipped': ['call-chain']}, fix_round=2)
        data.pop('call_chain')
        data['artifacts'].pop('call_chain_review')
        data['build']['commits'] = ['a' * 40, 'b' * 40]
        data['build']['current_slice'] = 'fast'
        data['retries'] = {'keel-qa': 1}
        data['review']['qa']['status'] = 'rejected'
        data['aso_bindings'] = {'builder': {'agent': 'custom-builder', 'spec_refs': ['custom.md']}}
        data['preflight']['test_compile'] = {'status': 'failed_allowed', 'summary': ['baseline evidence'], 'user_decision': True}
        state.write_text(json.dumps(data))
        (state.parent / 'qa-feedback.md').write_text('REJECTED: existing evidence')
        (state.parent / 'fix-brief.md').write_text('existing repair scope')
        (state.parent / 'progress.tsv').write_text('old FAST progress retained\n')
        return state, data

    def resume(self, profile, success=True):
        return self.shell('export PROJECT_DIR="$1"\nsource "$2"\nresume_keel_run "$3"', self.project, self.init, profile, success=success)

    def test_resume_fast_preserves_work_and_maps_only_active_stages(self):
        phases = {'INIT': 'INIT', 'BUILD_FAST': 'BUILD', 'REVIEW_FAST': 'REVIEW',
                  'FIX_FAST': 'FIX', 'REVIEW_FAST_FIX': 'REVIEW_FIX', 'PAUSED': 'PAUSED'}
        for old_phase, new_phase in phases.items():
            with self.subTest(phase=old_phase):
                state, old = self.legacy_fast('resume-' + old_phase, old_phase)
                evidence = {p: p.read_bytes() for p in state.parent.rglob('*') if p.is_file() and p != state}
                self.assertEqual(self.resume(state).stdout.strip(), str(state))
                new = json.loads(state.read_text())
                self.assertEqual(new['mode'], 'full')
                self.assertEqual(new['phase'], new_phase)
                self.assertEqual(new['call_chain']['prefilter']['mode'], 'on-demand')
                self.assertIsNone(new['call_chain']['prefilter']['decision'])
                self.assertEqual(new['artifacts']['call_chain_review'], str(state.parent / 'call-chain-review.md'))
                self.assertIsNone(new['build']['current_slice'])
                self.assertNotIn('fast', new)
                for key in ('fix_round', 'retries', 'review', 'preflight', 'aso_bindings', 'plan_path', 'limits'):
                    self.assertEqual(new[key], old[key])
                self.assertEqual(new['build']['commits'], old['build']['commits'])
                self.assertEqual({p: p.read_bytes() for p in evidence}, evidence)
                before = state.read_bytes()
                self.resume(state)
                self.assertEqual(state.read_bytes(), before)

    def test_resume_completed_or_invalid_runs_does_not_rewrite_history(self):
        state, _ = self.legacy_fast('finished-fast', 'DONE')
        Path(json.loads(state.read_text())['plan_path']).unlink()
        before = state.read_bytes()
        self.resume(state)
        self.assertEqual(state.read_bytes(), before)
        state, _ = self.legacy_fast('broken-fast', 'BUILD_FAST')
        Path(json.loads(state.read_text())['plan_path']).unlink()
        before = state.read_bytes()
        self.resume(state, success=False)
        self.assertEqual(state.read_bytes(), before)
        state = self.init_run('wrong-mode')
        data = json.loads(state.read_text())
        data['mode'] = 'fix'
        state.write_text(json.dumps(data))
        before = state.read_bytes()
        self.resume(state, success=False)
        self.assertEqual(state.read_bytes(), before)

    def test_resume_legacy_profile_retains_configured_progress(self):
        state, old = self.legacy_fast('profile-fast', 'FIX_FAST')
        profile = state.parent / 'profile.json'
        old['progress'] = {'events': str(state.parent / 'progress.events')}
        profile.write_text(json.dumps(old))
        before = profile.read_bytes()
        self.assertEqual(self.resume(profile).stdout.strip(), str(profile))
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(json.loads(state.read_text())['phase'], 'FIX')
        self.helper(profile, 'update_progress keel-builder FIX "继续修复"')
        self.assertTrue((state.parent / 'progress.events').is_file())

    def test_injected_progress_and_completion_protocol_keeps_all_public_tags(self):
        state = self.init_run('events')
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
        state = self.init_run('replaceable')
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
        state = self.init_run('callchain')
        self.helper(state, 'record_call_chain_skip', success=False)
        self.helper(state, 'record_call_chain_prefilter run "新增状态流转"')
        self.helper(state, 'record_call_chain_skip', success=False)
        (state.parent / 'call-chain-review.md').write_text('UPDATED\n状态及其证据')
        self.helper(state, 'record_call_chain_result updated "$3"', 'a' * 40)
        data = json.loads(state.read_text())
        self.assertEqual(data['phase'], 'DONE')
        self.assertEqual(data['call_chain']['action'], 'updated')
        self.assertEqual(data['call_chain']['commit'], 'a' * 40)
        shadow = self.init_run('shadow')
        self.helper(shadow, '_keel_state_jq \'.call_chain.prefilter.mode = "shadow"\'\nrecord_call_chain_prefilter noop "影子预判"\nrecord_call_chain_shadow_result updated')
        self.assertFalse(json.loads(shadow.read_text())['call_chain']['prefilter']['safe'])
        self.helper(shadow, 'record_call_chain_skip', success=False)

    def test_noop_finishes_without_call_chain_report(self):
        state = self.init_run('skip-call-chain')
        self.helper(state, 'record_call_chain_prefilter noop "仅局部校验，无入口或状态变化"\nrecord_call_chain_skip')
        data = json.loads(state.read_text())
        self.assertEqual(data['phase'], 'DONE')
        self.assertEqual(data['call_chain']['status'], 'skipped')
        self.assertIsNone(data['call_chain']['artifact'])
        self.assertFalse(Path(data['artifacts']['call_chain_review']).exists())

    def test_legacy_profile_uses_its_configured_progress_and_state(self):
        state = self.init_run('legacy')
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
