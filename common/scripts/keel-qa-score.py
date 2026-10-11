#!/usr/bin/env python3
"""Record QA business results and inspect scores without controlling a run."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True
STATUSES = {'passed', 'failed', 'unverified'}
CORE_FIELDS = ('schema_version', 'project', 'builder', 'review', 'verdict', 'blockers', 'commits',
               'limitations', 'source', 'goal_results', 'checks')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} 须为非空文本')
    return value.strip()


def strings(value, label):
    if not isinstance(value, list):
        raise ValueError(f'{label} 须为文本列表')
    return [nonempty(item, label) for item in value]


def result_item(raw, key):
    if not isinstance(raw, dict):
        raise ValueError('检查结果须为对象')
    identity = nonempty(raw.get(key), key)
    status = raw.get('status')
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError(f'{identity} 状态须为 passed、failed 或 unverified')
    evidence = raw.get('evidence', [])
    if isinstance(evidence, str):
        evidence = [evidence]
    evidence = strings(evidence, f'{identity} 的证据')
    reason = raw.get('reason', '')
    if not isinstance(reason, str):
        raise ValueError(f'{identity} 的原因须为文本')
    if status in {'passed', 'failed'} and not evidence:
        raise ValueError(f'{identity} 缺少验证证据')
    if status == 'unverified' and not reason.strip():
        raise ValueError(f'{identity} 须说明未验证原因')
    return {key: identity, 'status': status, 'evidence': evidence, 'reason': reason.strip()}


def result_list(raw, key):
    if not isinstance(raw, list):
        raise ValueError('检查结果须为列表')
    result, seen = [], set()
    for value in raw:
        item = result_item(value, key)
        if item[key] in seen:
            raise ValueError(f'检查项重复：{item[key]}')
        seen.add(item[key])
        result.append(item)
    return result


def totals(items):
    counts = {status: sum(item['status'] == status for item in items) for status in STATUSES}
    total = len(items)
    return {'completed': counts['passed'], 'total': total, 'failed': counts['failed'],
            'unverified': counts['unverified'],
            'percent': round(100 * counts['passed'] / total, 2) if total else None}


def goal_source(plan=None, fix=None):
    if plan and fix:
        raise ValueError('只能提供计划或修复说明之一')
    module = None
    if plan or fix:
        spec = importlib.util.spec_from_file_location('keel_score_plan', Path(__file__).with_name('keel-plan.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    if plan:
        path = Path(plan).resolve(strict=True)
        bundle = module.validate(path)
        catalog = [{'id': slug, 'target': module.one_field(feature['goal'], '目标')}
                   for slug, feature in bundle['features'].items()]
        sources = {path.name: bundle['source'], **{value['path']: value['source']
                   for value in bundle['features'].values()}}
        return {'kind': 'plan', 'path': str(path), 'sha256': digest(sources), 'catalog': catalog}
    if fix:
        path = Path(fix).resolve(strict=True)
        text = path.read_text(encoding='utf-8')
        titles = re.findall(r'^# (.+)$', module.prose(module.blocks(text)), re.M)
        if not text.startswith('# ') or len(titles) != 1:
            raise ValueError('修复说明须有唯一标题')
        return {'kind': 'fix', 'path': str(path), 'sha256': digest(text),
                'catalog': [{'id': 'bug', 'target': titles[0]}]}
    return {'kind': 'none', 'path': None, 'sha256': None, 'catalog': []}


def align_goals(raw, source):
    if raw is None:
        return None
    if not source['catalog']:
        raise ValueError('目标评分需要计划或批准的修复说明')
    items = {item['id']: item for item in result_list(raw, 'id')}
    known = {goal['id'] for goal in source['catalog']}
    unknown = set(items) - known
    if unknown:
        raise ValueError('未知目标：' + '、'.join(sorted(unknown)))
    return [items.get(goal['id'], {'id': goal['id'], 'status': 'unverified',
            'reason': '未报告验证结果', 'evidence': []}) for goal in source['catalog']]


def prepare(raw, source):
    if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
        raise ValueError('结果须使用 schema_version: 1')
    review, verdict = raw.get('review'), raw.get('verdict')
    if review not in {'initial', 'retest'} or verdict not in {'APPROVED', 'REJECTED'}:
        raise ValueError('须明确初验/复验及当次 APPROVED/REJECTED')
    if 'blockers' not in raw:
        raise ValueError('须提供当次阻断项列表，不能默认通过')
    checks, seen = [], set()
    if not isinstance(raw.get('checks', []), list):
        raise ValueError('checks 须为列表')
    for check in raw.get('checks', []):
        if not isinstance(check, dict):
            raise ValueError('检查组须为对象')
        name = nonempty(check.get('name'), '检查组名称')
        if name in seen:
            raise ValueError('检查组重复：' + name)
        seen.add(name)
        checks.append({'name': name, 'items': result_list(check.get('items'), 'name')})
    project = raw.get('project')
    if project is not None:
        project = nonempty(project, '项目')
    return {'schema_version': 1, 'project': project, 'builder': nonempty(raw.get('builder', 'unknown'), 'Builder'),
            'review': review, 'verdict': verdict, 'blockers': strings(raw['blockers'], '阻断项'),
            'commits': strings(raw.get('commits', []), '提交'),
            'limitations': strings(raw.get('limitations', []), '未验证事项'), 'source': source,
            'goal_results': align_goals(raw.get('goal_results'), source), 'checks': checks}


def scores(core):
    goals = core['goal_results']
    return (totals(goals) if goals is not None else None,
            [{'name': check['name'], **totals(check['items'])} for check in core['checks']])


def read_record(path):
    if path.is_symlink():
        raise ValueError('评分记录不能使用符号链接')
    record = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(record, dict) or any(key not in record for key in CORE_FIELDS):
        raise ValueError('评分记录字段不完整')
    source = record['source']
    if not isinstance(source, dict) or source.get('kind') not in {'plan', 'fix', 'none'}:
        raise ValueError('评分来源无效')
    catalog = source.get('catalog')
    if not isinstance(catalog, list) or any(not isinstance(goal, dict) for goal in catalog):
        raise ValueError('目标清单无效')
    identities = [nonempty(goal.get('id'), '目标ID') for goal in catalog]
    if len(set(identities)) != len(identities):
        raise ValueError('目标清单重复')
    for goal in catalog:
        nonempty(goal.get('target'), '目标说明')
    if source['kind'] != 'none' and (not catalog or not re.fullmatch(r'[0-9a-f]{64}', str(source.get('sha256')))):
        raise ValueError('目标来源摘要无效')
    core = prepare({key: record[key] for key in CORE_FIELDS}, source)
    if digest(core) != record.get('data_sha256'):
        raise ValueError('评分记录内容与摘要不一致')
    goal_score, check_scores = scores(core)
    if record.get('goal_score') != goal_score or record.get('check_scores') != check_scores:
        raise ValueError('评分数字与实际结果不一致')
    timestamp = datetime.fromisoformat(nonempty(record.get('recorded_at'), '记录时间'))
    if timestamp.tzinfo is None:
        raise ValueError('记录时间缺少时区')
    return record


def record_result(raw, output_dir, plan=None, fix=None):
    directory = Path(output_dir)
    if directory.is_symlink():
        raise ValueError('报告目录不能使用符号链接')
    source = goal_source(plan, fix)
    if isinstance(raw, dict) and raw.get('project') is None:
        raw = dict(raw)
        locations = [directory.resolve()]
        if source['path']:
            locations.append(Path(source['path']))
        for location in locations:
            project = next((parent.parent for parent in (location, *location.parents) if parent.name == '.keel'), None)
            if project is not None:
                raw['project'] = str(project)
                break
    core = prepare(raw, source)
    fingerprint = digest(core)
    directory.mkdir(parents=True, exist_ok=True)
    name = 'qa-score.json' if core['review'] == 'initial' else f'qa-score-retest-{fingerprint[:12]}.json'
    target = directory / name
    if target.exists() or target.is_symlink():
        if read_record(target)['data_sha256'] == fingerprint:
            return target
        raise ValueError('已有首次评分，不能用新结果覆盖')
    goal_score, check_scores = scores(core)
    record = {**core, 'recorded_at': datetime.now(timezone.utc).isoformat(), 'data_sha256': fingerprint,
              'goal_score': goal_score, 'check_scores': check_scores}
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as temp:
            temp_path = Path(temp.name)
            json.dump(record, temp, ensure_ascii=False, indent=2, allow_nan=False)
            temp.write('\n')
            temp.flush()
            os.fsync(temp.fileno())
        try:
            os.link(temp_path, target)
        except FileExistsError:
            if read_record(target)['data_sha256'] != fingerprint:
                raise ValueError('已有评分，不能用新结果覆盖')
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return target


def history(directory, last=10, builder=None, include_retests=False):
    root = Path(directory).resolve(strict=True)
    if not root.is_dir() or last < 1:
        raise ValueError('须提供评分目录和正整数记录数')
    root = root / '.keel' if (root / '.keel').is_dir() else root
    records, errors = [], []
    for path in root.rglob('qa-score*.json'):
        if not re.fullmatch(r'qa-score(?:-retest-[0-9a-f]{12})?\.json', path.name):
            continue
        try:
            record = read_record(path)
            if builder and record['builder'] != builder:
                continue
            if not include_retests and record['review'] != 'initial':
                continue
            records.append({'path': str(path), **record})
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append({'path': str(path), 'error': str(error)})
    records.sort(key=lambda record: (datetime.fromisoformat(record['recorded_at']), record['path']), reverse=True)
    records = records[:last]
    groups = {}
    for record in records:
        key = (record['project'], record['source']['kind'], record['builder'], record['review'])
        group = groups.setdefault(key, {'project': key[0], 'kind': key[1], 'builder': key[2], 'review': key[3],
                                      'records': 0, 'scored_records': 0, 'completed': 0, 'total': 0})
        group['records'] += 1
        if record['goal_score'] is not None:
            group['scored_records'] += 1
            group['completed'] += record['goal_score']['completed']
            group['total'] += record['goal_score']['total']
    for group in groups.values():
        group['percent'] = round(100 * group['completed'] / group['total'], 2) if group['total'] else None
    return {'records': records, 'summary': list(groups.values()), 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description='记录并查看 QA 评分，不决定验收或下一次检查。')
    commands = parser.add_subparsers(dest='command', required=True)
    write = commands.add_parser('record', help='计算评分并保存业务记录')
    write.add_argument('input', help='检查结果 JSON；- 表示标准输入')
    write.add_argument('--output-dir', required=True, help='本次报告目录')
    basis = write.add_mutually_exclusive_group()
    basis.add_argument('--plan', help='本次计划索引快照')
    basis.add_argument('--fix', help='本次批准的修复说明')
    view = commands.add_parser('history', help='查看最近评分')
    view.add_argument('directory', help='项目或评分目录')
    view.add_argument('--last', type=int, default=10)
    view.add_argument('--builder')
    view.add_argument('--include-retests', action='store_true')
    view.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'record':
            raw = json.loads(sys.stdin.read() if args.input == '-' else Path(args.input).read_text(encoding='utf-8'))
            print(record_result(raw, args.output_dir, args.plan, args.fix))
        else:
            data = history(args.directory, args.last, args.builder, args.include_retests)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
            else:
                if not data['records']:
                    print('未评分：暂无有效评分记录，不推算旧任务成绩。')
                for record in data['records']:
                    score = record['goal_score']
                    grade = f"{score['percent']:.2f} 分（{score['completed']}/{score['total']}）" if score else '目标未评分'
                    review = '初验' if record['review'] == 'initial' else '复验'
                    print(f"{record['recorded_at']} | {record['builder']} | {record['source']['kind']} | {review} | {grade} | {record['verdict']}")
                    for check in record['check_scores']:
                        value = f"{check['percent']:.2f} 分" if check['percent'] is not None else '未评分'
                        print(f"  {check['name']}：{value}（{check['completed']}/{check['total']}）")
                    if record['limitations']:
                        print('  未验证事项：' + '；'.join(record['limitations']))
                for group in data['summary']:
                    value = f"{group['percent']:.2f}%" if group['percent'] is not None else '未评分'
                    review = '初验' if group['review'] == 'initial' else '复验'
                    print(f"汇总 | {group['builder']} | {group['kind']} | {review} | 目标已评分 {group['scored_records']}/{group['records']} 条 | 完成 {group['completed']}/{group['total']} | {value}")
                for error in data['errors']:
                    print(f"无效记录：{error['path']}：{error['error']}", file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'错误：{error}\n')


if __name__ == '__main__':
    main()
