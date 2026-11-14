"""Independent V0.2.1 integration. Public models are vendored byte-for-byte."""
import asyncio
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from http.cookies import SimpleCookie
from pathlib import Path
from .teaching_contract_v021 import contracts as C, validator
from .teaching_service import DecideTeachingService
from . import project_files, project_safety, knowledge

SERVICE_FACTORY = DecideTeachingService
SERVICE_MODE = 'mock'
APPROVED_LIBRARY = None
SESSIONS = {}
COOKIE = 'control_v021_session'

DEMO_EDGE_CASES = {
    'knowledge_point_id': 'edge-cases',
    'concepts': ['边界情形指刚好达到或越过功能处理条件的输入或操作。'],
    'examples': ['列表从一个项目变为空时，界面应显示空列表提示。'],
    'misconceptions': ['只重复常见输入，遗漏空值或临界值。'],
}

class AccessDenied(PermissionError):pass


def install_service(factory, *, mode, approved_library):
    """Trusted deployment injection point; never called with browser/model data."""
    global SERVICE_FACTORY,SERVICE_MODE,APPROVED_LIBRARY
    if mode not in ('mock','model'):raise ValueError('unsupported service mode')
    value=copy.deepcopy(approved_library)
    if mode=='model' and value.get('approval',{}).get('production_approved') is not True:
        raise ValueError('reviewed production course/strategy library required')
    C.CourseCatalog.model_validate(value['catalog']);C.ContentPolicy.model_validate(value['content_policy'])
    for strategy in value['strategies']:C.TeachingStrategy.model_validate(strategy)
    for package in value['knowledge_packages']:C.KnowledgePackage.model_validate(package)
    caps={c['id'] for c in value['catalog']['capabilities']}
    points={k['id'] for k in value['catalog']['knowledge_points']}
    rubrics={r['id']:r for r in value['catalog']['rubrics']}
    if len(caps)!=len(value['catalog']['capabilities']) or len(points)!=len(value['catalog']['knowledge_points']):raise ValueError('duplicate course identifiers')
    for cap in value['catalog']['capabilities']:
        if not set(cap['knowledge_point_ids'])<=points or not set(cap['prerequisite_capability_ids'])<=caps or rubrics.get(cap['rubric_id'],{}).get('capability_id')!=cap['id']:raise ValueError('invalid course relationships')
    if not points<={p['knowledge_point_id'] for p in value['knowledge_packages']}:raise ValueError('knowledge packages incomplete')
    for policy in value['strategies']:
        if not set(policy['capability_ids'])<=caps:raise ValueError('strategy capability not registered')
    keys=[(p['id'],p['version']) for p in value['strategies']]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate policy versions')
    SERVICE_FACTORY=factory;SERVICE_MODE=mode;APPROVED_LIBRARY=value


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def state(task):
    return task.setdefault('teaching_v021', {'schema_version':'0.2.1', 'mode':SERVICE_MODE,
        'requests':{}, 'contexts':{}, 'decisions':{}, 'turns':[], 'evaluations':[],
        'assignments':[], 'switch_grants':[], 'proposals':[], 'experiments':[], 'outcomes':[]})


def fixture(name):
    return json.loads((Path(__file__).parent/'teaching_contract_v021/public/fixtures'/(name+'.json')).read_text(encoding='utf-8'))


def text(value, limit=4000):
    # Public context never includes credentials or arbitrary process configuration.
    return project_safety.scrub(str(value))[:limit] or '(empty)'


def auth(handler, task_id=None, admin=False):
    expected=os.environ.get('CONTROL_V021_ACCESS_TOKEN','')
    supplied=handler.headers.get('Authorization','')
    if expected and hmac.compare_digest(supplied, 'Bearer '+expected):
        return {'role':'admin','task_id':task_id}
    jar=SimpleCookie()
    try: jar.load(handler.headers.get('Cookie',''))
    except Exception: raise AccessDenied('invalid session') from None
    token=jar.get(COOKIE)
    session=SESSIONS.get(token.value) if token else None
    if not session or session['expires']<time.time() or admin or (task_id and session['task_id']!=task_id):
        raise AccessDenied('V0.2.1 requires an authorized project session')
    return session


def login(handler, body, backend):
    # Bootstrap token is configured by the local operator; never persisted to DB/browser storage.
    auth(handler, admin=True)
    task_id=body.get('task_id');backend.load(task_id)
    token=secrets.token_urlsafe(32)
    SESSIONS[token]={'role':'student','task_id':task_id,'expires':time.time()+8*3600}
    for key,row in list(SESSIONS.items()):
        if row['expires']<time.time(): SESSIONS.pop(key,None)
    raw=json.dumps({'authenticated':True,'task_id':task_id}).encode()
    handler.send_response(200)
    handler.send_header('Content-Type','application/json; charset=utf-8')
    handler.send_header('Content-Length',str(len(raw)))
    handler.send_header('Cache-Control','no-store')
    handler.send_header('Set-Cookie',f'{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/api; Max-Age=28800')
    handler.end_headers();handler.wfile.write(raw)


def configure(task):
    s=state(task)
    if s.get('library'):return
    if APPROVED_LIBRARY is not None:
        s['library']=copy.deepcopy(APPROVED_LIBRARY);return
    if SERVICE_MODE!='mock':raise ValueError('production library must be reviewed and provisioned before model service injection')
    req=fixture('teach_request');alternate=fixture('teach_request_followup')['strategy_candidates']
    strategies=[]
    for item in req['strategy_candidates']+alternate:
        if (item['id'],item['version']) not in {(r['id'],r['version']) for r in strategies}: strategies.append(item)
    s['library']={'catalog':fixture('course_catalog'),'content_policy':fixture('content_policy'),
        'strategies':strategies,'knowledge_packages':req['knowledge_packages']+[copy.deepcopy(DEMO_EDGE_CASES)],
        'approval':{'status':'approved_for_mock_integration_only','production_approved':False}}


def freeze(task, backend):
    s=state(task);lib=s['library'];files,assets=project_files.scan(backend.project(task['id']))
    checkpoint=(task.get('coding_checkpoints') or [None])[-1]
    if not checkpoint:raise ValueError('a real Coding checkpoint is required')
    code_hash=knowledge.code_hash(files);asset_hash=project_files.asset_hash(assets)
    if checkpoint['project_evidence']['code_hash']!=code_hash or checkpoint['project_evidence'].get('asset_hash',project_files.asset_hash({}))!=asset_hash:
        raise ValueError('checkpoint is stale; create a new Coding checkpoint')
    context_id='ctx-'+uuid.uuid4().hex; evidence=[];sources={}
    def add(source,kind,summary,record):
        eid='ev-'+uuid.uuid4().hex
        # Complete redacted source is frozen in the backend, model sees bounded excerpt only.
        value=json.loads(project_safety.scrub(canonical(record)))
        sources[eid]=value
        evidence.append({'id':eid,'source':source,'kind':kind,'summary':text(summary),
            'content':text(canonical(value),5000),'artifact_ref':eid})
    planning = checkpoint.get('kind') == 'planning'
    plan = task.get('plan_draft') if planning else task.get('plan')
    if plan:
        add('project','plan','Saved plan draft' if planning else 'Current confirmed plan and current step',
            {'plan':plan,'step':task['step']})
    project_evidence = checkpoint['project_evidence']
    if project_evidence.get('changes') or project_evidence.get('binary_changes'):
        add('project','code_diff','Actual persisted Coding checkpoint',checkpoint)
    version = backend.workflow.digest(files, assets)
    for row in task.get('execution_records',[])[-3:]+task.get('browser_records',[])[-3:]+task.get('behavior_records',[])[-3:]:
        if row.get('hash')==version:add('project','test','Version-matched record; preserve reported verification provenance',row)
    for i,m in list(enumerate(task['messages']))[-12:]:
        if m.get('role')=='user' and m.get('queue_status') not in ('queued','needs_retry'):
            add('learner','student_message','Saved student message',{'message_id':'message-'+str(i),'channel':m['channel'],'content':m['content']})
    context={'context_id':context_id,'session_id':task['id'],'checkpoint_id':checkpoint['checkpoint_id'],
        'project':{'stage':'planning' if planning else ('planning','implementation','implementation','verification','verification')[task.get('workflow',{}).get('stage',0)],
            'task_id':task['id'],'goal':text(checkpoint.get('user_requirement') or task['title']),
            'description':text(checkpoint['task_description']),'evidence_refs':[e['id'] for e in evidence if e['source']=='project']},
        'learner':{'student_id':task.get('student_id') or 'local-'+task['id'],'knowledge_states':[],'prior_help_count':len(s['turns'])},
        'course':{'catalog_version':lib['catalog']['version'],'candidate_capability_ids':[c['id'] for c in lib['catalog']['capabilities']],
            'target_capability_ids':[],'completed_capability_ids':[]},
        'history':{'recent_decision_ids':list(s['decisions'])[-10:],'recent_evaluation_ids':[e['response']['evaluation_id'] for e in s['evaluations'][-10:]]},'evidence':evidence}
    C.TeachingContext.model_validate(context)
    s['contexts'][context_id]={'context':context,'sources':sources,'code_hash':code_hash,'asset_hash':asset_hash}
    return context


def current(task, backend, *, allow_skip=False):
    s=state(task);decision=s['decisions'].get(s.get('active_decision'))
    if decision is None:raise ValueError('no active teaching decision')
    if not decision['teach'] and not allow_skip:raise ValueError('current decision skipped teaching')
    frozen=s['contexts'][decision['context_id']]
    files,assets=project_files.scan(backend.project(task['id']))
    if frozen['code_hash']!=knowledge.code_hash(files) or frozen['asset_hash']!=project_files.asset_hash(assets):
        raise ValueError('project changed since decision; request a new decision')
    return decision,copy.deepcopy(frozen['context'])


def history(s, decision_id):
    turns=[copy.deepcopy(r) for r in s['turns'] if r['decision_id']==decision_id]
    evaluations=[r for r in s['evaluations'] if r['response']['decision_id']==decision_id]
    records=[]
    for row in evaluations[-10:]:
        response=row['response'];maxima={c['id']:c['max_score'] for c in row['rubric']['criteria']}
        fields=('evaluation_id','decision_id','turn_id','assessment_mode','rubric_id','rubric_version','proposed_mastery_level','knowledge_gaps','confidence','next_recommendation','reason')
        record={k:copy.deepcopy(response[k]) for k in fields}
        record['criteria']=[{'criterion_id':c['criterion_id'],'score':c['score'],'max_score':maxima[c['criterion_id']]} for c in response['criteria']]
        records.append(record)
    valid={r['evaluation_id'] for r in records}
    for t in turns:t['evaluation_ids']=[i for i in t['evaluation_ids'] if i in valid]
    return {'recent_turns':turns[-20:],'recent_evaluations':records,'truncated':len(turns)>20 or len(evaluations)>10}


def build_request(task, operation, rid, body, backend):
    s=state(task);lib=s['library'];request={'schema_version':'0.2.1','request_id':rid}
    if operation=='decide':
        request.update(context=freeze(task,backend),catalog=lib['catalog'],content_policy=lib['content_policy']);return request
    decision,context=current(task,backend)
    if operation=='teach':
        past=history(s,decision['decision_id']);active=s.get('active_strategy')
        reply=next((turn['student_reply'] for turn in reversed(past['recent_turns']) if turn.get('student_reply')),None)
        selected = set(decision['knowledge_point_ids'])
        packages = [p for p in lib['knowledge_packages'] if p['knowledge_point_id'] in selected]
        if ('edge-cases' in selected and lib.get('approval', {}).get('status') == 'approved_for_mock_integration_only'
                and not any(p['knowledge_point_id'] == 'edge-cases' for p in packages)):
            # Previously configured demo projects only stored the acceptance-criteria package.
            packages.append(copy.deepcopy(DEMO_EDGE_CASES))
        grant=next((g for g in s['switch_grants'] if not g.get('consumed') and g['decision_id']==decision['decision_id']),None)
        request.update(context=context,decision=decision,phase=body.get('phase','knowledge_teaching'),
            turn_index=len([r for r in s['turns'] if r['decision_id']==decision['decision_id']]),
            strategy_candidates=[p for p in lib['strategies'] if decision['capability_id'] in p['capability_ids']],
            active_strategy=active,allow_strategy_switch=bool(grant and active),teaching_history=past,
            knowledge_packages=packages,
            last_student_message=reply,
            latest_evaluation_id=past['recent_evaluations'][-1]['evaluation_id'] if past['recent_evaluations'] else None)
    elif operation=='evaluate':
        turn=next((t for t in reversed(s['turns']) if t['decision_id']==decision['decision_id']),None)
        if not turn or not turn.get('student_reply'):raise ValueError('a saved student response is required')
        cap=next(c for c in lib['catalog']['capabilities'] if c['id']==decision['capability_id'])
        rubric=next(r for r in lib['catalog']['rubrics'] if r['id']==cap['rubric_id'])
        request.update(context=context,decision=decision,turn_id=turn['turn_id'],assessment_id='assessment-'+rid,
            assessment_mode=body.get('assessment_mode','formative'),rubric=rubric,student_response=turn['student_reply'],
            assessment_task_id='mock-demo-validation',assessment_reference='MOCK integration only: explain how to verify the current feature; not a formal assessment.')
    elif operation=='evolve':
        outcomes=[r for r in s['outcomes'] if r['capability_id']==decision['capability_id']]
        if not outcomes or not s.get('active_strategy'):raise ValueError('recorded teaching outcomes are required')
        policy=next(p for p in lib['strategies'] if (p['id'],p['version'])==(s['active_strategy']['id'],s['active_strategy']['version']))
        outcomes=[r for r in outcomes if (r['applied_policy_id'],r['applied_policy_version'])==(policy['id'],policy['version'])]
        request.update(current_policy=policy,history=outcomes,frozen_catalog_version=lib['catalog']['version'],evaluation_rubric_ids=[r['id'] for r in lib['catalog']['rubrics']])
    return request


def assert_request_current(task,request,backend):
    context=request.get('context')
    if context:
        frozen=state(task)['contexts'][context['context_id']]
        files,assets=project_files.scan(backend.project(task['id']))
        if frozen['code_hash']!=knowledge.code_hash(files) or frozen['asset_hash']!=project_files.asset_hash(assets):
            raise ValueError('source changed; stale contract result or retry rejected')


async def invoke(operation, request, *, planner_state=None):
    obj=validator.validate(operation+'_request',request)
    before=canonical(obj.model_dump(mode='json'))
    service=SERVICE_FACTORY()
    if planner_state is not None and isinstance(service, DecideTeachingService):
        service.planner_state=planner_state
    response=await asyncio.wait_for(getattr(service,operation)(obj),timeout=120)
    if canonical(obj.model_dump(mode='json'))!=before:raise ValueError('service mutated a read-only request')
    data=response.model_dump(mode='json')
    validator.validate(operation+'_response',data,request)
    return data


def apply_response(task, operation, request, response, backend):
    s=state(task)
    if operation=='decide':
        if response['decision_id'] in s['decisions']:raise ValueError('duplicate decision_id')
        s['decisions'][response['decision_id']]=response;s['active_decision']=response['decision_id'];s['active_strategy']=None
    elif operation=='teach':
        if any(t['turn_id']==response['turn_id'] for t in s['turns']):raise ValueError('duplicate turn_id')
        turn={k:copy.deepcopy(response[k]) for k in ('turn_id','decision_id','phase','strategy_id','strategy_version','action')}
        turn.update(turn_index=request['turn_index'],student_reply=None,evaluation_ids=[])
        C.RecordedTeachingTurn.model_validate(turn)
        s['turns'].append(turn);s['active_strategy']={'id':response['strategy_id'],'version':response['strategy_version']}
        s['assignments'].append({'request_id':request['request_id'],'decision_id':response['decision_id'],'turn_id':response['turn_id'],
            **s['active_strategy'],'selection_mode':response['strategy_selection_mode'],'reason':response['strategy_selection_reason'],'mode':SERVICE_MODE})
        for g in s['switch_grants']:
            if g['decision_id']==response['decision_id'] and not g.get('consumed'):g['consumed']=request['request_id']
        backend.message(task,'teaching','assistant',response['action']['content'])
        task['messages'][-1].update(engine_version='0.2.1',engine_mode=SERVICE_MODE,turn_id=response['turn_id'])
        if SERVICE_FACTORY is DecideTeachingService:
            task['messages'][-1]['teaching_source']='teaching_methods'
    elif operation=='evaluate':
        if any(e['response']['evaluation_id']==response['evaluation_id'] for e in s['evaluations']):raise ValueError('duplicate evaluation_id')
        s['evaluations'].append({'request_id':request['request_id'],'response':response,'rubric':request['rubric'],'mode':SERVICE_MODE,'applied_mastery':False})
        turn=next(t for t in s['turns'] if t['turn_id']==response['turn_id']);turn['evaluation_ids'].append(response['evaluation_id'])
        s['outcomes'].append({'record_id':'outcome-'+request['request_id'],'session_id':task['id'],
            'capability_id':request['decision']['capability_id'],'applied_policy_id':turn['strategy_id'],'applied_policy_version':turn['strategy_version'],
            'baseline_level':'unassessed','final_level':response['proposed_mastery_level'],
            'hint_count':sum(t['action']['type']=='hint' for t in s['turns'] if t['decision_id']==turn['decision_id']),
            'transfer_passed':response.get('suggested_pass') if request['assessment_mode']=='independent_transfer' else None,
            'evidence_refs':[response['evaluation_id']]})
        backend.message(task,'teaching','assistant','【V0.2.1 '+SERVICE_MODE+' 评价，仅供联调，不认证能力】'+response['reason'])
    elif operation=='evolve':
        s['proposals'].append({'response':response,'mode':SERVICE_MODE,'published':False})
        s['experiments'].append({'proposal_id':response['proposal_id'],'status':'pending','current_policy_id':response['current_policy_id'],
            'from_version':response['from_version'],'candidate_version':response['candidate_policy']['version'],'observations':[],
            'decision_reason':'Pending separate evidence; Mock never validates teaching effectiveness.'})
    # No path updates mastery, unlocks Skills or publishes candidate policies.


ALLOWED={'configure':set(),'decide':set(),'teach':{'phase'},'respond':{'message'},'evaluate':{'assessment_mode'},
    'evolve':set(),'allow-switch':{'reason'},'resume':{'confirmed','teaching_completed','instruction'}}


def command(task, operation, body, backend):
    body=project_safety.scrub(copy.deepcopy(body))
    if operation not in ALLOWED:raise ValueError('unknown V0.2.1 operation')
    if set(body)-ALLOWED[operation]-{'request_id','retry'}:raise ValueError('unsupported client fields; context/history/strategies are backend-owned')
    rid=body.get('request_id')
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,90}',rid):raise ValueError('stable request_id required (1-90 ASCII letters/digits/_/-)')
    if 'retry' in body and not isinstance(body['retry'],bool):raise ValueError('retry must be boolean')
    s=state(task)
    if s['mode']!=SERVICE_MODE:raise ValueError('service mode changed; create a new isolated integration session')
    fingerprint=canonical({'operation':operation,'body':{k:v for k,v in body.items() if k!='retry'}})
    previous=s['requests'].get(rid)
    if previous:
        if previous['fingerprint']!=fingerprint:raise ValueError('request_id collision')
        if previous['status']=='completed':
            operation_row=next((op for cp in task.get('coding_checkpoints',[]) for op in cp.get('operations',[]) if op['request_id']==rid),None) if operation=='resume' else None
            if not (operation_row and operation_row['status']=='failed' and body.get('retry')):
                receipt=copy.deepcopy(previous['receipt'])
                if operation_row:receipt['operation']=copy.deepcopy(operation_row)
                return 200,receipt
        if not body.get('retry'):raise ValueError('failed/interrupted request requires explicit retry=true')
    elif body.get('retry'):raise ValueError('no failed request to retry')
    if backend.task_busy(task):raise ValueError('task is busy; retry after current operation')
    if operation=='resume':
        # Existing checkpoint state machine owns exactly-once resume. Never accept skill_unlocks.
        decision,context=current(task,backend,allow_skip=True)
        if decision['teach'] and not any(t['decision_id']==decision['decision_id'] for t in s['turns']):raise ValueError('execute teaching action before resume')
        frozen=s['contexts'][context['context_id']]
        s['requests'][rid]={'operation':operation,'fingerprint':fingerprint,'status':'running','body':copy.deepcopy(body),'mode':SERVICE_MODE}
        backend.save(task)
        try:
            code,receipt=backend.checkpoint_command(copy.deepcopy(task),context['checkpoint_id'],'resume',{
                'session_id':task['id'],'request_id':rid,'confirmed':body.get('confirmed'),
                'teaching_completed':body.get('teaching_completed'),'instruction':body.get('instruction',''),
                'expected_code_hash':frozen['code_hash'],'retry':body.get('retry',False),'skill_unlocks':[]})
            receipt={'mode':SERVICE_MODE,'operation':receipt['operation'],'skill_unlocks':[]}
            fresh=backend.load(task['id']);state(fresh)['requests'][rid].update(status='completed',receipt=receipt)
            backend.save(fresh);return code,receipt
        except Exception:
            fresh=backend.load(task['id']);state(fresh)['requests'][rid].update(status='failed',error='resume failed; explicit retry required')
            backend.save(fresh);raise
    if operation!='configure' and not s.get('library'):raise ValueError('请先配置联调课程。')
    entry={'operation':operation,'fingerprint':fingerprint,'status':'running','body':copy.deepcopy(body),'mode':SERVICE_MODE}
    s['requests'][rid]=entry;backend.save(task)
    try:
        work=copy.deepcopy(task);ws=state(work)
        if operation=='configure':configure(work);response={'configured':True,'approval':ws['library']['approval']}
        elif operation=='respond':
            decision,context=current(work,backend)
            turn=next((t for t in reversed(ws['turns']) if t['decision_id']==decision['decision_id']),None)
            message=body.get('message')
            if not turn or turn['student_reply'] is not None:raise ValueError('no unanswered executed teaching turn')
            if not isinstance(message,str) or not message.strip() or len(message)>4000:raise ValueError('student response must contain 1-4000 characters')
            backend.message(work,'teaching','user',message)
            turn['student_reply']={'message_id':'message-'+str(len(work['messages'])-1),'content':work['messages'][-1]['content']}
            response={'saved':True,'student_reply':turn['student_reply']}
        elif operation=='allow-switch':
            decision,context=current(work,backend)
            if not ws.get('active_strategy'):raise ValueError('no active strategy')
            if not isinstance(body.get('reason'),str) or not body['reason'].strip():raise ValueError('operator reason required')
            ws['switch_grants'].append({'decision_id':decision['decision_id'],'request_id':rid,'reason':text(body['reason']),'consumed':None})
            response={'authorized_next_turn':True}
        else:
            # Retrying the same request uses the exact previously saved contract request.
            request=entry.get('contract_request') or (previous or {}).get('contract_request')
            if request is None:request=build_request(work,operation,rid,body,backend)
            # Freeze request and evidence before model call; restart can explicitly retry.
            ws['requests'][rid]['contract_request']=copy.deepcopy(request)
            backend.save(work)
            assert_request_current(work,request,backend)
            if operation=='teach':
                active=ws.get('active_decision')
                if SERVICE_FACTORY is DecideTeachingService and request['decision']['decision_id'].startswith('mock-decision-'):
                    raise ValueError('请重新选择教学目标，生成当前检查点的规则决策。')
                turn_count=sum(turn['decision_id']==active for turn in ws['turns'])
                if request['decision']['decision_id']!=active or request['turn_index']!=turn_count:
                    raise ValueError('教学决策或回合已更新，请发起新的教学请求。')
                planner_state=ws.setdefault('planner',{})
            else:
                planner_state=None
            response=asyncio.run(invoke(operation,request,planner_state=planner_state))
            assert_request_current(work,request,backend)
            apply_response(work,operation,request,response,backend)
        receipt={'schema_version':'0.2.1','mode':SERVICE_MODE,'applied_mastery':False,'skill_unlocks':[], 'response':response}
        ws['requests'][rid].update(status='completed',receipt=receipt)
        backend.save(work);return 200,receipt
    except Exception as error:
        fresh=backend.load(task['id']);state(fresh)['requests'][rid].update(status='failed',error='service, mapping or contract failure; explicit retry required')
        backend.save(fresh)
        if isinstance(error,(ValueError,TypeError,KeyError)):raise
        raise ValueError('Teaching service failed; request saved, explicit retry required') from None


def get_view(task):
    s=task.get('teaching_v021')
    implementations = ({'decide':'rules','teach':'subplan','evaluate':'mock','evolve':'mock'}
                       if SERVICE_FACTORY is DecideTeachingService else {})
    if not s:return {'schema_version':'0.2.1','configured':False,'mode':SERVICE_MODE,'implementations':implementations}
    return {'schema_version':'0.2.1','configured':bool(s.get('library')),'mode':s['mode'],'implementations':implementations,
        'active_decision':s.get('active_decision'),'active_strategy':s.get('active_strategy'),
        'decision':s['decisions'].get(s.get('active_decision')),
        'assignments':s['assignments'],'turns':s['turns'],'evaluations':s['evaluations'],'proposals':s['proposals'],
        'experiments':s['experiments'],'requests':s['requests'],'contexts':s['contexts'],
        'applied_mastery':False,'skill_unlocks':[]}
