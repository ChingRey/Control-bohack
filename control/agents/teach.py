"""Render and record actual steps from the V0.2.1 teaching subplanner."""
from . import teaching_methods, benchmark_registry
STAGES = ['诊断', '必要知识', '引导实践', '独立迁移']
BASE = {
    'sequence': [
        {'id':'observe','stage':STAGES[0],'prompt':'先预测正常文本、空字符串和纯空格提交后，记录数会怎样变化。','hint':0},
        {'id':'principle','stage':STAGES[1],'prompt':'原始字符串非空，不代表它含有有效内容。规范化只处理两端空白，内容内部的空格可能有意义。','hint':1},
        {'id':'practice','stage':STAGES[2],'prompt':'选择处理规则，运行练习后核对新增的记录。','hint':1},
        {'id':'transfer','stage':STAGES[3],'prompt':'在新的表单中独立选择规则并预测结果，然后提交考核。','hint':0},
    ],
}
ADAPT = {
    'verification': ('验证对照练习','为正常文本、空字符串和纯空格各写一行「输入 → 预期 → 实际」，再逐行找出第一个不一致。'),
    'judgment': ('顺序练习','写下原始输入和处理后的输入，比较在哪一步检查空结果才能避免漏判。'),
    'knowledge': ('概念拆解','用一条含内部空格的正常标题和一条纯空格标题，区分内容与两端空白。'),
    'ai_collaboration': ('改写交付要求','先明确 Coding Agent 要保留的行为，再列出应拒绝的输入和你将运行的验收用例。'),
}


def materials(version):
    suite=benchmark_registry.get(version)
    if not hasattr(suite,'BASE_PROMPTS'):
        return BASE,ADAPT
    return {'sequence':[{**step,'prompt':prompt} for step,prompt in zip(BASE['sequence'],suite.BASE_PROMPTS)]},suite.ADAPT


def event(session, step, phase, feedback=None, override=False):
    decision, strategy = session['decision'], session['strategy']
    return {
        'id':f"{session['id']}:action:{len(session['events'])}",'phase':phase,
        'decision_id':decision['decision_id'],'skill_id':decision['skill_id'],
        'strategy_id':strategy['id'],'strategy_version':strategy['version'],
        'strategy_status':strategy['status'],'strategy_reason':session['selection_reason'],
        'actual_strategy_used':{'strategy_id':strategy['id'],'version':strategy['version'],'step_id':step['id'],
                                'local_override':override},
        'stage':step['stage'],'prompt':step['prompt'],'hint_level':step['hint'],
        'feedback_evaluation_id': feedback['evaluation_id'] if feedback else None,
    }


def _deliver(session, feedback=None):
    planner=session.setdefault('planner',{})
    strategy=session['strategy']
    sequence=strategy['sequence']
    actions=('ask','explain','practice','ask_transfer')
    registered={'id':strategy['id'],'version':strategy['version'],
                'content':{'steps':[{'id':step['id'],'action':action,'purpose':step['prompt']}
                                    for step,action in zip(sequence,actions)]}}
    known=[item['id'] for rows in session['evidence'].values() for item in rows]
    context={'stage':'verification','coding_plan':session['project']['plan'],'valid_evidence_refs':known}
    method=teaching_methods.teach(session['decision'],planner,registered,context)
    step=method['next_step']
    if not step['step_id'] or step['action_source']!='subplan':
        raise ValueError('当前教学计划没有可执行的下一步')
    teaching_methods.store_subplan(planner,method)
    matched=next((x for x in sequence if x['id']==step['step_id']),None)
    if matched is None:
        exercised={'id':step['step_id'],'stage':'反馈后的新练习','prompt':step['instruction'],
                   'hint':2 if step['action']!='ask' else 0}
        phase='remediation'
    else:
        exercised=matched
        phase='independent' if step['action']=='ask_transfer' else 'lesson'
    result=event(session,exercised,phase,feedback,override=matched is None)
    result['subplan_id']=method['subplan']['id']
    result['subplan_version']=method['subplan']['version']
    result['planner_action']=step['action']
    teaching_methods.record_step(planner,method,{
        'execution_id':result['id'],'subplan_id':result['subplan_id'],'subplan_version':result['subplan_version'],
        'step_id':step['step_id'],'action':step['subplan_action'],'success':True,'result_ref':result['id']})
    return result


def start(session):
    for _ in range(3):
        session['events'].append(_deliver(session))
    return session['events']


def after_feedback(session, feedback, remediate=True):
    planner=session['planner']
    if remediate:
        _,adapt=materials(session['benchmark_version'])
        weak=next((k for k in adapt if k in feedback['weaknesses']),None)
        missing=any(d in feedback['missing'] for d in adapt)
        if weak or missing:
            subplan=planner['subplans'][session['decision']['decision_id']]
            prompt=adapt[weak][1] if weak else '补交缺失的判断，并写出预期的测试结果。'
            if feedback.get('case_gaps'):
                prompt+=' 本次缺少可靠断言：'+'、'.join(feedback['case_gaps'])+'。'
            planner['last_evaluation']={
                'evaluation_id':feedback['evaluation_id'],'decision_id':session['decision']['decision_id'],
                'goal_id':session['decision']['goal_id'],'subplan_id':subplan['id'],'subplan_version':subplan['version'],
                'goal_status':'partial' if weak else 'insufficient_evidence','evidence_refs':feedback['evidence_ids'],
                'teaching_diagnosis':{'error_type':'application_gap' if weak else 'insufficient_evidence',
                                      'misconceptions':[prompt],'reason':prompt}}
    return _deliver(session,feedback)
