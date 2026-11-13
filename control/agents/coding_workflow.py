"""Model-independent checkpoint contract. No model, credentials or fabricated edits."""
import copy
import hashlib
import json

def state(task):
    return task.setdefault('coding_workflow', {'revision':1, 'status':'planning',
        'checkpoints':[], 'events':[], 'loads':[], 'experience_enabled':True,
        'skill_enabled':False, 'skill_bindings':[]})

def event(task, kind, detail):
    s=state(task)
    s['events'].append({'id':len(s['events'])+1,'kind':kind,'detail':detail,'source':'workbench'})
    s['revision']+=1

def set_plan(task, steps):
    if not isinstance(steps,list) or not 1<=len(steps)<=12 or any(not isinstance(x,str) or not x.strip() or len(x)>300 for x in steps):
        raise ValueError('请填写1–12个阶段，每行一个；每阶段结束后暂停')
    if task.get('plan'):raise ValueError('已确认计划不能被草稿覆盖')
    task['plan_draft']=[x.strip() for x in steps]
    task['stage']='planning'
    event(task,'plan_draft','学生提供阶段草稿；Teaching 可读取讨论，尚未执行')

def confirm(task):
    s=state(task)
    s['checkpoints']=[{'index':i,'title':x,'status':'pending'} for i,x in enumerate(task['plan'])]
    s['status']='paused'
    event(task,'plan_confirmed','计划已确认；等待学生授权当前阶段')

def prepare(task, instruction, learning_context=None, knowledge_context=None):
    s=state(task)
    packet=copy.deepcopy(learning_context or {'rules':[],'skills':[]})
    packet['rules']=packet.get('rules',[]) if s['experience_enabled'] else []
    # Future verified-skill resolver supplies bindings. Client cannot supply Skill bodies.
    packet['skills']=[]
    payload={'contract_version':1,'task_id':task['id'],'phase_index':task['step'],
        'plan':task['plan'],'instruction':instruction,'stop_after_current_phase':True,
        'learning_context':packet,'project_knowledge':copy.deepcopy(knowledge_context or []),'capability_revision':s['revision']}
    return payload

class OpenCodeCodingAgent:
    """Transport seam: adapter must return verified tool events and file changes.

    No implicit credentials, global OpenCode config or model selection. The actual
    version-pinned transport is deliberately not enabled until provider selection.
    """
    def __init__(self, transport=None):self.transport=transport
    def step(self, task, instruction, learning_context=None):
        if self.transport is None:
            raise ValueError('OpenCode执行器尚未连接：模型/API按要求暂未配置；没有修改代码或推进阶段')
        return self.transport(prepare(task,instruction,learning_context))

def inspect_phase(task, packet):
    s=state(task)
    digest=hashlib.sha256(json.dumps(packet,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    s['loads'].append({'phase':task['step'],'payload_hash':digest,
        'rule_versions':[{'id':r['id'],'revision':r['revision']} for r in packet['learning_context']['rules']],
        'skill_versions':[],'submitted':False,'applied':False})
    event(task,'execution_blocked','连接预检：无模型/API，未向OpenCode提交；仍停在当前检查点')
    s['status']='blocked_unconfigured'

def sync_plan(task, text='', events=None):
    import re
    if task.get('plan'):return False
    rows=[]
    for event_item in events or []:
        part=event_item.get('part',{})
        if part.get('tool')=='todowrite':
            tool_state=part.get('state',{})
            todos=tool_state.get('input',{}).get('todos',[])
            candidate=[x.get('content','').strip() for x in todos if isinstance(x,dict)]
            if candidate and all(candidate):rows=candidate
    if not rows and re.search(r'开发计划|实施计划|阶段计划|实现计划|开发步骤|实施步骤',text):
        for line in text.splitlines():
            match=re.match(r'^\s*(?:#{1,4}\s*)?(?:\*\*)?(?:(?:阶段|步骤)\s*[一二三四五六七八九十0-9]+\s*[：:.、)）-]|[0-9]+[.、)）]\s+)(.+)',line)
            if match:rows.append(match.group(1).strip().strip('*')[:300])
    if not 1<=len(rows)<=12:return False
    if rows==task.get('plan_draft') or rows==task.get('plan'):return False
    task['plan_draft']=rows
    state(task)['plan_source']='opencode_todos' if events and any(e.get('part',{}).get('tool')=='todowrite' for e in events) else 'assistant_explicit_plan'
    event(task,'plan_synced','聊天中的计划已同步，按原顺序显示')
    return True

def accept_phase(task):
    s=state(task);i=task['step']
    if not task.get('plan') or i>=len(task['plan']):raise ValueError('没有待检查的阶段')
    checkpoints=s.get('checkpoints',[])
    if i>=len(checkpoints) or checkpoints[i]['status']!='executed_pending_review':raise ValueError('当前阶段尚未执行完成，不能确认通过')
    checkpoints[i]['status']='accepted_by_student'
    task['step']+=1
    event(task,'phase_accepted','学生确认第'+str(i+1)+'阶段检查通过')
    s['status']='paused'
