"""Map stored project checkpoints into the V0.2.1 Decide service."""
import asyncio
from uuid import uuid4
from . import benchmark as b
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
    checkpoint_id=project['checkpoint_id']
    artifact='plan-'+checkpoint_id
    eval_id=result['evaluation_id']
    evidence=[{'id':artifact,'source':'project','kind':'plan','summary':'工作台已保存的待办项目计划',
               'content':'\n'.join(project['plan'])},
              {'id':eval_id,'source':'assessment','kind':'evaluation','summary':'本次独立前测'}]
    earlier=personal.get('evaluation_id')
    if earlier:
        evidence.append({'id':earlier,'source':'assessment','kind':'evaluation','summary':'同一本机档案先前在其他项目的评价'})
    weak='verification' in result['weaknesses']
    experience=validated if validated.get('focus') in result['weaknesses'] else {}
    request=DecideRequest.model_validate({
        'schema_version':'0.2.1','request_id':rid,'catalog':CATALOG,'content_policy':POLICY,
        'context':{'context_id':'ctx-'+rid,'session_id':session['id'],'checkpoint_id':checkpoint_id,
                   'project':{'stage':'verification','task_id':session['task_id'],'goal':project['title'],
                              'description':'核对表单输入边界','evidence_refs':[artifact] if project['plan'] else []},
                   'learner':{'student_id':session['learner_id'],'knowledge_states':[
                       {'knowledge_point_id':b.TOPIC,'level':'needs_support' if weak else 'guided',
                        'evidence_refs':[eval_id]}]},
                   'course':{'catalog_version':CATALOG['version'],'candidate_capability_ids':[b.SKILL],
                             'target_capability_ids':[b.SKILL] if experience else []},
                   'history':{'recent_evaluation_ids':[earlier] if earlier else []},'evidence':evidence}})
    decision=asyncio.run(DecideService().decide(request)).model_dump(mode='json')
    if not decision['teach']:
        raise ValueError(decision['reason'])
    objective=decision['objective']
    if experience:
        focus=experience['focus']
        objective={
            'verification':'先独立设计正常输入与空白输入的行为测试，再用当前项目证据核对结果',
            'judgment':'先能独立判断输入的正确处理顺序，并验证空白输入',
            'knowledge':'先区分有效内容和两端空白，再解释边界判断',
            'ai_collaboration':'先说明给 Coding Agent 的要求和可运行的验收办法',
        }.get(focus,objective)
        decision['reason']+=' 匹配的已验证经验支持优先补足当前前测暴露的薄弱项。'
    return {**decision,'objective':objective,'learning_goal':objective,'goal':objective,
            'goal_id':b.SKILL,'skill_id':b.SKILL,'target_capability_id':b.SKILL,
            'knowledge_requirements':['字符串规范化','用实际结果核对预期'],
            'prerequisites':['能读取表单提交结果'],
            'success_criteria':['正常输入保留','空白输入拒绝','独立完成迁移'],
            'assessment_requirements':{'benchmark_version':b.VERSION,'independent':True},
            'experience_ref':experience.get('ref'),'personal_evaluation_ref':earlier,
            'source':'decide_service_v0.2.1','checkpoint_id':checkpoint_id}
