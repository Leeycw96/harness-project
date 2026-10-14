#!/usr/bin/env python3
"""Check ASO dependency boundaries, deployment and plan snapshot inputs."""
import json
from pathlib import Path
import re
import subprocess
import sys
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
ROLE_AGENTS = {'builder': 'builder', 'qa': 'qa', 'call-chain': 'doc-writer'}
AGENT_DIRS = {agent: AGENTS for agent in ROLE_AGENTS.values()} | {'planner': ROOT / 'keel-plan/agents'}
RETIRED_SPECS = {'keel-dev-spec.md', 'keel-qa-spec.md', 'keel-fix-spec.md',
                 'keel-plan-spec.md', 'keel-call-chain-spec.md', 'keel-work-spec.md'}
SPEC_FILES = {'keel-business-flow-spec.md', 'keel-code-change-spec.md'}
SCENARIO_SPECS = {'keel-delivery-spec.md', 'keel-code-quality-spec.md', 'keel-implementation-spec.md',
                  'keel-investigation-spec.md', 'keel-proposal-spec.md', 'keel-fix-review-spec.md',
                  'keel-acceptance-spec.md', 'keel-flow-index-spec.md', 'keel-bug-scope-spec.md',
                  'keel-document-writing-spec.md', 'keel-qa-scoring-spec.md'}
SPEC_FILES |= SCENARIO_SPECS


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
        result = self.shell('export PROJECT_DIR="$1"\nsource "$2"\ninit_keel_run "$3" "$4"', self.project, self.init, output, self.plan)
        plan = output / 'plan.md'
        self.assertEqual(result.stdout.strip(), str(plan))
        return plan

    def qa_score(self, plan, goals, retest=False):
        result = subprocess.run([sys.executable, str(self.project / '.codex/common/scripts/keel-qa-score.py'),
                                 'record', '-', '--output-dir', str(plan.parent),
                                 '--plan', str(plan),
                                 *(['--retest'] if retest else [])],
                                input=json.dumps({'goals': goals, 'checks': {'回归': 100}}),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(result.stdout.strip())

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
        # QA verdicts (APPROVED/REJECTED) are document standards;
        # Agent registration and task orchestration stay outside Spec.
        for name in SPEC_FILES:
            with self.subTest(spec=name):
                text = (REFS / name).read_text()
                self.assertNotRegex(text, r'keel-builder|keel-qa\.md|keel-(?:call-chain|doc-writer)\.md|\.codex/agents/|KEEL_PROFILE|state\.json|complete_stage|update_progress|\b(?:BUILD|REVIEW|FIX|PAUSED|PREFLIGHT)(?:_[A-Z]+)*\b')

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
        agent_roles = {'keel-' + agent: role for role, agent in ROLE_AGENTS.items()}
        for step, agent, spec_cell in rows:
            role = agent_roles[agent]
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
        fix_qa = self.read_reference('.agents/skills/keel-fix/SKILL.md#验收与返修').split('\n\n')[1]
        fix_specs = re.findall(r'\.codex/common/refs/[\w.-]+\.md(?:#[\w -]+)?', fix_qa)
        self.assertIn('.codex/common/refs/keel-qa-scoring-spec.md', fix_specs)
        effective_fix_specs = self.reachable_references(fix_specs)
        self.assertNotIn('.codex/common/refs/keel-implementation-spec.md', effective_fix_specs)

    def test_agent_input_is_task_and_named_specs_without_runtime_injection(self):
        contracts = [(DEV_SKILL, 'Agent 调度'),
                     ('.agents/skills/keel-fix/SKILL.md', 'Agent 调用'),
                     ('.agents/skills/keel-plan/SKILL.md', '调度')]
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
                self.assertRegex(contract, r'不(?:附|下发|把)[^\n。]*Skill')
                self.assertIn('主会话', contract)

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
            entries += ['.codex/agents/keel-call-chain.md', '.codex/agents/keel-call-chain.toml']
            entries += ['.codex/common/scripts/keel-common.sh']
            for entry in entries:
                path = project / entry
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('previous deployed instructions')
            manifest.write_text('\n'.join(entries) + '\n')
            user_file = project / '.codex/common/refs/project-notes.md'
            user_file.write_text('project-owned instructions')
            user_notes = project / '.agents/skills/keel-dev-fast/user-notes.md'
            user_notes.write_text('keep untracked user notes')
            history = project / '.keel/iterations/old/run-1'
            history.mkdir(parents=True)
            records = {history / 'state.json': 'historical user-owned state file',
                       history / 'profile.json': 'historical user-owned profile file'}
            for path, content in records.items():
                path.write_text(content)
            result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(project)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for entry in entries:
                self.assertFalse((project / entry).exists())
                self.assertNotIn(entry, manifest.read_text().splitlines())
            for name in SPEC_FILES:
                self.assertEqual((project / '.codex/common/refs' / name).read_bytes(), (REFS / name).read_bytes())
                self.assertIn('.codex/common/refs/' + name, manifest.read_text().splitlines())
            for suffix in ('md', 'toml'):
                name = 'keel-doc-writer.' + suffix
                self.assertEqual((project / '.codex/agents' / name).read_bytes(), (AGENTS / name).read_bytes())
                self.assertIn('.codex/agents/' + name, manifest.read_text().splitlines())
            config = tomllib.loads((project / '.codex/agents/keel-doc-writer.toml').read_text())
            self.assertEqual(config['name'], 'keel-doc-writer')
            self.assertEqual(user_file.read_text(), 'project-owned instructions')
            self.assertEqual(user_notes.read_text(), 'keep untracked user notes')
            for path, content in records.items():
                self.assertEqual(path.read_text(), content)

    def test_initialization_returns_a_self_contained_plan_without_runtime_state(self):
        plan = self.init_run('init-dev')
        source_features = self.plan.parent / 'plan-template.features'
        expected = {'plan.md'} | {
            str(Path('plan-template.features') / path.relative_to(source_features))
            for path in source_features.rglob('*') if path.is_file()
        }
        self.assertEqual({str(path.relative_to(plan.parent)) for path in plan.parent.rglob('*') if path.is_file()},
                         expected)
        self.assertEqual(plan.read_bytes(), self.plan.read_bytes())
        result = subprocess.run([sys.executable, str(self.project / '.codex/common/scripts/keel-plan.py'),
                                 'validate', str(plan)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.project / '.codex/common/scripts/keel-common.sh').exists())
        self.assertFalse((self.project / '.agents/skills/keel-dev-fast/SKILL.md').exists())

    def test_run_number_helpers_select_the_next_numeric_directory(self):
        output = self.project / 'run-numbers'
        for name in ('run-1', 'run-9', 'run-invalid', 'notes'):
            (output / name).mkdir(parents=True)
        result = self.shell('export PROJECT_DIR="$1"\nsource "$2"\nget_latest_run_number "$3"\nget_next_run_number "$3"\nget_next_run_number "$4"',
                            self.project, self.init, output, output / 'missing')
        self.assertEqual(result.stdout.splitlines(), ['9', '10', '1'])

    def test_qa_scoring_succeeds_without_generating_feedback_or_state(self):
        for retest in (False, True):
            with self.subTest(retest=retest):
                plan = self.init_run('approved-score-' + str(retest))
                feedback = plan.parent / 'qa-feedback.md'
                initial = None
                if retest:
                    initial = self.qa_score(plan, {'cancel-order': 100, 'confirm-refund': 0})
                    initial_bytes = initial.read_bytes()
                    feedback.write_text('REJECTED：初验退款未完成，保留原报告。')
                    previous_feedback = feedback.read_bytes()
                before_files = {path: path.read_bytes() for path in plan.parent.rglob('*') if path.is_file()}
                returned_score = self.qa_score(plan, {'cancel-order': 100, 'confirm-refund': 100}, retest)
                self.assertEqual(returned_score.name == 'qa-score.json', not retest)
                for path, content in before_files.items():
                    self.assertEqual(path.read_bytes(), content)
                if retest:
                    self.assertRegex(returned_score.name, r'^qa-score-retest-[0-9a-f]{12}\.json$')
                    self.assertNotEqual(returned_score, initial)
                    self.assertEqual(initial.read_bytes(), initial_bytes)
                    self.assertEqual(feedback.read_bytes(), previous_feedback)
                else:
                    self.assertFalse(feedback.exists())
                self.assertFalse((plan.parent / 'state.json').exists())
                self.assertFalse((plan.parent / 'profile.json').exists())

    def test_custom_agent_and_spec_survive_redeployment(self):
        with tempfile.TemporaryDirectory(prefix='keel-custom-role-') as work:
            project = Path(work)
            result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(project)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            role_paths = list((project / '.codex/agents').glob('*'))
            roles = {path: path.read_bytes() for path in role_paths}
            custom = {
                project / '.codex/agents/alternate-builder.toml':
                    'name = "alternate-builder"\ndeveloper_instructions = "依据注入目标与规范完成实现并报告证据。"\n',
                project / '.codex/common/refs/alternate-spec.md':
                    '使用本项目配置的验证工具，遵守已授权的交付范围。\n',
            }
            for path, content in custom.items():
                path.write_text(content)
            result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(project)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({path: path.read_bytes() for path in role_paths}, roles)
            for path, content in custom.items():
                self.assertEqual(path.read_text(), content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
