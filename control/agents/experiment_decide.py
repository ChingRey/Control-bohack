"""Map stored project checkpoints into the V0.2.1 Decide service."""
import asyncio
from uuid import uuid4
from . import benchmark as b, benchmark_registry
from .decide_service import DecideService
from .teaching_contract_v021.contracts import DecideRequest

CATALOG = {
    'version':'input-validation-1',
    'capabilities':[{'id':b.SKILL,'title':'行为验证','behaviors':['构造正常与边界用例','对比预期和实际'],
                     'knowledge_point_ids':[b.TOPIC],'rubric_id':b.VERSION}],
    'knowledge_points':[{'id':b.TOPIC,'capability_id':b.SKILL,'title':'输入边界验证','project_stages':['verification']}],
    'rubrics':[{'id':b.VERSION,'version':1,'capability_id':b.SKILL,
                'criteria':[{'id':key,'description':label,'max_score':weight} for key,(label,weight) in b.DIMENSIONS.items()],
                'pass_score':80}],
}
POLICY = {'id':'input-boundary-policy','version':1,
          'rules':[{'when':'有可查证的项目计划和前测','action':'围绕行为验证选择教学目标'}],
          'stop_conditions':['缺少与阶段相关的项目证据']}


def choose(session, result, personal, validated):
    rid=uuid4().hex
    project=session['project']
    suite=benchmark_registry.get(session['benchmark_version'])
    title=getattr(suite,'TITLE','输入边界验证')
    catalog={'version':suite.VERSION,'capabilities':[{**CATALOG['capabilities'][0], 'id':suite.SKILL,
             'knowledge_point_ids':[suite.TOPIC], 'rubric_id':suite.VERSION}],
             'knowledge_points':[{**CATALOG['knowledge_points'][0],'id':suite.TOPIC,'capability_id':suite.SKILL,'title':title}],
             'rubrics':[{**CATALOG['rubrics'][0],'id':suite.VERSION,'capability_id':suite.SKILL}]}
    checkpoint_id=project['checkpoint_id']
    artifact='plan-'+checkpoint_id
    eval_id=result['evaluation_id']
    evidence=[{'id':artifact,'source':'project','kind':'plan','summary':'工作台已保存的项目计划',
               'content':'\n'.join(project['plan'])},
              {'id':eval_id,'source':'assessment','kind':'evaluation','summary':'本次独立前测'}]
    earlier=personal.get('evaluation_id')
    if earlier:
        evidence.append({'id':earlier,'source':'assessment','kind':'evaluation','summary':'同一本机档案先前在其他项目的评价'})
    weak='verification' in result['weaknesses']
    experience=validated if validated.get('focus') in result['weaknesses'] else {}
    request=DecideRequest.model_validate({
        'schema_version':'0.2.1','request_id':rid,'catalog':catalog,'content_policy':POLICY,
        'context':{'context_id':'ctx-'+rid,'session_id':session['id'],'checkpoint_id':checkpoint_id,
                   'project':{'stage':'verification','task_id':session['task_id'],'goal':project['title'],
                              'description':title,'evidence_refs':[artifact] if project['plan'] else []},
                   'learner':{'student_id':session['learner_id'],'knowledge_states':[
                       {'knowledge_point_id':suite.TOPIC,'level':'needs_support' if weak else 'guided',
                        'evidence_refs':[eval_id]}]},
                   'course':{'catalog_version':catalog['version'],'candidate_capability_ids':[suite.SKILL],
                             'target_capability_ids':[suite.SKILL] if experience else []},
                   'history':{'recent_evaluation_ids':[earlier] if earlier else []},'evidence':evidence}})
    decision=asyncio.run(DecideService().decide(request)).model_dump(mode='json')
    if not decision['teach']:
        raise ValueError(decision['reason'])
    objectives={
        'verification':'先独立设计正常输入与空白输入的行为测试，再用当前项目证据核对结果',
        'judgment':'先能独立判断输入的正确处理顺序，并验证空白输入',
        'knowledge':'先区分有效内容和两端空白，再解释边界判断',
        'ai_collaboration':'先说明给 Coding Agent 的要求和可运行的验收办法',
    } if suite is b else suite.GOALS
    focus=experience.get('focus') or next((key for key in objectives if key in result['weaknesses']),None)
    objective=objectives.get(focus,decision['objective'])
    decision['reason']+=' 根据本次前测选择本轮优先练习。' if focus else ' 前测未暴露明确薄弱项，继续核对项目证据。'
    if experience:
        decision['reason']+=' 匹配的已验证经验支持该选择。'
    return {**decision,'objective':objective,'learning_goal':objective,'goal':objective,
            'goal_id':suite.SKILL,'skill_id':suite.SKILL,'target_capability_id':suite.SKILL,
            'knowledge_requirements':list(getattr(suite,'REQUIREMENTS',('字符串规范化','用实际结果核对预期'))),
            'prerequisites':['能读取操作结果'],
            'success_criteria':list(getattr(suite,'REQUIREMENTS',('正常输入保留','空白输入拒绝')))+['独立完成迁移'],
            'assessment_requirements':{'benchmark_version':suite.VERSION,'independent':True},
            'experience_ref':experience.get('ref'),'personal_evaluation_ref':earlier,
            'pre_evaluation_ref':eval_id,'pre_weaknesses':result['weaknesses'],'pre_focus':focus,
            'source':'decide_service_v0.2.1','checkpoint_id':checkpoint_id}
