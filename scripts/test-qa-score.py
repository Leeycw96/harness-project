#!/usr/bin/env python3
"""Exercise compact item scores, immutable reviews and legacy history."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'common/scripts/keel-qa-score.py'
ASSETS = ROOT / 'keel-plan/skills/keel-plan/assets'


class QaScoreTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='keel-qa-score-test-')
        self.project = Path(self.work.name).resolve()
        self.plan = self.project / 'plan.md'
        shutil.copyfile(ASSETS / 'plan-template.md', self.plan)
        shutil.copytree(ASSETS / 'plan-template.features', self.project / 'plan-template.features')
        self.fix = self.project / 'approved.md'
        shutil.copyfile(ROOT / 'keel-dev/skills/keel-fix/assets/bug-template.md', self.fix)
        self.input = self.project / 'qa-input.json'

    def tearDown(self):
        self.work.cleanup()

    def cli(self, *args, success=True, stdin=None):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                input=stdin, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def payload(self):
        return {'goals': {'cancel-order': 100, 'confirm-refund': 0},
                'checks': {'重复申请': 100, '失败回调': 0, '现场复验': 0}}

    def legacy_payload(self):
        return {'schema_version': 1, 'project': '旧项目', 'builder': 'Builder A',
                'review': 'initial', 'verdict': 'REJECTED', 'blockers': ['退款未完成'],
                'commits': ['a' * 40], 'limitations': ['等待现场确认'],
                'goal_results': [
                    {'id': 'cancel-order', 'status': 'passed',
                     'evidence': ['验收报告#取消申请'], 'reason': ''},
                    {'id': 'confirm-refund', 'status': 'failed',
                     'evidence': ['验收报告#退款失败'], 'reason': ''}],
                'checks': [{'name': '业务检查', 'items': [
                    {'name': '重复申请', 'status': 'passed', 'evidence': ['检查报告'], 'reason': ''},
                    {'name': '现场复验', 'status': 'unverified', 'evidence': [], 'reason': '环境不可用'}]}]}

    def legacy_record(self, name='legacy', review='initial'):
        core = self.legacy_payload()
        core['review'] = review
        core['source'] = {'kind': 'plan', 'path': str(self.plan), 'sha256': 'b' * 64,
                          'catalog': [{'id': 'cancel-order', 'target': '取消订单'},
                                      {'id': 'confirm-refund', 'target': '确认退款'}]}
        fingerprint = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest()
        record = {**core, 'recorded_at': '2026-01-01T00:00:00+00:00', 'data_sha256': fingerprint,
                  'goal_score': {'completed': 1, 'total': 2, 'failed': 1, 'unverified': 0, 'percent': 50},
                  'check_scores': [{'name': '业务检查', 'completed': 1, 'total': 2,
                                    'failed': 0, 'unverified': 1, 'percent': 50}]}
        directory = self.project / name
        directory.mkdir(parents=True, exist_ok=True)
        filename = 'qa-score.json' if review == 'initial' else 'qa-score-retest-123456789abc.json'
        path = directory / filename
        path.write_text(json.dumps(record, ensure_ascii=False))
        return path

    def record(self, payload, name='run-1', scope='plan', success=True, stdin=False, retest=False):
        output = self.project / name
        self.input.write_text(json.dumps(payload, ensure_ascii=False))
        source_args = [] if scope is None else ['--' + scope, self.plan if scope == 'plan' else self.fix]
        result = self.cli('record', '-' if stdin else self.input, '--output-dir', output,
                          *source_args, *(['--retest'] if retest else []), success=success,
                          stdin=json.dumps(payload, ensure_ascii=False) if stdin else None)
        return output, result

    def score(self, output):
        return json.loads((output / 'qa-score.json').read_text())

    def history(self, directory=None, *args):
        return json.loads(self.cli('history', directory or self.project, *args, '--json').stdout)

    def test_minimal_input_produces_only_item_scores(self):
        payload = self.payload()
        output, result = self.record(payload, stdin=True)
        self.assertEqual(result.stdout.strip(), str(output / 'qa-score.json'))
        self.assertEqual(self.score(output), payload)
        self.assertEqual(set(output.iterdir()), {output / 'qa-score.json'})
        record = self.history()['records'][0]
        self.assertEqual(record['goal_score'], {'completed': 1, 'total': 2, 'percent': 50})
        self.assertEqual(record['check_scores'][0]['completed'], 1)
        self.assertEqual(record['check_scores'][0]['total'], 3)
        self.assertNotIn('verdict', record)

    def test_missing_goals_are_zero_and_do_not_shrink_denominator(self):
        payload = self.payload()
        del payload['goals']['confirm-refund']
        output, _ = self.record(payload)
        self.assertEqual(self.score(output)['goals'], self.payload()['goals'])
        self.assertEqual(self.history()['records'][0]['goal_score']['percent'], 50)
        output, _ = self.record({'goals': {}, 'checks': {}}, name='no-goals-reported')
        self.assertEqual(self.score(output)['goals'], {'cancel-order': 0, 'confirm-refund': 0})

    def test_check_only_and_empty_records_need_no_source(self):
        for index, payload in enumerate(({'checks': {'接口约定': 100}}, {})):
            with self.subTest(payload=payload):
                output, _ = self.record(payload, name='check-only-' + str(index), scope=None)
                self.assertEqual(self.score(output), {'goals': {}, 'checks': payload.get('checks', {})})
                record = self.history(output)['records'][0]
                self.assertIsNone(record['goal_score'])
                self.assertEqual(record['source']['kind'], 'none')
        self.assertIn('目标未评分', self.cli('history', output).stdout)

    def test_fix_uses_one_goal_and_does_not_require_plan_or_runtime_state(self):
        self.fix.write_text(self.fix.read_text() + '\n```python\n# 代码注释不是修复标题\namount = 9\n```\n')
        for value in (0, 100):
            with self.subTest(value=value):
                output, _ = self.record({'goals': {'bug': value}, 'checks': {}},
                                        name='fix-' + str(value), scope='fix')
                self.assertEqual(self.score(output), {'goals': {'bug': value}, 'checks': {}})
                self.assertEqual(self.history(output)['records'][0]['goal_score']['percent'], value)
                self.assertFalse((output / 'state.json').exists())
        output, _ = self.record({}, name='fix-omitted', scope='fix')
        self.assertEqual(self.score(output)['goals'], {'bug': 0})

    def test_invalid_scores_names_and_extra_metadata_are_rejected(self):
        invalid = [{'goals': {'cancel-order': value}} for value in (True, 100.0, '100', -1, 1, 101, None)]
        invalid += [{'checks': {'接口': value}} for value in (False, 0.0, '0', None)]
        invalid += [{'goals': []}, {'checks': []}, {'checks': {' ': 100}},
                    {'goals': {'cancel-order': 100}, 'reason': '多余说明'}]
        for payload in invalid:
            with self.subTest(payload=payload):
                output, _ = self.record(payload, name='invalid-format', success=False)
                self.assertFalse((output / 'qa-score.json').exists())

    def test_unknown_duplicate_and_unsourced_goals_are_rejected(self):
        for payload, scope in (({'goals': {'unknown': 100}}, 'plan'),
                               (self.payload(), None),
                               ({'checks': {'接口': 100, ' 接口 ': 0}}, None)):
            with self.subTest(payload=payload):
                output, _ = self.record(payload, name='invalid-goal', scope=scope, success=False)
                self.assertFalse((output / 'qa-score.json').exists())
        output = self.project / 'duplicate-json'
        self.cli('record', '-', '--output-dir', output, success=False,
                 stdin='{"goals":{},"checks":{"重复申请":100,"重复申请":0}}')
        self.assertFalse((output / 'qa-score.json').exists())

    def test_initial_score_is_immutable_and_retests_have_separate_files(self):
        initial = self.payload()
        output, _ = self.record(initial)
        first = (output / 'qa-score.json').read_bytes()
        self.record(copy.deepcopy(initial))
        self.assertEqual((output / 'qa-score.json').read_bytes(), first)
        changed = copy.deepcopy(initial)
        changed['goals']['confirm-refund'] = 100
        self.record(changed, success=False)
        self.assertEqual((output / 'qa-score.json').read_bytes(), first)
        self.record(changed, retest=True)
        retests = list(output.glob('qa-score-retest-*.json'))
        self.assertEqual(len(retests), 1)
        self.assertEqual(json.loads(retests[0].read_text()), changed)
        self.record(copy.deepcopy(changed), retest=True)
        self.assertEqual(list(output.glob('qa-score-retest-*.json')), retests)
        self.record(initial, retest=True)
        self.assertEqual(len(list(output.glob('qa-score-retest-*.json'))), 2)
        self.assertEqual((output / 'qa-score.json').read_bytes(), first)
        self.assertEqual(len(self.history()['records']), 1)
        self.assertEqual(len(self.history(None, '--include-retests')['records']), 3)

    def test_legacy_input_converts_to_scores_without_explanations(self):
        payload = self.legacy_payload()
        output, _ = self.record(payload, name='legacy-input')
        self.assertEqual(self.score(output), {'goals': self.payload()['goals'],
                                             'checks': {'业务检查/重复申请': 100, '业务检查/现场复验': 0}})
        payload['review'] = 'retest'
        self.record(payload, name='legacy-input')
        self.assertEqual(len(list(output.glob('qa-score-retest-*.json'))), 1)

    def test_legacy_input_with_no_results_still_scores_confirmed_goals_zero(self):
        for scope, expected in (('plan', {'cancel-order': 0, 'confirm-refund': 0}),
                                ('fix', {'bug': 0})):
            with self.subTest(scope=scope):
                payload = self.legacy_payload()
                payload['goal_results'] = None
                output, _ = self.record(payload, name='legacy-omitted-' + scope, scope=scope)
                self.assertEqual(self.score(output)['goals'], expected)

    def test_legacy_check_names_that_collide_when_flattened_are_rejected(self):
        payload = self.legacy_payload()
        item = payload['checks'][0]['items'][0]
        payload['checks'] = [{'name': '业务/接口', 'items': [{**item, 'name': '重复申请'}]},
                             {'name': '业务', 'items': [{**item, 'name': '接口/重复申请'}]}]
        output, result = self.record(payload, name='legacy-duplicate', success=False)
        self.assertIn('检查项重复', result.stderr)
        self.assertFalse((output / 'qa-score.json').exists())

    def test_legacy_history_and_builder_filter_remain_readable(self):
        legacy = self.legacy_record()
        self.legacy_record(review='retest')
        self.record(self.payload(), name='current')
        history = self.history()
        self.assertEqual(len(history['records']), 2)
        self.assertEqual(history['errors'], [])
        filtered = self.history(None, '--builder', 'Builder A', '--include-retests')
        self.assertEqual(len(filtered['records']), 2)
        self.assertTrue(all(record['builder'] == 'Builder A' for record in filtered['records']))
        self.assertEqual({record['review'] for record in filtered['records']}, {'initial', 'retest'})
        self.plan.unlink()
        self.assertEqual(len(self.history(legacy.parent)['records']), 1)
        output, _ = self.record({'checks': {}}, name='legacy', scope=None, success=False)
        self.assertEqual(output, legacy.parent)
        self.assertIn('schema_version', json.loads(legacy.read_text()))

    def test_invalid_legacy_and_compact_history_are_reported(self):
        path = self.legacy_record()
        record = json.loads(path.read_text())
        record['goal_score']['percent'] = 100
        path.write_text(json.dumps(record))
        output, _ = self.record(self.payload(), name='invalid-current')
        (output / 'qa-score.json').write_text('{"goals":{},"checks":{"接口":99}}')
        history = self.history()
        self.assertEqual(history['records'], [])
        self.assertEqual(history['summary'], [])
        self.assertEqual(len(history['errors']), 2)

    def test_history_infers_context_and_uses_file_time_for_recent_records(self):
        path = self.project / '.keel/iterations/feature/run-1'
        output, _ = self.record(self.payload(), name=str(path))
        os.utime(output / 'qa-score.json', (1_700_000_000, 1_700_000_000))
        bug_path = self.project / '.keel/bugs/refund/run-1'
        self.record({'goals': {'bug': 100}}, name=str(bug_path), scope='fix')
        history = self.history(None, '--last', 100)
        self.assertEqual(len(history['records']), 2)
        self.assertEqual(history['records'][0]['source']['kind'], 'fix')
        self.assertEqual(history['records'][1]['source']['kind'], 'plan')
        self.assertTrue(all(record['project'] == str(self.project) for record in history['records']))
        self.assertTrue(all(record['builder'] == 'unknown' for record in history['records']))
        recent = self.history(None, '--last', 1)
        self.assertEqual(len(recent['records']), 1)
        self.assertEqual(recent['records'][0]['source']['kind'], 'fix')
        self.assertEqual(len(history['summary']), 2)

    def test_record_and_history_never_read_or_modify_runtime_state(self):
        output = self.project / '.keel/iterations/test/run-1'
        output.mkdir(parents=True)
        originals = {}
        for name in ('state.json', 'profile.json'):
            path = output / name
            path.write_bytes(b'invalid state must not be parsed\xff')
            originals[path] = path.read_bytes()
        self.record(self.payload(), name=str(output))
        self.assertEqual(len(self.history()['records']), 1)
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        self.plan.unlink()
        self.assertEqual(len(self.history()['records']), 1)

    def test_deployed_cli_records_minimal_scores_with_its_shared_parser(self):
        deployed = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(self.project)],
                                  capture_output=True, text=True)
        self.assertEqual(deployed.returncode, 0, deployed.stderr)
        script = self.project / '.codex/common/scripts/keel-qa-score.py'
        self.input.write_text(json.dumps(self.payload(), ensure_ascii=False))
        output = self.project / '.keel/iterations/test/run-1'
        recorded = subprocess.run([sys.executable, str(script), 'record', str(self.input),
                                   '--output-dir', str(output), '--plan', str(self.plan)],
                                  capture_output=True, text=True)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(self.score(output), self.payload())
        viewed = subprocess.run([sys.executable, str(script), 'history', str(self.project), '--json'],
                                capture_output=True, text=True)
        self.assertEqual(viewed.returncode, 0, viewed.stderr)
        self.assertEqual(len(json.loads(viewed.stdout)['records']), 1)

    def test_unscored_old_reports_are_not_given_zero_or_full_marks(self):
        directory = self.project / 'old-report'
        directory.mkdir()
        (directory / 'qa-feedback.md').write_text('APPROVED\n没有评分记录。')
        history = self.history(directory)
        self.assertEqual(history, {'records': [], 'summary': [], 'errors': []})
        text = self.cli('history', directory).stdout
        self.assertIn('未评分', text)
        self.assertNotIn('0.00 分', text)
        self.assertNotIn('100.00 分', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
