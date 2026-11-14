"""Model-independent checkpoint contract. No model, credentials or fabricated edits."""
import copy
import hashlib
import json
from . import skill_gateway

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
    task.pop('plan_decision',None)
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
    packet['skills']=[]  # Coding grows only through reviewed project knowledge; Skill loading disabled.
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
    if not rows and re.search(r'开发计划|实施计划|阶段计划|实现计划|开发步骤|实施步骤|开始规划|具体规划|计划如下|以下计划|制定.*计划|按照以下计划',text):
        for line in text.splitlines():
            match=re.match(r'^\s*(?:#{1,4}\s*)?(?:\*\*)?(?:(?:阶段|步骤)\s*[一二三四五六七八九十0-9]+\s*[：:.、)）-]|[0-9]+[.、)）]\s+)(.+)',line)
            if match:rows.append(match.group(1).strip().strip('*')[:300])
    if not 1<=len(rows)<=12:return False
    if rows==task.get('plan_draft') or rows==task.get('plan'):return False
    task['plan_draft']=rows
    task.pop('plan_decision',None)
    state(task)['plan_source']='opencode_todos' if events and any(e.get('part',{}).get('tool')=='todowrite' for e in events) else 'assistant_explicit_plan'
    event(task,'plan_synced','聊天中的计划已同步，按原顺序显示')
    return True

def message_intent(text):
    """Recognize explicit file/command requests without treating '按计划创建' as planning."""
    import re
    readonly=bool(re.search(r'(?:只|仅|先|暂时)(?:讨论|分析|解释|规划)|(?:不要|别|暂不|不需要)(?:写|改|创建|生成|执行|开发)|(?:怎么|如何|能否|是否|能不能).{0,18}(?:创建|写入|修改|实现|开发)',text))
    plan=bool(re.search(r'(?:制定|生成|讨论|调整|给出|设计|修改).{0,6}(?:计划|规划)|(?:计划|规划).{0,6}(?:怎么|如何|是否)',text))
    edit=bool(re.search(r'开始|执行|实现|开发|修改|修复|写代码|写文件|继续|创建|新建|写入|编写|添加|删除|重命名|移动|安装|构建|运行|测试|create|write|implement|fix|build|install|rename|delete',text,re.I))
    return 'execute' if edit and not (readonly or plan) else 'discuss'

def development_authorized(text):
    import re
    return message_intent(text)=='execute' and bool(re.search(r'创建|新建|写入|编写|修改|修复|删除|重命名|开始|执行|动手|继续|create|write|implement|fix',text,re.I))

def direct_file_request(text):
    import re
    return bool(re.search(r'^(?:(?:请|帮我|麻烦|直接|现在|立即|给我|请你|按计划|按照计划)\s*)*(?:创建|新建|写入|编写|修改|删除|重命名).{0,120}(?:[.](?:[cm]?js|tsx?|jsx|py|html|css|sql|json)|(?:JS|JavaScript|脚本)文件)',text,re.I))

def accept_phase(task):
    s=state(task);i=task['step']
    if not task.get('plan') or i>=len(task['plan']):raise ValueError('没有待检查的阶段')
    checkpoints=s.get('checkpoints',[])
    if i>=len(checkpoints) or checkpoints[i]['status']!='executed_pending_review':raise ValueError('当前阶段尚未执行完成，不能确认通过')
    checkpoints[i]['status']='accepted_by_student'
    task['step']+=1
    event(task,'phase_accepted','学生确认第'+str(i+1)+'阶段检查通过')
    s['status']='paused'


def confirms_plan(text):
    import re
    text=re.sub(r'[\s。！!，,]+','',text)
    return text in ('确认计划','就按这个计划','按这个计划做','符合','符合我的期望','计划没问题','我确认了','确认了','我确认','确认','可以就这样','就这样吧','没问题')

def phase_contract(task):
    """Plan scope is backend-owned; model todos cannot advance this contract."""
    import re
    plan=task.get('plan',[]);index=task.get('step',0)
    current=plan[index] if 0<=index<len(plan) else None
    title=re.split(r'[：:]',current or '',maxsplit=1)[0].replace('**','')
    review_only=bool(current and re.search(r'需求分析|需求澄清|梳理需求|讨论方案|确定.*(?:规则|机制|需求)',title))
    checkpoints=state(task).get('checkpoints',[])
    requires_file_change=bool(current and not review_only and re.search(r'创建|新建|写入|写文件|写代码|编写|修改|实现|开发|修复|添加|删除|重命名',current))
    status=checkpoints[index]['status'] if index<len(checkpoints) else None
    return {'plan_confirmed':bool(plan),'current_index':index,'current_title':current,
        'requires_file_change':requires_file_change,
        'execution_status':'executed' if status in ('executed_pending_review','accepted_by_student') else 'not_executed',
        'acceptance_status':'accepted' if status=='accepted_by_student' else 'not_accepted',
        'execution_mode':'review_only' if review_only else 'file_execution',
        'current_status':checkpoints[index]['status'] if index<len(checkpoints) else None,
        'accepted':[{'index':i,'title':x['title']} for i,x in enumerate(checkpoints) if x['status']=='accepted_by_student'],
        'future':[{'index':i,'title':x} for i,x in enumerate(plan) if i>index],
        'boundary':'仅处理current_title；future是后续安排，不是本阶段缺陷。模型轮次结束不代表学生验收通过。'}
