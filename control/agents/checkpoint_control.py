"""Student-confirmed checkpoint commands and idempotency, without model authority."""
import copy
import hashlib
import json
import re
from . import coding_workflow, knowledge, learning, project_files


def find(task, checkpoint_id):
    event = next((e for e in task.get('coding_checkpoints', []) if e['checkpoint_id'] == checkpoint_id), None)
    if event is None:
        raise ValueError('当前会话不存在该检查点')
    return event


def root(task, event):
    return find(task, event.get('root_checkpoint_id', event['checkpoint_id']))


def finish(task, job, status, result_checkpoint_id=None, error=None):
    ref = job.get('checkpoint_operation')
    if not ref:
        return
    parent = find(task, ref['checkpoint_id'])
    operation = next(o for o in parent['operations'] if o['request_id'] == ref['request_id'])
    operation.update(status=status, error=error)
    if result_checkpoint_id:
        operation['result_checkpoint_id'] = result_checkpoint_id


def skill_results(unlocks):
    if not isinstance(unlocks, list) or len(unlocks) > 10:
        raise ValueError('skill_unlocks必须是最多10项的列表')
    known = {s['id'] for s in learning.CATALOG['skills']}
    results = []
    for unlock in unlocks:
        if not isinstance(unlock, dict) or set(unlock) != {'skill_id', 'assessment_id', 'unlocked'}:
            raise ValueError('Skill通知需要skill_id、assessment_id和unlocked，不接受客户端设置实际启用状态')
        if unlock['skill_id'] not in known or unlock['unlocked'] is not True:
            raise ValueError('未知Skill或无效的解锁结果')
        if not isinstance(unlock['assessment_id'], str) or not 1 <= len(unlock['assessment_id']) <= 120:
            raise ValueError('Skill通知缺少能力考核结果标识')
        results.append({**copy.deepcopy(unlock), 'notification_status': 'received',
                        'assessment_source': 'teaching_report_not_independently_verified',
                        'enabled': False, 'used': False, 'activation_status': 'unsupported',
                        'reason': '当前Skill候选未完成效果验证，尚无经审核绑定和实际加载确认通道；通知不等于实际启用'})
    return results


def prepare(task, checkpoint_id, action, body, files, binary_files=None):
    """Mutate only a locked task copy. Caller persists before launching Coding.

    Returns (operation, launch). Exact duplicates return the original receipt.
    A failed command can retry only its original target phase and source version.
    """
    if task.get('mode') != 'opencode' or action not in ('revise', 'resume'):
        raise ValueError('仅OpenCode开发检查点支持修改和恢复')
    if body.get('session_id') != task['id'] or body.get('confirmed') is not True:
        raise ValueError('需要当前session_id及学生明确确认 confirmed=true')
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', request_id):
        raise ValueError('需要稳定且唯一的request_id')
    instruction = body.get('instruction', '')
    if not isinstance(instruction, str) or len(instruction) > 12000 or (action == 'revise' and not instruction.strip()):
        raise ValueError('修改操作需要学生已确认的非空instruction，最多12000字符')
    if action == 'resume' and body.get('teaching_completed') is not True:
        raise ValueError('恢复前需明确确认 teaching_completed=true')
    if 'retry' in body and type(body['retry']) is not bool:
        raise ValueError('retry必须为布尔值')
    event = find(task, checkpoint_id)
    parent = root(task, event)
    unlocks = body.get('skill_unlocks', [])
    acknowledgements = skill_results(unlocks)
    request = {'checkpoint_id': checkpoint_id, 'action': action, 'instruction': instruction,
               'expected_code_hash': body.get('expected_code_hash'), 'skill_unlocks': unlocks}
    digest = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    operations = parent.setdefault('operations', [])
    previous = next((o for o in operations if o['request_id'] == request_id), None)
    if previous:
        if previous['request_hash'] != digest:
            raise ValueError('相同request_id不能提交不同操作或内容')
        if previous['status'] != 'failed' or not body.get('retry', False):
            return previous, False
    elif body.get('retry'):
        raise ValueError('retry只能用于已保存的失败请求')
    if parent.get('resume_request_id') and not (previous and previous['action'] == 'resume'):
        raise ValueError('此检查点已最终恢复，不能再次恢复或提交修改')
    if any(task.get(k, {}).get('status') in ('queued', 'running') for k in ('coding_run', 'teaching_run')):
        raise ValueError('当前会话正在执行，不能同时修改或恢复')
    code_hash = knowledge.code_hash(files)
    asset_hash=project_files.asset_hash(binary_files or {})
    if previous and previous.get('expected_asset_hash',project_files.asset_hash({}))!=asset_hash:
        raise ValueError('二进制资源版本已变化，不能重试旧请求')
    if body.get('expected_code_hash') != code_hash:
        raise ValueError('源码版本不一致，请读取最新检查点后重试')
    if previous:
        if task['coding_checkpoints'][-1]['checkpoint_id'] != previous['base_checkpoint_id']:
            raise ValueError('已有新的检查点，不能重试旧请求')
        if task['step'] != previous['target_step']:
            raise ValueError('开发阶段已变化，不能重试旧请求')
        previous.update(status='queued', error=None, attempt=previous['attempt'] + 1)
        return previous, True
    latest = task['coding_checkpoints'][-1]
    if root(task, latest)['checkpoint_id'] != parent['checkpoint_id'] or latest['kind'] != 'development':
        raise ValueError('仅当前开发检查点可接受修改或恢复，计划草稿仍需确认')
    if latest['project_evidence'].get('asset_hash',project_files.asset_hash({}))!=asset_hash:raise ValueError('检查点二进制资源版本已过期')
    if latest['project_evidence']['code_hash'] != code_hash or task['step'] != parent['stage_index']:
        raise ValueError('检查点或开发阶段已过期，请重新检查当前项目')
    if action == 'resume':
        coding_workflow.accept_phase(task)
        parent['resume_request_id'] = request_id
    operation = {'request_id': request_id, 'request_hash': digest, 'action': action,
                 'checkpoint_id': checkpoint_id, 'root_checkpoint_id': parent['checkpoint_id'],
                 'instruction': instruction, 'expected_code_hash': code_hash, 'target_step': task['step'],
                 'status': 'queued', 'attempt': 1, 'skill_results': acknowledgements,
                 'base_checkpoint_id': latest['checkpoint_id'],'expected_asset_hash':asset_hash,
                 'student_confirmed': True, 'teaching_completed': body.get('teaching_completed') is True}
    operations.append(operation)
    return operation, True
