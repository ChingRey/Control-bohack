"""Local API probe; never handles provider credentials."""
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'data/phase-scope-probe.json'

def call(path, body=None):
    request = Request('http://127.0.0.1:8782/api/' + path,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=20) as response:
        return json.load(response)

def wait(tid):
    deadline = time.time() + 900
    while time.time() < deadline:
        task = call('tasks/' + tid)
        if all(task.get(k, {}).get('status') not in ('queued', 'running') for k in ('coding_run', 'teaching_run')):
            return task
        time.sleep(2)
    raise TimeoutError('Model turn did not finish')

action = sys.argv[1]
if action == 'start':
    task = call('tasks', {'coding_mode': 'opencode', 'checkpoint_delivery': 'manual'})
    STATE.write_text(json.dumps({'task_id': task['id']}), encoding='utf-8')
    task = call('tasks/' + task['id'] + '/coding/messages', {'message':
        '做一个计数器项目。请先写三阶段计划：第一阶段需求分析，确定初始值7、点击加一规则，不创建文件；第二阶段实现src/counter.js，导出count和increment，不做重置；第三阶段添加reset。先给计划，不执行。'})
elif action == 'approve':
    tid = json.loads(STATE.read_text())['task_id']
    task = call('tasks/' + tid)
    task = call('tasks/' + tid + '/coding/plan-decision', {'choice': 'approve',
        'request_id': 'scope-approve', 'expected_plan': task['plan_draft']})
elif action == 'resume':
    tid = json.loads(STATE.read_text())['task_id']
    task = call('tasks/' + tid)
    event = task['coding_checkpoints'][-1]
    task = call('tasks/' + tid + '/checkpoints/' + event['checkpoint_id'] + '/resume', {
        'session_id': tid, 'request_id': 'scope-resume', 'confirmed': True,
        'teaching_completed': True, 'expected_code_hash': event['project_evidence']['code_hash']})
elif action == 'teacher':
    tid = json.loads(STATE.read_text())['task_id']
    task = call('tasks/' + tid + '/teaching/messages', {'message':
        '请按当前计划检查本轮结果：先指出本轮是计划第几项、叫什么，以及后面尚未实现的功能现在算不算遗漏。引用本轮Coding对话和真实文件证据，别提前推进后续阶段。'})
else:
    tid = json.loads(STATE.read_text())['task_id']
    task = call('tasks/' + tid)
task = wait(task.get('id') or tid)
output = {k: task.get(k) for k in ('id', 'plan', 'plan_draft', 'step', 'coding_run', 'teaching_run', 'files')}
output['recent_messages'] = task['messages'][-4:]
output['checkpoints'] = [{'stage': e['stage'], 'stage_index': e.get('stage_index')} for e in task.get('coding_checkpoints', [])]
print(json.dumps(output, ensure_ascii=False, indent=2))
STATE.with_name('phase-scope-' + action + '.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
