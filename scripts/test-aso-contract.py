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
DEV_SKILL = '.agents/skills/keel-dev/SKILL.md'
ROLE_STEPS = {'builder': '实现', 'qa': '验收', 'call-chain': '流程维护'}
ROLE_SPECS = {'builder': 'keel-implementation-spec.md', 'qa': 'keel-acceptance-spec.md',
              'call-chain': 'keel-flow-index-spec.md'}
AGENT_DIRS = {role: AGENTS for role in ROLE_STEPS} | {'planner': ROOT / 'keel-plan/agents'}
RETIRED_SPECS = {'keel-dev-spec.md', 'keel-qa-spec.md', 'keel-fix-spec.md',
                 'keel-plan-spec.md', 'keel-call-chain-spec.md', 'keel-work-spec.md'}
SPEC_FILES = {'keel-business-flow-spec.md', 'keel-code-change-spec.md'}
SCENARIO_SPECS = {'keel-delivery-spec.md', 'keel-code-quality-spec.md', 'keel-implementation-spec.md',
                  'keel-investigation-spec.md', 'keel-proposal-spec.md', 'keel-fix-review-spec.md',
                  'keel-acceptance-spec.md', 'keel-flow-index-spec.md', 'keel-bug-scope-spec.md',
                  'keel-document-writing-spec.md', 'keel-qa-scoring-spec.md'}
SPEC_FILES |= SCENARIO_SPECS
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
        # Artifact verdicts (APPROVED/REJECTED, NOOP/UPDATED) are document standards;
        # agent registration, runtime state and stage control belong to orchestration.
        for name in SPEC_FILES:
            with self.subTest(spec=name):
                text = (REFS / name).read_text()
                self.assertNotRegex(text, r'keel-builder|keel-qa\.md|keel-call-chain\.md|\.codex/agents/|KEEL_PROFILE|state\.json|complete_stage|update_progress|\b(?:BUILD|REVIEW|FIX|PAUSED|PREFLIGHT)(?:_[A-Z]+)*\b')

    def test_specs_do_not_prescribe_execution_or_permissions(self):
        # Guard the operation clauses removed in this revision, without banning artifact terminology.
        operational_clause = re.compile(r'^- (?:运行|执行)[ \t]+(?:`|python3\b|bash\b|source\b)|^- (?:只可写|可读取|只改并提交)|^## (?:操作约束|工作与资料边界)$', re.M)
        for name in SPEC_FILES:
            with self.subTest(spec=name):
                text = (REFS / name).read_text()
                self.assertIsNone(operational_clause.search(text), name)
                self.assertNotIn('python3 .codex/common/scripts/keel-qa-score.py record', text)

    def spec_metadata(self, path):
        header = re.match(r'\A---\n(.*?)\n---(?:\n|\Z)', path.read_text(), re.S)
        self.assertIsNotNone(header, str(path))
        fields = {}
        for key, value in re.findall(r'^(name|description):[ \t]*(.*)$', header[1], re.M):
            self.assertNotIn(key, fields, str(path))
            self.assertTrue(value.strip().strip('\'"').strip(), str(path) + ': ' + key)
            fields[key] = value.strip()
        self.assertEqual(set(fields), {'name', 'description'}, str(path))
        return fields, header[0]

    def test_specs_have_unique_metadata_preserved_by_deployment(self):
        names = set()
        for source in sorted(REFS.glob('*-spec.md')):
            with self.subTest(spec=source.name):
                metadata, header = self.spec_metadata(source)
                self.assertNotIn(metadata['name'], names, source.name)
                names.add(metadata['name'])
                deployed_metadata, deployed_header = self.spec_metadata(self.refs / source.name)
                self.assertEqual(deployed_metadata, metadata)
                self.assertEqual(deployed_header, header)

    def reachable_references(self, roots):
        roots = list(roots)
        seen = set()
        while roots:
            reference = roots.pop().strip()
            if reference in seen:
                continue
            seen.add(reference)
            text = self.read_reference(reference)
            roots.extend(re.findall(r'\.(?:codex|agents)/[\w/.-]+\.(?:md|sh|py)(?:#[\w -]+)?', text))
        return seen

    def test_scenario_specs_do_not_depend_on_retired_entries(self):
        for name in SCENARIO_SPECS:
            with self.subTest(spec=name):
                text = (REFS / name).read_text()
                targets = re.findall(r'\.codex/common/refs/([\w.-]+\.md)', text)
                self.assertTrue(RETIRED_SPECS.isdisjoint(targets), name)

    def test_deployed_orchestration_resource_graph_is_complete(self):
        roots = ['.agents/skills/keel-dev/SKILL.md',
                 '.agents/skills/keel-fix/SKILL.md', '.agents/skills/keel-plan/SKILL.md']
        seen = self.reachable_references(roots)
        for entry in ('.agents/skills/keel-plan/SKILL.md', '.agents/skills/keel-dev/SKILL.md'):
            self.assertIn('.codex/common/refs/keel-business-flow-spec.md', self.reachable_references([entry]))
        for name in SPEC_FILES:
            self.assertIn('.codex/common/refs/' + name, {reference.partition('#')[0] for reference in seen})
        self.assertTrue(RETIRED_SPECS.isdisjoint({Path(reference.partition('#')[0]).name for reference in seen}))
        self.assertFalse(any(re.search(r'/SKILL\.md#', reference) for reference in seen))
        self.assertIn('.agents/skills/keel-fix/scripts/keel-fix.py', seen)
        self.assertIn('.codex/common/scripts/keel-qa-score.py', seen)
        self.assertIn('.agents/skills/keel-fix/assets/bug-template.md', seen)
        self.assertIn('.agents/skills/keel-fix/assets/investigation-template.md', seen)
        self.assertIn('.agents/skills/keel-plan/assets/incremental-example.md', seen)
        self.assertEqual({p.name for p in self.refs.iterdir()}, SPEC_FILES)

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
                    ('.codex/common/refs/keel-proposal-spec.md', 'common/refs/keel-proposal-spec.md'),
                    ('.codex/common/refs/keel-document-writing-spec.md', 'common/refs/keel-document-writing-spec.md'),
                    ('.codex/common/refs/keel-qa-scoring-spec.md', 'common/refs/keel-qa-scoring-spec.md'),
                    ('.codex/common/scripts/keel-qa-score.py', 'common/scripts/keel-qa-score.py'),
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

    def test_default_bindings_route_each_role_directly_to_scenario_specs(self):
        main = self.read_reference(DEV_SKILL + '#角色与规范')
        rows = re.findall(r'^\| (实现|验收|流程维护) \| (keel-[\w-]+) \| ([^|]+) \|$', main, re.M)
        self.assertEqual(len(rows), 3)
        for step, agent, spec_cell in rows:
            role = agent.removeprefix('keel-')
            self.assertEqual(step, ROLE_STEPS[role])
            spec_refs = re.findall(r'\.codex/common/refs/[\w.-]+\.md(?:#[\w -]+)?', spec_cell)
            self.assertTrue(spec_refs, spec_cell)
            self.assertIn(ROLE_SPECS[role], {Path(reference.partition('#')[0]).name for reference in spec_refs})
            self.assertIn('.codex/common/refs/keel-document-writing-spec.md', spec_refs)
            effective = self.reachable_references(spec_refs)
            effective_files = {Path(reference.partition('#')[0]).name for reference in effective}
            self.assertTrue(RETIRED_SPECS.isdisjoint(effective_files))
            self.assertIn('keel-delivery-spec.md', effective_files)
            if role in {'builder', 'qa'}:
                self.assertIn('keel-code-quality-spec.md', effective_files)
            if role == 'qa':
                self.assertIn('.codex/common/refs/keel-qa-scoring-spec.md', spec_refs)
                self.assertNotIn('keel-implementation-spec.md', effective_files)
            for reference in spec_refs:
                self.read_reference(reference)
                metadata, _ = self.spec_metadata(self.project / reference.partition('#')[0])
                self.assertIn(metadata['name'], spec_cell)
            self.assertTrue((self.project / '.codex/agents' / (agent + '.toml')).is_file())
        for tag, (role, _, _) in TAGS.items():
            self.assertIn(tag, self.read_reference(DEV_SKILL + '#' + ROLE_STEPS[role]))
        fix_qa = self.read_reference('.agents/skills/keel-fix/SKILL.md#验收与返修').split('\n\n')[1]
        fix_specs = re.findall(r'\.codex/common/refs/[\w.-]+\.md(?:#[\w -]+)?', fix_qa)
        self.assertIn('.codex/common/refs/keel-qa-scoring-spec.md', fix_specs)
        effective_fix_specs = self.reachable_references(fix_specs)
        self.assertNotIn('.codex/common/refs/keel-implementation-spec.md', effective_fix_specs)

    def test_agent_input_is_task_and_named_specs_without_runtime_injection(self):
        contracts = [(DEV_SKILL, '运行衔接'),
                     ('.agents/skills/keel-fix/SKILL.md', '运行衔接'),
                     ('.agents/skills/keel-plan/SKILL.md', '调度与恢复')]
        for skill, heading in contracts:
            with self.subTest(skill=skill):
                text = self.read_reference(skill)
                contract = self.read_reference(skill + '#' + heading)
                inputs = re.findall(r'^- \*\*(.+?)\*\*：(.+)$', contract, re.M)
                self.assertEqual([label for label, _ in inputs], ['任务', 'Spec'])
                for _, definition in inputs:
                    self.assertNotRegex(definition, r'KEEL_PROFILE|\b(?:stage|artifact|tag|reporter|task_ref)\b|SKILL\.md|运行衔接|complete_stage|update_progress')
                self.assertIn('name', inputs[1][1])
                self.assertIn('绝对路径', inputs[1][1])
                self.assertIn('#二级标题', inputs[1][1])
                self.assertNotRegex(text, r'\.agents/skills/[\w-]+/SKILL\.md#')
                self.assertNotRegex(contract, r'Agent[^\n。]*(?:导出 KEEL_PROFILE|source |export |complete_stage|update_progress)')
                self.assertRegex(contract, r'不(?:附|下发)[^\n。]*Skill')
                if heading == '运行衔接':
                    self.assertIn('忽略旧 task_ref', contract)
                    self.assertIn('主会话', contract)
                    self.assertIn('进展通过原生消息跟进，不另存进度文件', contract)
                    self.assertIn('complete_stage', contract)
                    self.assertIn('Agent 不调用运行助手或修改运行状态', contract)

    def test_fix_investigation_has_readonly_task_and_output_specs(self):
        text = self.read_reference('.agents/skills/keel-fix/SKILL.md#接收与定位')
        dispatch = text.split('\n\n')[1]
        refs = re.findall(r'\.codex/common/refs/[\w.-]+\.md(?:#[\w -]+)?', dispatch)
        self.assertEqual(set(refs), {'.codex/common/refs/keel-delivery-spec.md',
                                     '.codex/common/refs/keel-investigation-spec.md',
                                     '.codex/common/refs/keel-bug-scope-spec.md#分类结论',
                                     '.codex/common/refs/keel-document-writing-spec.md'})
        effective = self.reachable_references(refs)
        names = {Path(reference.partition('#')[0]).name for reference in effective}
        self.assertNotIn('keel-implementation-spec.md', names)
        self.assertTrue(RETIRED_SPECS.isdisjoint(names))
        self.assertIn('只读问题调查', dispatch)
        style = (AGENTS / 'keel-builder.md').read_text()
        self.assertIn('只读调查', style)
        self.assertIn('不改代码、测试、配置或数据', style)

    def test_plan_research_and_drafting_use_distinct_proposal_scope(self):
        research = self.read_reference('.agents/skills/keel-plan/SKILL.md#调研')
        self.assertIn('.codex/common/refs/keel-proposal-spec.md#调研结果', research)
        self.assertIn('.codex/common/refs/keel-document-writing-spec.md', research)
        self.assertNotRegex(research, r'keel-proposal-spec\.md`|keel-proposal-spec\.md[）)]')
        drafting = self.read_reference('.agents/skills/keel-plan/SKILL.md#起草与修订')
        self.assertIn('.codex/common/refs/keel-proposal-spec.md`', drafting)
        self.assertIn('.codex/common/refs/keel-code-change-spec.md', drafting)
        # Drafting inherits the writing spec already declared for research.
        self.assertRegex(drafting, r'沿用调研步骤[^。\n]*文档表达 Spec')

    def test_redeployment_removes_retired_files_but_preserves_user_files(self):
        with tempfile.TemporaryDirectory(prefix='keel-upgrade-') as work:
            project = Path(work)
            retired = ['keel-dev-coding-rules.md', 'keel-call-chain-rules.md',
                       'keel-dev-environment.md', 'keel-dev-task-protocol.md',
                       'tasks/implement.md', 'tasks/verify.md', 'tasks/maintain-flow.md',
                       'keel-dev-orchestration.md', *sorted(RETIRED_SPECS)]
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
            for name in SPEC_FILES:
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
        self.assertNotIn('progress', data)
        self.assertFalse((state.parent / 'progress.tsv').exists())
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
        data['aso_bindings'] = {'builder': {'agent': 'custom-builder', 'spec_refs': ['custom.md'],
                                          'task_ref': str(self.project / DEV_SKILL) + '#实现'}}
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

    def test_resume_legacy_profile_preserves_history_without_creating_progress_events(self):
        state, old = self.legacy_fast('profile-fast', 'FIX_FAST')
        profile = state.parent / 'profile.json'
        old['progress'] = {'events': str(state.parent / 'progress.events')}
        profile.write_text(json.dumps(old))
        before = profile.read_bytes()
        self.assertEqual(self.resume(profile).stdout.strip(), str(profile))
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(json.loads(state.read_text())['phase'], 'FIX')
        old_progress = (state.parent / 'progress.tsv').read_bytes()
        self.helper(profile, 'update_progress keel-builder FIX "继续修复"')
        self.assertFalse((state.parent / 'progress.events').exists())
        self.assertEqual((state.parent / 'progress.tsv').read_bytes(), old_progress)
        self.assertEqual(profile.read_bytes(), before)

    def test_progress_helpers_return_public_tags_without_writing_runtime_files(self):
        state = self.init_run('events')
        data = json.loads(state.read_text())
        data.update(phase='REVIEW_FIX', fix_round=2, retries={'keel-qa': 2})
        state.write_text(json.dumps(data))
        original_state = state.read_bytes()
        for _, (_, _, artifact_name) in TAGS.items():
            artifact = state.parent / artifact_name
            if not artifact.exists():
                artifact.write_text('current task evidence')
        original_files = {p: p.read_bytes() for p in state.parent.rglob('*') if p.is_file()}
        for tag, (role, stage, artifact_name) in TAGS.items():
            artifact = state.parent / artifact_name
            result = self.helper(state, 'update_progress "$3" "$4" "正在执行" "$5"\ncomplete_stage "$3" "$6" "已完成" "$5"', 'keel-' + role, stage, artifact, tag)
            self.assertEqual(result.stdout.splitlines(), [
                f'keel-{role} | {stage} | 正在执行 | artifact: {artifact}',
                f'{tag} | 已完成 | artifact: {artifact}',
            ])
        # Compatibility output is distinct from the main session's verdict and state transition.
        self.assertEqual(state.read_bytes(), original_state)
        self.helper(state, 'complete_stage keel-qa APPROVED "不能通过" "$3"', state.parent / 'missing.md', success=False)
        self.assertEqual(state.read_bytes(), original_state)
        self.assertEqual({p: p.read_bytes() for p in state.parent.rglob('*') if p.is_file()}, original_files)

    def test_progress_output_requires_no_runtime_profile_and_keeps_argument_guards(self):
        result = self.shell('unset KEEL_PROFILE\nsource "$1"\nupdate_progress builder BUILD "正在执行"\ncomplete_stage keel-builder BUILD_DONE "已完成"', self.helpers)
        self.assertEqual(result.stdout.splitlines(), ['keel-builder | BUILD | 正在执行', 'BUILD_DONE | 已完成'])
        for command in ('update_progress "" BUILD "正在执行"', 'complete_stage keel-builder "" "已完成"'):
            with self.subTest(command=command):
                self.shell('unset KEEL_PROFILE\nsource "$1"\n' + command, self.helpers, success=False)

    def test_old_completion_logs_and_missing_return_cannot_complete_call_chain(self):
        state = self.init_run('missing-call-chain-return')
        self.helper(state, '_keel_state_jq \'.phase = "CALL_CHAIN" | .fix_round = 2 | .retries = {"keel-call-chain": 2}\'\nrecord_call_chain_prefilter run "状态流转发生变化"')
        log = state.parent / 'progress.tsv'
        log.write_text('old\tcomplete\tkeel-call-chain\tCALL_CHAIN_UPDATED\t历史完成记录\n')
        self.assertEqual(self.resume(state).stdout.strip(), str(state))
        before = state.read_bytes()
        old_log = log.read_bytes()
        report = state.parent / 'call-chain-review.md'
        # The main session validates the returned report before recording completion and the result.
        command = 'complete_stage keel-call-chain CALL_CHAIN_UPDATED "已核验流程报告" "$3"\nrecord_call_chain_result updated'
        self.helper(state, command, report, success=False)
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(log.read_bytes(), old_log)
        self.assertNotEqual(json.loads(state.read_text())['call_chain']['status'], 'completed')
        # The updated document is deliberately uncommitted, in a project without a Git repository.
        self.assertFalse((self.project / '.git').exists())
        document = self.project / '.keel/call-chain/order-lifecycle.md'
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text('订单生命周期\n已补充退款确认状态与代码依据。')
        report.write_text('UPDATED\n已更新 .keel/call-chain/order-lifecycle.md；状态变化有实际代码依据。')
        self.helper(state, command, report)
        after = json.loads(state.read_text())
        self.assertEqual(after['phase'], 'DONE')
        self.assertEqual(after['call_chain']['status'], 'completed')
        self.assertEqual(after['call_chain']['artifact'], str(report))
        self.assertIsNone(after['call_chain']['commit'])
        self.assertTrue(document.is_file())
        self.assertEqual(after['fix_round'], 2)
        self.assertEqual(after['retries'], {'keel-call-chain': 2})
        self.assertEqual(log.read_bytes(), old_log)

    def test_call_chain_commit_metadata_is_optional(self):
        cases = [('noop', None), ('updated', None), ('updated', 'b' * 40)]
        for number, (action, commit) in enumerate(cases):
            with self.subTest(action=action, commit=commit):
                state = self.init_run('optional-commit-' + str(number))
                self.helper(state, 'record_call_chain_prefilter run "核实受影响流程"')
                (state.parent / 'call-chain-review.md').write_text(action.upper() + '\n文档与代码证据已核对。')
                command = 'record_call_chain_result "$3"'
                args = [action]
                if commit is not None:
                    command += ' "$4"'
                    args.append(commit)
                self.helper(state, command, *args)
                data = json.loads(state.read_text())
                self.assertEqual(data['phase'], 'DONE')
                self.assertEqual(data['call_chain']['action'], action)
                self.assertEqual(data['call_chain']['commit'], commit)

    def test_invalid_optional_call_chain_commit_does_not_change_state(self):
        state = self.init_run('invalid-optional-commit')
        self.helper(state, 'record_call_chain_prefilter run "核实受影响流程"')
        before = state.read_bytes()
        self.helper(state, 'record_call_chain_result updated "$3"', 'invalid-sha', success=False)
        self.assertEqual(state.read_bytes(), before)

    def test_replaceable_bindings_survive_state_updates_without_role_edits(self):
        state = self.init_run('replaceable')
        role_paths = list((self.project / '.codex/agents').glob('*'))
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in role_paths}
        spec = self.project / 'alternate-spec.md'
        spec.write_text('使用本项目配置的验证工具，遵守已授权的交付范围。')
        (self.project / '.codex/agents/alternate-builder.toml').write_text(
            'name = "alternate-builder"\ndeveloper_instructions = "依据注入目标与规范完成实现并报告证据。"\n')
        bindings = {'builder': {'agent': 'alternate-builder', 'spec_refs':[str(spec)]}}
        self.helper(state, '_keel_state_jq --argjson bindings "$3" \'.aso_bindings = $bindings\'\nrecord_call_chain_prefilter noop "仅局部校验"\nrecord_call_chain_skip', json.dumps(bindings))
        self.assertEqual(json.loads(state.read_text())['aso_bindings'], bindings)
        self.assertEqual(set(bindings['builder']), {'agent', 'spec_refs'})
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

    def test_legacy_profile_updates_state_without_modifying_configured_progress(self):
        state = self.init_run('legacy')
        profile = state.parent / 'profile.json'
        old = json.loads(state.read_text())
        old['progress'] = {'events':str(state.parent / 'progress.events')}
        profile.write_text(json.dumps(old))
        events = state.parent / 'progress.events'
        events.write_text('historical progress\n')
        before_profile, before_events = profile.read_bytes(), events.read_bytes()
        before_paths = {p for p in state.parent.rglob('*') if p.is_file()}
        result = self.helper(profile, 'keel_state_file\nupdate_progress keel-builder BUILD "恢复"\ncomplete_stage keel-builder BUILD_DONE "已完成"\nrecord_call_chain_prefilter noop "无变化"')
        self.assertIn(str(state), result.stdout)
        self.assertEqual(profile.read_bytes(), before_profile)
        self.assertEqual(events.read_bytes(), before_events)
        self.assertEqual({p for p in state.parent.rglob('*') if p.is_file()}, before_paths)
        self.assertFalse((state.parent / 'progress.tsv').exists())
        self.assertEqual(json.loads(state.read_text())['call_chain']['prefilter']['decision'], 'noop')


if __name__ == '__main__':
    unittest.main(verbosity=2)
