"""Teaching subplans for the Teaching Agent.

The Coding Agent owns the project plan. This module treats it as read-only
context and adapts only the teaching path for the objective selected by decide.
"""
from copy import deepcopy
from uuid import uuid4


TEACHING_ACTIONS = frozenset({
    'ask', 'explain', 'example', 'hint', 'practice', 'ask_transfer',
})
WORKFLOW_ACTIONS = frozenset({'assess', 'pause'})
SUBPLAN_STATUSES = frozenset({
    'active', 'awaiting_evaluation', 'completed', 'paused', 'failed',
})
STEP_STATUSES = frozenset({'pending', 'running', 'completed', 'failed', 'skipped'})
EVALUATION_STATUSES = frozenset({
    'insufficient_evidence', 'unmet', 'partial', 'met',
})
DEFAULT_STEPS = (
    ('diagnose', 'ask', '了解学生当前的判断和已有依据。'),
    ('teach', 'explain', '针对当前目标补充必要概念或原理。'),
    ('apply', 'practice', '让学生把刚才的理解应用到当前项目。'),
    ('transfer', 'ask_transfer', '用一个不同情境检查学生能否独立迁移。'),
)
MAX_REPLANS_PER_SUBPLAN = 5
LEGACY_ACTIONS = ('ask', 'ask', 'hint', 'practice', 'practice', 'ask_transfer')


def _infer_legacy_action(text):
    """Migrate legacy prose steps by meaning; never infer an action from position."""
    rules = (
        ('ask_transfer', ('迁移', '新情境', '新场景', '不同情境', '其他场景')),
        ('example', ('示例', '例子', '演示', '对比例')),
        ('hint', ('提示', '线索', '引导')),
        ('practice', ('练习', '实践', '应用', '动手操作', '检查', '验证', '提出')),
        ('explain', ('讲解', '解释', '原理', '概念')),
        ('ask', ('了解', '询问', '追问', '说出', '描述', '预测', '判断', '思考')),
    )
    for action, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return action
    return None


def _normalize_steps(strategy):
    """Convert both old string steps and new structured steps to one schema."""
    if not isinstance(strategy, dict):
        raise ValueError('strategy 必须是对象')
    content = strategy.get('content', {})
    if not isinstance(content, dict):
        raise ValueError('strategy.content 必须是对象')
    steps = content.get('steps', [])
    if not isinstance(steps, list):
        raise ValueError('strategy.content.steps 必须是列表')

    normalized = []
    for index, step in enumerate(steps):
        if isinstance(step, str):
            _required_text(step, f'strategy.steps[{index}]', 500)
            action = _infer_legacy_action(step)
            if action is None:
                raise ValueError(f'strategy.steps[{index}] 无法判断教学动作，请人工整理: {step[:80]}')
            normalized.append({
                'id': f'legacy-step-{index + 1}',
                'action': action,
                'purpose': step,
                'status': 'pending',
            })
        elif isinstance(step, dict):
            if not isinstance(step.get('action'),str) or step.get('action') not in TEACHING_ACTIONS:
                raise ValueError(f'strategy.steps[{index}].action 无效')
            normalized.append({
                'id': step.get('id', f'step-{index + 1}'),
                'action': step['action'],
                'purpose': step.get('purpose') or step.get('instruction') or '按本步骤推进教学',
                'status': step.get('status', 'pending'),
            })
        else:
            raise ValueError(f'strategy.steps[{index}] 必须是字符串或对象')
    return normalized


def _required_text(value, field, limit=240):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{field} 必须是 1–{limit} 个字符的非空字符串')
    return value.strip()


def _decision_fields(decision):
    """Validate and normalize the canonical Decision contract."""
    if not isinstance(decision, dict):
        raise ValueError('缺少 decide() 决策对象')
    decision_id = _required_text(decision.get('decision_id'), 'decision_id', 128)
    goal_id = _required_text(decision.get('goal_id'), 'goal_id', 128)
    objective = _required_text(decision.get('objective'), 'objective', 500)
    knowledge_ids = decision.get('knowledge_point_ids', [])
    evidence_refs = decision.get('evidence_refs', [])
    criteria = decision.get('success_criteria', [])
    if not isinstance(knowledge_ids, list) or len(knowledge_ids) > 20 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 128 for item in knowledge_ids):
        raise ValueError('knowledge_point_ids 必须是最多20个非空字符串')
    if not isinstance(evidence_refs, list) or len(evidence_refs) > 50 or any(
            type(item) not in (int, str) or isinstance(item, str) and not item.strip() for item in evidence_refs):
        raise ValueError('evidence_refs 格式无效')
    if not isinstance(criteria, list) or len(criteria) > 20:
        raise ValueError('success_criteria 必须是最多20项的列表')
    normalized_criteria = []
    seen_criteria = set()
    for index, criterion in enumerate(criteria):
        if isinstance(criterion, str):
            criterion = {'criterion_id': f'criterion-{index + 1}', 'description': criterion, 'required': True}
        if (not isinstance(criterion, dict)
                or not isinstance(criterion.get('criterion_id'), str)
                or not criterion['criterion_id'].strip()
                or not isinstance(criterion.get('description'), str)
                or not criterion['description'].strip()
                or len(criterion['description'])>1000
                or len(criterion['criterion_id'])>128
                or type(criterion.get('required', True)) is not bool):
            raise ValueError('success_criteria 条目格式无效')
        criterion_id = criterion['criterion_id'].strip()
        if criterion_id in seen_criteria:
            raise ValueError(f'重复的验收标准 ID: {criterion_id}')
        seen_criteria.add(criterion_id)
        normalized_criteria.append({
            'criterion_id': criterion_id,
            'description': criterion['description'].strip(),
            'required': criterion.get('required', True),
        })
    if not normalized_criteria:
        normalized_criteria.append({
            'criterion_id': 'objective-evidence',
            'description': f'学生能基于真实证据独立解释当前目标：{objective.strip()}',
            'required': True,
        })
        normalized_criteria.append({
            'criterion_id': 'transfer-evidence',
            'description': f'学生能在不同情境中独立应用：{objective.strip()}',
            'required': True,
        })
    return {
        'decision_id': decision_id,
        'goal_id': goal_id,
        'objective': objective,
        'knowledge_point_ids': list(dict.fromkeys(knowledge_ids)),
        'evidence_refs': list(dict.fromkeys(evidence_refs)),
        'success_criteria': normalized_criteria,
    }


def _validate_step(step):
    if not isinstance(step, dict):
        raise ValueError('教学 Step 必须是对象')
    _required_text(step.get('id'), 'step.id', 128)
    if not isinstance(step.get('action'),str) or step.get('action') not in TEACHING_ACTIONS:
        raise ValueError(f"Step {step.get('id')} 的教学动作无效")
    _required_text(step.get('purpose'), 'step.purpose', 500)
    if not isinstance(step.get('status', 'pending'),str) or step.get('status', 'pending') not in STEP_STATUSES:
        raise ValueError(f"Step {step.get('id')} 的状态无效")
    knowledge_ids = step.get('knowledge_point_ids', [])
    if not isinstance(knowledge_ids, list) or any(not isinstance(item, str) or not item.strip() for item in knowledge_ids):
        raise ValueError(f"Step {step.get('id')} 的 knowledge_point_ids 无效")
    if step.get('execution_id') is not None and (not isinstance(step['execution_id'], str) or len(step['execution_id'])>128):
        raise ValueError(f"Step {step.get('id')} 的 execution_id 无效")
    if step.get('result_ref') is not None and (not isinstance(step['result_ref'], str) or len(step['result_ref'])>500):
        raise ValueError(f"Step {step.get('id')} 的 result_ref 无效")
    if step.get('failure_reason') is not None and (not isinstance(step['failure_reason'], str) or len(step['failure_reason'])>1000):
        raise ValueError(f"Step {step.get('id')} 的 failure_reason 无效")


def _validate_execution_result(result):
    if not isinstance(result, dict):
        raise ValueError('execution_result 必须是对象')
    for field in ('execution_id', 'subplan_id', 'step_id'):
        _required_text(result.get(field), f'execution_result.{field}', 128)
    if type(result.get('subplan_version')) is not int or result['subplan_version'] < 1:
        raise ValueError('execution_result.subplan_version 必须是正整数')
    if not isinstance(result.get('action'),str) or result.get('action') not in TEACHING_ACTIONS:
        raise ValueError('execution_result.action 无效')
    if type(result.get('success')) is not bool:
        raise ValueError('execution_result.success 必须是布尔值')
    if result.get('result_ref') is not None and (not isinstance(result['result_ref'], str) or len(result['result_ref'])>500):
        raise ValueError('execution_result.result_ref 格式无效')
    if result.get('failure_reason') is not None and (not isinstance(result['failure_reason'], str) or len(result['failure_reason'])>1000):
        raise ValueError('execution_result.failure_reason 格式无效')
    return result


def _validate_subplan(subplan):
    if not isinstance(subplan, dict):
        raise ValueError('Subplan 必须是对象')
    for field in ('id', 'decision_id', 'goal_id', 'objective'):
        _required_text(subplan.get(field), f'subplan.{field}', 500 if field == 'objective' else 128)
    if type(subplan.get('version')) is not int or subplan['version'] < 1:
        raise ValueError('subplan.version 必须是正整数')
    if not isinstance(subplan.get('status'),str) or subplan.get('status') not in SUBPLAN_STATUSES:
        raise ValueError('subplan.status 无效')
    steps = subplan.get('steps')
    if not isinstance(steps, list) or not steps:
        raise ValueError('subplan.steps 不能为空')
    seen = set()
    for step in steps:
        _validate_step(step)
        if step['id'] in seen:
            raise ValueError(f"重复的步骤 ID: {step['id']}")
        seen.add(step['id'])
    index = subplan.get('current_step_index')
    if type(index) is not int or not 0 <= index <= len(steps):
        raise ValueError('subplan.current_step_index 超出范围')
    criteria = subplan.get('success_criteria', [])
    if not isinstance(criteria, list) or len(criteria) > 20:
        raise ValueError('subplan.success_criteria 必须是最多20项的列表')
    criterion_ids = set()
    for criterion in criteria:
        if (not isinstance(criterion, dict)
                or not isinstance(criterion.get('criterion_id'), str)
                or not criterion['criterion_id'].strip()
                or not isinstance(criterion.get('description'), str)
                or not criterion['description'].strip()
                or len(criterion['criterion_id'])>128
                or len(criterion['description'])>1000
                or type(criterion.get('required', True)) is not bool):
            raise ValueError('subplan.success_criteria 条目格式无效')
        if criterion['criterion_id'] in criterion_ids:
            raise ValueError(f"重复的成功标准 ID: {criterion['criterion_id']}")
        criterion_ids.add(criterion['criterion_id'])
    learner_snapshot = subplan.get('learner_snapshot')
    if learner_snapshot is not None:
        if not isinstance(learner_snapshot, dict):
            raise ValueError('subplan.learner_snapshot 必须是对象')
        if (not isinstance(learner_snapshot.get('knowledge_point_ids'), list)
                or learner_snapshot.get('observed_level') not in
                {'unknown', 'needs_help', 'supported', 'independent', 'transfer_candidate'}
                or not isinstance(learner_snapshot.get('evidence_refs'), list)
                or learner_snapshot.get('status') not in {'unknown', 'provisional_not_certified'}):
            raise ValueError('subplan.learner_snapshot 字段无效')
    executions = subplan.get('execution_results', [])
    if not isinstance(executions, list) or len(executions)>1000:
        raise ValueError('subplan.execution_results 必须是最多1000项的列表')
    execution_ids = set()
    for result in executions:
        _validate_execution_result(result)
        if result['execution_id'] in execution_ids:
            raise ValueError(f"重复的执行 ID: {result['execution_id']}")
        execution_ids.add(result['execution_id'])
    replan_history=subplan.get('replan_history',[])
    if not isinstance(replan_history,list) or len(replan_history)>MAX_REPLANS_PER_SUBPLAN:
        raise ValueError('subplan.replan_history 超出允许范围')
    if any(not isinstance(item,dict) for item in replan_history):
        raise ValueError('subplan.replan_history 条目必须是对象')
    completion_refs=subplan.get('completion_evidence_refs',[])
    if not isinstance(completion_refs,list) or len(completion_refs)>50 or any(
            type(ref) not in (int,str) or isinstance(ref,str) and not ref.strip() for ref in completion_refs):
        raise ValueError('subplan.completion_evidence_refs 格式无效')
    if len(set(completion_refs))!=len(completion_refs):
        raise ValueError('subplan.completion_evidence_refs 不得重复')
    if subplan.get('last_applied_evaluation_id') is not None and not isinstance(subplan['last_applied_evaluation_id'],str):
        raise ValueError('subplan.last_applied_evaluation_id 格式无效')
    knowledge_ids = subplan.get('knowledge_point_ids', [])
    if not isinstance(knowledge_ids, list) or any(not isinstance(item, str) or not item.strip() for item in knowledge_ids):
        raise ValueError('subplan.knowledge_point_ids 无效')
    strategy_version = subplan.get('strategy_version')
    if strategy_version is not None and (type(strategy_version) is not int or strategy_version < 1):
        raise ValueError('subplan.strategy_version 必须是正整数或空值')
    strategy_id = subplan.get('strategy_id')
    if strategy_id is not None and (not isinstance(strategy_id, str) or not strategy_id.strip()):
        raise ValueError('subplan.strategy_id 格式无效')
    if (strategy_id is None) != (strategy_version is None):
        raise ValueError('strategy_id 与 strategy_version 必须同时存在或同时为空')
    return subplan


def _validate_evaluation(evaluation, valid_evidence_refs=None):
    """Validate the canonical Evaluation object before it can affect a plan."""
    if not isinstance(evaluation, dict):
        raise ValueError('Evaluation 必须是对象')
    allowed={'evaluation_id','decision_id','goal_id','subplan_id','subplan_version',
        'goal_status','evidence_refs','transfer_evidence_ref','confidence',
        'criterion_results','issue_kind','teaching_diagnosis'}
    if set(evaluation)-allowed:
        raise ValueError('Evaluation 包含未定义字段')
    for field in ('evaluation_id', 'decision_id', 'goal_id', 'subplan_id'):
        _required_text(evaluation.get(field), f'evaluation.{field}', 128)
    if 'status' in evaluation or 'assessment' in evaluation:
        raise ValueError('Evaluation 只允许使用 goal_status 作为权威状态字段')
    version = evaluation.get('subplan_version')
    if type(version) is not int or version < 1:
        raise ValueError('evaluation.subplan_version 必须是正整数')
    if not isinstance(evaluation.get('goal_status'),str) or evaluation.get('goal_status') not in EVALUATION_STATUSES:
        raise ValueError('evaluation.goal_status 无效')
    refs = evaluation.get('evidence_refs')
    if not isinstance(refs, list) or len(refs) > 50 or any(
            type(item) not in (int, str) or isinstance(item, str) and not item.strip() for item in refs):
        raise ValueError('evaluation.evidence_refs 格式无效')
    if len(set(refs))!=len(refs):
        raise ValueError('evaluation.evidence_refs 不得重复引用同一学生证据')
    if evaluation['goal_status'] != 'insufficient_evidence' and not refs:
        raise ValueError('有结论的 Evaluation 必须关联学生证据')
    if valid_evidence_refs is not None:
        known_refs = set(valid_evidence_refs)
        if any(ref not in known_refs for ref in refs):
            raise ValueError('Evaluation 引用了当前项目中不存在的学生证据')
    transfer_ref=evaluation.get('transfer_evidence_ref')
    if transfer_ref is not None and (type(transfer_ref) not in (int,str) or transfer_ref not in refs):
        raise ValueError('Evaluation 的迁移证据必须包含在学生证据列表中')
    if evaluation.get('goal_status')=='met' and transfer_ref is None:
        raise ValueError('目标完成必须关联独立迁移作答证据')
    results = evaluation.get('criterion_results', [])
    if not isinstance(results, list) or len(results) > 20:
        raise ValueError('evaluation.criterion_results 必须是最多20项的列表')
    seen_criterion_ids = set()
    for result in results:
        if (not isinstance(result, dict)
                or not isinstance(result.get('criterion_id'), str)
                or not result['criterion_id'].strip()
                or type(result.get('passed')) is not bool
                or not isinstance(result.get('reason', ''), str)):
            raise ValueError('evaluation.criterion_results 条目格式无效')
        if len(result['criterion_id'])>128 or len(result.get('reason',''))>1000:
            raise ValueError('evaluation.criterion_results 条目超出长度限制')
        if result['criterion_id'] in seen_criterion_ids:
            raise ValueError(f"重复的评估标准 ID: {result['criterion_id']}")
        seen_criterion_ids.add(result['criterion_id'])
    confidence = evaluation.get('confidence')
    if confidence is not None and (type(confidence) not in (int, float) or not 0 <= confidence <= 1):
        raise ValueError('evaluation.confidence 必须介于0和1之间')
    diagnosis = evaluation.get('teaching_diagnosis', {})
    if not isinstance(diagnosis, dict) or set(diagnosis)-{'error_type','misconceptions','recommended_action','reason'}:
        raise ValueError('evaluation.teaching_diagnosis 必须是对象')
    if diagnosis.get('error_type') not in (None, 'conceptual_gap', 'procedural_gap',
            'application_gap', 'execution_error', 'transfer_gap', 'insufficient_evidence'):
        raise ValueError('evaluation.teaching_diagnosis.error_type 无效')
    misconceptions=diagnosis.get('misconceptions',[])
    if not isinstance(misconceptions,list) or len(misconceptions)>3 or any(not isinstance(item,str) or len(item)>240 for item in misconceptions):
        raise ValueError('evaluation.teaching_diagnosis.misconceptions 无效')
    if diagnosis.get('recommended_action') not in (*TEACHING_ACTIONS,None):
        raise ValueError('evaluation.teaching_diagnosis.recommended_action 无效')
    if not isinstance(diagnosis.get('reason',''),str) or len(diagnosis.get('reason',''))>500:
        raise ValueError('evaluation.teaching_diagnosis.reason 无效')
    if evaluation.get('issue_kind') not in (None,'hypothesis','confirmed','none'):
        raise ValueError('evaluation.issue_kind 无效')
    return evaluation


def _create_subplan(decision, learner_state, strategy, project_context):
    """Create a teaching-only subplan for one decide() objective."""
    fields = _decision_fields(decision)
    steps = _normalize_steps(strategy) or [
        {'id': sid, 'action': action, 'purpose': purpose}
        for sid, action, purpose in DEFAULT_STEPS
    ]
    knowledge_state = learner_state.get('learning', {}).get('knowledge_state', {})
    if not isinstance(knowledge_state, dict):
        knowledge_state = {}
    relevant_ids = fields['knowledge_point_ids'] or [fields['goal_id']]
    known = [knowledge_state[key] for key in relevant_ids
             if isinstance(knowledge_state.get(key), dict)]
    ranks = {'needs_help': 0, 'unknown': 0, 'supported': 1,
             'independent': 2, 'transfer_candidate': 3}
    signal = min((item.get('level', 'unknown') for item in known),
                 key=lambda level: ranks.get(level, 0), default='unknown')
    if known and signal == 'supported':
        steps = [step for step in steps if step['action'] != 'explain']
        if not any(step['action'] == 'example' for step in steps):
            steps.insert(0, {'id': 'adaptive-example', 'action': 'example',
                             'purpose': '基于已有部分理解，用短例子补足尚不稳固的部分。'})
    elif known and signal in {'independent', 'transfer_candidate'}:
        # These are provisional observations, so shorten the route only by
        # adding a fresh independent calibration task, not by certifying mastery.
        steps = [
            {'id': 'adaptive-practice', 'action': 'practice',
             'purpose': '用当前项目中的新例子校准学生能否独立运用已有理解。'},
            {'id': 'adaptive-transfer', 'action': 'ask_transfer',
             'purpose': '用不同情境的任务检查已有理解能否迁移；不预先给出答案。'},
        ]
    if not steps:
        steps = [
            {'id': 'adaptive-practice', 'action': 'practice',
             'purpose': '让学生围绕当前目标完成一次可观察的独立应用。'},
            {'id': 'adaptive-transfer', 'action': 'ask_transfer',
             'purpose': '在不同情境中检查理解能否迁移。'},
        ]
    learner_snapshot = {
        'knowledge_point_ids': relevant_ids,
        'observed_level': signal,
        'evidence_refs': list(dict.fromkeys(
            ref for item in known for ref in item.get('evidence_ids', []) if type(ref) in (int, str))),
        'status': 'provisional_not_certified' if known else 'unknown',
    }
    objective = fields['objective'] or '围绕当前决策目标了解、解释并检查学生的理解。'
    for step in steps:
        step.setdefault('status', 'pending')
        step.setdefault('knowledge_point_ids', [])
        step.setdefault('execution_id', None)
        step.setdefault('failure_reason', None)
    subplan = {
        'id': str(uuid4()),
        **fields,
        'version': 1,
        'objective': objective,
        'steps': steps,
        'current_step_index': 0,
        'status': 'active',
        'success_criteria': fields['success_criteria'],
        'learner_snapshot': learner_snapshot,
        'strategy_id': strategy.get('id'),
        'strategy_version': strategy.get('version'),
        'project_plan_snapshot': deepcopy(project_context.get('coding_plan', [])),
        'last_applied_evaluation_id': None,
        'execution_results': [],
        'replan_reason': None,
        'replan_history': [],
    }
    return _validate_subplan(subplan)


def _evaluation_signal(evaluation):
    """Read the single canonical evaluation status without guessing aliases."""
    if not isinstance(evaluation, dict):
        return None
    status = evaluation.get('goal_status')
    if not isinstance(status, str):
        return None
    status = status.strip().lower()
    return status if status in EVALUATION_STATUSES else None


def _validated_completion_status(subplan, evaluation):
    """Do not complete a goal from a label alone; require evidence per required criterion."""
    if _evaluation_signal(evaluation) != 'met':
        return _evaluation_signal(evaluation), None
    criteria = subplan.get('success_criteria', [])
    required = [item for item in criteria if item.get('required', True)]
    if not evaluation.get('evidence_refs'):
        return 'insufficient_evidence', '完成评估缺少学生证据'
    if evaluation.get('transfer_evidence_ref') not in evaluation.get('evidence_refs',[]):
        return 'insufficient_evidence', '完成评估缺少独立迁移作答证据'
    if not required:
        return 'insufficient_evidence', '当前目标没有定义必需的成功标准'
    results = evaluation.get('criterion_results', [])
    result_by_id = {item['criterion_id']: item for item in results}
    required_ids = {item['criterion_id'] for item in required}
    unknown_ids = set(result_by_id) - {item['criterion_id'] for item in criteria}
    if unknown_ids:
        return 'insufficient_evidence', '评估引用了未定义的成功标准'
    if any(item['criterion_id'] not in result_by_id for item in required):
        return 'insufficient_evidence', '并非所有必需的成功标准都已评估'
    if any(not result_by_id[criterion_id]['passed'] for criterion_id in required_ids):
        return 'partial', '至少一项必需的成功标准尚未通过'
    return 'met', None


def _replan_subplan(subplan, evaluation):
    """Adjust only the current teaching route; never edit the Coding plan."""
    signal = _evaluation_signal(evaluation)
    if signal not in {'insufficient_evidence', 'unmet', 'partial'}:
        return subplan, None
    if len(subplan.get('replan_history', [])) >= MAX_REPLANS_PER_SUBPLAN:
        revised=deepcopy(subplan)
        revised['status']='paused'
        reason=f'已达到 {MAX_REPLANS_PER_SUBPLAN} 次重新规划上限，需要人工检查目标或成功标准。'
        revised['replan_reason']=reason
        return revised,reason

    current_index = subplan.get('current_step_index', 0)
    if type(current_index) is not int or current_index < 0:
        current_index = 0
    previous_steps = deepcopy(subplan.get('steps', []))
    completed_history = deepcopy(previous_steps[:current_index])
    remaining = deepcopy(previous_steps[current_index:])
    if remaining and remaining[0].get('status') == 'failed':
        failed_step = remaining.pop(0)
        failed_step['status'] = 'skipped'
        failed_step['skip_reason'] = '评估后由针对性新步骤替代；原失败记录保留在子计划历史中。'
        completed_history.append(failed_step)
    diagnosis = evaluation.get('teaching_diagnosis', {})
    if not isinstance(diagnosis, dict):
        diagnosis = {}
    misconceptions = diagnosis.get('misconceptions', [])
    if not isinstance(misconceptions, list):
        misconceptions = []
    suggested = diagnosis.get('recommended_action')
    defaults = {
        'insufficient_evidence': ('ask', '现有学生证据不足以判断理解。'),
        'unmet': ('example', '评估显示目标尚未达成，需针对困难补充支持。'),
        'partial': ('practice', '评估显示已有部分理解，可用针对性练习巩固。'),
    }
    default_action, default_reason = defaults[signal]
    diagnosis_actions = {
        'conceptual_gap': 'explain', 'procedural_gap': 'example',
        'application_gap': 'practice', 'execution_error': 'hint',
        'transfer_gap': 'ask_transfer', 'insufficient_evidence': 'ask',
    }
    compatible = {
        'conceptual_gap': {'explain', 'example'},
        'procedural_gap': {'example', 'practice'},
        'application_gap': {'practice', 'ask_transfer'},
        'execution_error': {'hint', 'example'},
        'transfer_gap': {'ask_transfer', 'practice'},
        'insufficient_evidence': {'ask'},
    }
    error_type = diagnosis.get('error_type')
    diagnosed_action = diagnosis_actions.get(error_type)
    if signal == 'insufficient_evidence':
        action = 'ask'
    elif diagnosed_action:
        action = suggested if suggested in compatible[error_type] else diagnosed_action
    else:
        action = suggested if suggested in TEACHING_ACTIONS else default_action
    reason = diagnosis.get('reason') or default_reason
    misconception = next((item for item in misconceptions
                          if isinstance(item, str) and item.strip()), '')
    purposes = {
        'ask': '请学生具体说明当前判断及其依据，不预设其已经理解。',
        'hint': '给出一个最小线索，让学生继续自己推理。',
        'explain': '围绕当前困难简短解释相关概念，再请学生用自己的话说明。',
        'example': '用一个小型对比例子帮助辨析困难，再让学生自己应用。',
        'practice': '让学生在当前目标的另一个具体情境中独立应用。',
        'ask_transfer': '给出不同情境的迁移问题，不先提供提示或答案。',
    }
    step_id = f'{action}-v{subplan.get("version", 1) + 1}'
    purpose = purposes[action]
    if misconception:
        purpose += f' 重点关注：{misconception[:240]}'
    inserted = {'id': step_id, 'action': action, 'purpose': purpose}

    revised = deepcopy(subplan)
    previous_version = revised.get('version', 1)
    revised['version'] = previous_version + 1
    revised['steps'] = completed_history + [inserted] + remaining
    for step in revised['steps']:
        step.setdefault('knowledge_point_ids', [])
        step.setdefault('execution_id', None)
        step.setdefault('failure_reason', None)
    revised['current_step_index'] = len(completed_history)
    revised['status'] = 'active'
    revised['replan_reason'] = reason
    revised.setdefault('replan_history', []).append({
        'from_version': previous_version,
        'to_version': revised['version'],
        'reason': reason,
        'previous_current_step_index': current_index,
        'previous_steps': previous_steps,
        'previous_execution_results': deepcopy(subplan.get('execution_results', [])),
        'evaluation_refs': evaluation.get('evidence_refs', evaluation.get('evidence_ids', [])),
    })
    return revised, reason


def _next_step(subplan, action='message'):
    """Select the current subplan step, unless a workflow action takes priority."""
    steps = subplan.get('steps', [])
    index = subplan.get('current_step_index', 0)
    if type(index) is not int or index < 0:
        index = 0
    if subplan.get('status') == 'completed':
        return {
            'step_id': None, 'step_index': index, 'step_count': len(steps),
            'action': 'pause', 'subplan_action': 'pause', 'action_source': 'subplan',
            'instruction': '当前教学目标已有达成证据；等待 decide() 选择下一个目标。',
            'status': 'completed',
        }
    if subplan.get('status') in {'paused', 'failed'}:
        return {
            'step_id': None, 'step_index': index, 'step_count': len(steps),
            'action': 'pause', 'subplan_action': 'pause', 'action_source': 'workflow',
            'instruction': f"当前教学子计划状态为 {subplan['status']}，需要外部恢复或处理。",
            'status': subplan['status'],
        }
    if subplan.get('status') == 'awaiting_evaluation':
        requested = 'assess' if action == 'evaluate' else 'pause'
        return {
            'step_id': None, 'step_index': index, 'step_count': len(steps),
            'action': requested, 'subplan_action': requested, 'action_source': 'workflow',
            'instruction': '教学步骤已执行完，等待基于学生证据的正式评估。',
            'status': 'awaiting_evaluation',
        }
    if index >= len(steps):
        subplan['status'] = 'awaiting_evaluation'
        requested = 'assess' if action == 'evaluate' else 'pause'
        return {
            'step_id': None, 'step_index': index, 'step_count': len(steps),
            'action': requested, 'subplan_action': requested, 'action_source': 'workflow',
            'instruction': '教学步骤已执行完，等待基于学生证据的正式评估。',
            'status': 'awaiting_evaluation',
        }
    if action == 'evaluate':
        return {
            'step_id': None, 'step_index': index, 'step_count': len(steps),
            'action': 'assess', 'subplan_action': 'assess', 'action_source': 'workflow',
            'instruction': '根据学生已有原话证据评估当前目标，不把教师讲解当作掌握证据。',
            'status': subplan.get('status', 'active'),
        }
    if action == 'pause':
        return {
            'step_id': None, 'step_index': index, 'step_count': len(steps),
            'action': 'pause', 'subplan_action': 'pause', 'action_source': 'workflow',
            'instruction': '按当前请求暂停本轮教学，不推进子计划步骤。',
            'status': subplan.get('status', 'active'),
        }
    if action == 'knowledge':
        return {
            'step_id': None, 'step_index': index, 'step_count': len(steps),
            'action': 'explain', 'subplan_action': None, 'action_source': 'workflow',
            'instruction': '讲解学生主动选择的技术主题，不推进当前教学子计划步骤。',
            'status': subplan.get('status', 'active'),
        }
    step = steps[index] if index < len(steps) else None
    if step and step.get('status') == 'failed':
        return {
            'step_id': step.get('id'), 'step_index': index, 'step_count': len(steps),
            'action': 'pause', 'subplan_action': 'pause', 'action_source': 'workflow',
            'instruction': step.get('failure_reason') or '上一步教学动作执行失败，等待评估或重新规划。',
            'status': 'failed',
        }
    strategy_action = step.get('action', 'ask') if step else 'ask'
    requested_action = strategy_action
    action_source = 'subplan'
    if action == 'evaluate':
        requested_action, action_source = 'assess', 'workflow'
    elif action == 'knowledge':
        requested_action, action_source = 'explain', 'workflow'
    return {
        'step_id': step.get('id') if step else None,
        'step_index': index,
        'step_count': len(steps),
        'action': requested_action,
        'subplan_action': strategy_action,
        'action_source': action_source,
        'instruction': step.get('purpose') if step else '围绕当前目标选择一个简短、可观察的教学动作。',
        'status': step.get('status', 'pending') if step else 'pending',
    }


def teach(decision, learner_state, strategy, project_context, action='message'):
    """Create or adapt a teaching subplan and return its next action.

    The Coding Agent's plan is passed as read-only context. The target objective
    comes from decide(); this function may adapt only how that objective is taught.
    It is deterministic apart from generating a new ID for a newly created plan.
    """
    if not isinstance(action,str) or action not in {'message', 'review', 'evaluate', 'knowledge', 'reconcile'} | TEACHING_ACTIONS | WORKFLOW_ACTIONS:
        raise ValueError(f'teach action 无效: {action!r}')
    if not isinstance(learner_state, dict):
        raise ValueError('learner_state 必须是对象')
    if not isinstance(strategy, dict):
        raise ValueError('strategy 必须是对象')
    if not isinstance(project_context, dict):
        raise ValueError('project_context 必须是对象')
    strategy_id = strategy.get('id')
    strategy_version = strategy.get('version')
    if strategy_id is not None:
        _required_text(strategy_id, 'strategy.id', 128)
        if type(strategy_version) is not int or strategy_version < 1:
            raise ValueError('strategy.version 必须是正整数')
    elif strategy_version is not None:
        raise ValueError('strategy.version 不能脱离 strategy.id')
    if 'subplans' in learner_state and not isinstance(learner_state['subplans'], dict):
        raise ValueError('learner_state.subplans 必须是对象')
    if 'hint_level' in learner_state and (type(learner_state['hint_level']) is not int or not 0 <= learner_state['hint_level'] <= 3):
        raise ValueError('learner_state.hint_level 必须是0到3的整数')
    if 'coding_plan' in project_context and not isinstance(project_context['coding_plan'], list):
        raise ValueError('project_context.coding_plan 必须是列表')
    if 'valid_evidence_refs' in project_context and not isinstance(project_context['valid_evidence_refs'], list):
        raise ValueError('project_context.valid_evidence_refs 必须是列表')
    if 'valid_evidence_refs' in project_context and any(
            type(item) not in (int, str) or isinstance(item, str) and not item.strip()
            for item in project_context['valid_evidence_refs']):
        raise ValueError('project_context.valid_evidence_refs 条目格式无效')

    fields = _decision_fields(decision)
    plans = learner_state.get('subplans', {})
    _normalize_steps(strategy)
    key = fields['decision_id']
    active = plans.get(key)
    created = not isinstance(active, dict)
    if created:
        subplan = _create_subplan(decision, learner_state, strategy, project_context)
    else:
        subplan = deepcopy(_validate_subplan(active))
        if subplan['goal_id'] != fields['goal_id']:
            raise ValueError('decision_id 已用于另一个 goal_id，必须为新目标生成新的 decision_id')

    evaluation = learner_state.get('last_evaluation')
    reason = None
    evaluation_matches = False
    evaluation_stale = False
    evaluation_applied = False
    if evaluation is not None:
        try:
            _validate_evaluation(evaluation, project_context.get('valid_evidence_refs'))
            evaluation_matches = (
                evaluation['decision_id'] == subplan['decision_id']
                and evaluation['goal_id'] == subplan['goal_id']
                and evaluation['subplan_id'] == subplan['id']
                and evaluation['subplan_version'] == subplan['version']
            )
            evaluation_stale = not evaluation_matches
        except ValueError:
            # Persisted records from the previous schema are stale, not actionable.
            evaluation_stale = True
    if not created and evaluation_matches:
        evaluation_id = evaluation.get('evaluation_id') or evaluation.get('revision')
        already_applied = (
            evaluation_id is not None
            and evaluation_id == subplan.get('last_applied_evaluation_id')
        ) or (evaluation_id is None and evaluation == subplan.get('last_applied_evaluation'))
        if not already_applied:
            completion_status, completion_issue = _validated_completion_status(subplan, evaluation)
            effective_evaluation = deepcopy(evaluation)
            effective_evaluation['goal_status'] = completion_status
            if completion_issue:
                effective_evaluation['completion_validation_issue'] = completion_issue
            if completion_status == 'met':
                subplan['status'] = 'completed'
                subplan['completion_evidence_refs'] = deepcopy(
                    evaluation.get('evidence_refs', evaluation.get('evidence_ids', [])))
            else:
                subplan, reason = _replan_subplan(subplan, effective_evaluation)
            subplan['last_applied_evaluation'] = effective_evaluation
            subplan['last_applied_evaluation_id'] = evaluation_id
            evaluation_applied = True

    subplan = _validate_subplan(subplan)
    next_step = _next_step(subplan, action)
    return {
        **fields,
        'subplan': subplan,
        'subplan_created': created,
        'subplan_replanned': reason is not None,
        'subplan_updated': evaluation_applied,
        'replan_reason': reason,
        'evaluation_stale': evaluation_stale,
        'next_step': next_step,
        'strategy_id': subplan.get('strategy_id'),
        'strategy_version': subplan.get('strategy_version'),
        'hint_level': learner_state.get('hint_level', 0),
        'project_stage': project_context.get('stage'),
        'coding_plan_read_only': True,
        'coding_plan': deepcopy(project_context.get('coding_plan', [])),
        'allowed_actions': sorted(TEACHING_ACTIONS),
        'workflow_actions': sorted(WORKFLOW_ACTIONS),
    }


def store_subplan(learner_state, method, enabled=True):
    """Persist a created, resumed, or replanned subplan without executing a step."""
    if not enabled:
        return {'updated': False, 'reason': 'disabled'}
    if not isinstance(learner_state, dict) or not isinstance(method, dict):
        raise ValueError('保存 Subplan 的状态或计划格式无效')
    planned = method.get('subplan')
    if not isinstance(planned, dict):
        raise ValueError('Teaching method 缺少 Subplan')
    fields = _decision_fields(method)
    planned = deepcopy(_validate_subplan(planned))
    if planned['decision_id'] != fields['decision_id'] or planned['goal_id'] != fields['goal_id']:
        raise ValueError('保存 Subplan 时 Decision 身份不一致')
    plans = learner_state.setdefault('subplans', {})
    if not isinstance(plans, dict):
        raise ValueError('learner_state.subplans 必须是对象')
    key = fields['decision_id']
    current = plans.get(key)
    if current is None:
        if not method.get('subplan_created'):
            raise ValueError('当前 Subplan 已不存在，拒绝保存过期计划')
        planned.setdefault('execution_results', [])
    else:
        current = _validate_subplan(current)
        if current['id'] != planned['id'] or current['goal_id'] != planned['goal_id']:
            raise ValueError('Subplan 身份已变化，拒绝覆盖')
        if planned['version'] < current['version']:
            raise ValueError('Subplan 版本已过期，拒绝覆盖')
        if planned['version'] > current['version'] and not (
                method.get('subplan_replanned') or method.get('subplan_updated')):
            raise ValueError('Subplan 未经重新规划授权，不得升级版本')
        if planned['version'] == current['version']:
            old_shape=[(x['id'],x['action'],x['purpose']) for x in current['steps']]
            new_shape=[(x['id'],x['action'],x['purpose']) for x in planned['steps']]
            if old_shape != new_shape and not (method.get('subplan_replanned') or method.get('subplan_updated')):
                raise ValueError('同版本 Subplan 步骤发生变化，拒绝覆盖')
            for field in ('objective','success_criteria','knowledge_point_ids','strategy_id',
                          'strategy_version','learner_snapshot','project_plan_snapshot'):
                if current.get(field) != planned.get(field):
                    raise ValueError(f'同版本 Subplan 的 {field} 不得变化')
            allowed_statuses = {
                'completed': {'completed'},
                'awaiting_evaluation': {'awaiting_evaluation', 'completed'},
                'failed': {'failed'},
                'paused': {'paused', 'active'},
                'active': {'active', 'awaiting_evaluation', 'paused', 'failed', 'completed'},
            }
            if planned['status'] not in allowed_statuses[current['status']]:
                raise ValueError('Subplan 状态倒退或非法变化')
            if planned['status'] == 'completed' and not method.get('subplan_updated'):
                raise ValueError('Subplan 只能由已应用的达标评估标记完成')
            if planned['status'] == 'completed':
                applied_evaluation=planned.get('last_applied_evaluation')
                if not isinstance(applied_evaluation,dict) or _validated_completion_status(planned,applied_evaluation)[0]!='met':
                    raise ValueError('Subplan 完成状态缺少满足标准的评估证据')
            if planned['current_step_index'] < current['current_step_index']:
                raise ValueError('Subplan 进度倒退，拒绝覆盖')
            if planned['current_step_index'] > current['current_step_index'] and any(
                    step.get('status') not in ('completed','skipped')
                    for step in planned['steps'][current['current_step_index']:planned['current_step_index']]):
                raise ValueError('Subplan 进度不能越过未完成步骤')
            for old_step,new_step in zip(current['steps'],planned['steps']):
                if old_step['status'] in ('completed','skipped') and new_step['status']!=old_step['status']:
                    raise ValueError('同版本 Subplan 不得重置已完成或跳过的步骤')
                if old_step['status']=='failed' and new_step['status'] not in ('failed','skipped'):
                    raise ValueError('同版本 Subplan 不得清除失败步骤；请生成新版本重新规划')
            planned['execution_results']=deepcopy(current.get('execution_results',[]))
    plans[key] = planned
    learner_state['active_decision_id'] = key
    return {'updated': True, 'subplan_id': planned['id'], 'version': planned['version']}


def record_step(learner_state, method, execution_result, enabled=True):
    """Record one execution attempt; advance only after a matching success."""
    if not enabled:
        return {'updated': False, 'reason': 'disabled'}
    result = _validate_execution_result(execution_result)
    if not isinstance(learner_state, dict) or not isinstance(method, dict):
        raise ValueError('执行 Step 的状态或计划格式无效')
    fields = _decision_fields(method)
    key = fields['decision_id']
    plans = learner_state.get('subplans')
    if not isinstance(plans, dict):
        raise ValueError('learner_state.subplans 必须是对象')
    stored = plans.get(key)
    if stored is None and method.get('subplan_created'):
        store_subplan(learner_state, method, enabled=True)
        plans = learner_state['subplans']
        stored = plans.get(key)
    if not isinstance(stored, dict):
        raise ValueError('当前 Subplan 不存在，拒绝记录执行结果')
    stored = _validate_subplan(stored)
    planned = method.get('subplan')
    if not isinstance(planned, dict):
        raise ValueError('Teaching method 缺少 Subplan')
    planned = _validate_subplan(planned)
    next_step = method.get('next_step', {})
    if not isinstance(next_step,dict) or next_step.get('action_source')!='subplan':
        raise ValueError('execution_result 只能记录当前 Subplan 教学步骤')
    if stored['decision_id'] != key or planned['decision_id'] != key:
        raise ValueError('Execution result 的 Decision ID 不匹配')
    if (result['subplan_id'] != stored['id'] or result['subplan_id'] != planned['id']
            or result['subplan_version'] != stored['version']
            or result['subplan_version'] != planned['version']):
        raise ValueError('Stale execution result: Subplan ID 或版本不匹配')
    if result['step_id'] != next_step.get('step_id'):
        raise ValueError('Stale execution result: Step ID 不匹配')

    executions = stored.setdefault('execution_results', [])
    existing = next((item for item in executions if item['execution_id']==result['execution_id']), None)
    if existing:
        if any(existing.get(field) != result.get(field) for field in result):
            raise ValueError('execution_id 已被不同执行结果使用')
        return {'updated': False, 'duplicate': True, 'subplan_id': stored['id'],
                'version': stored['version'], 'advanced': bool(existing.get('advanced'))}

    # Validate the stored and caller snapshots before any mutation. A caller may
    # only report the currently active step and may not overwrite newer progress.
    if stored['current_step_index'] != planned['current_step_index']:
        raise ValueError('Stale execution result: Subplan 进度已变化')
    if stored['status'] != planned['status']:
        raise ValueError('Stale execution result: 当前步骤状态已变化')

    index = stored['current_step_index']
    if index >= len(stored['steps']) or stored['steps'][index]['id'] != result['step_id']:
        raise ValueError('Stale execution result: Step 已不再是当前待执行步骤')
    step = stored['steps'][index]
    planned_step = planned['steps'][index]
    if (step['id'] != planned_step['id'] or step['action'] != planned_step['action']
            or step['status'] != planned_step['status']):
        raise ValueError('Stale execution result: 当前 Step 状态或动作已变化')
    if step.get('status') not in ('pending', 'running'):
        raise ValueError('当前 Step 不处于待执行状态')
    action_matches = (result['action'] == step['action']
                      and result['action'] == next_step.get('subplan_action'))
    advanced = False
    if not result['success']:
        step['status'] = 'failed'
        step['execution_id'] = result['execution_id']
        step['failure_reason'] = result.get('failure_reason') or '教学动作执行失败'
    elif action_matches:
        step['status'] = 'completed'
        step['execution_id'] = result['execution_id']
        step['failure_reason'] = None
        step['result_ref'] = result.get('result_ref')
        stored['current_step_index'] += 1
        advanced = True
        if stored['current_step_index'] >= len(stored['steps']):
            stored['status'] = 'awaiting_evaluation'
    else:
        step['status'] = 'failed'
        step['execution_id'] = result['execution_id']
        step['failure_reason'] = '实际教学动作与计划动作不一致'
    history = {**result, 'advanced': advanced}
    executions.append(history)
    learner_state['subplans'][key] = stored
    learner_state['active_decision_id'] = key
    return {'updated': True, 'duplicate': False, 'subplan_id': stored['id'],
            'version': stored['version'], 'advanced': advanced,
            'reason': None if advanced else ('execution_failed' if not result['success'] else 'action_mismatch')}


def needs_evaluation(learner_state):
    """Return whether the current stored teaching route has exhausted its steps."""
    plans = learner_state.get('subplans', {}) if isinstance(learner_state, dict) else {}
    if not isinstance(plans, dict):
        return False
    active_id = learner_state.get('active_decision_id')
    if active_id is not None:
        plan = plans.get(active_id)
        return bool(isinstance(plan, dict) and (
            plan.get('status') == 'awaiting_evaluation'
            or plan.get('status') == 'active'
            and type(plan.get('current_step_index')) is int
            and plan['current_step_index'] >= len(plan.get('steps', []))))
    return any(
        isinstance(plan, dict)
        and (plan.get('status') == 'awaiting_evaluation'
             or plan.get('status') == 'active'
             and type(plan.get('current_step_index')) is int
             and plan['current_step_index'] >= len(plan.get('steps', [])))
        for plan in plans.values()
    )


def update_hint_level(current, request_action, output):
    """Adjust assistance gradually from evaluation evidence and the chosen teaching move."""
    if type(current) is not int or not 0 <= current <= 3:
        raise ValueError('hint_level 必须是0到3的整数')
    if not isinstance(output, dict):
        raise ValueError('教学输出必须是对象')
    suggested = output.get('hint_level', current)
    if type(suggested) is not int or not 0 <= suggested <= 3:
        raise ValueError('输出 hint_level 必须是0到3的整数')
    if request_action == 'evaluate':
        assessment = output.get('assessment')
        if assessment == 'developing':
            return min(3, max(current, suggested) + 1)
        if assessment == 'candidate':
            return max(0, min(current, suggested) - 1)
        return current
    if output.get('teaching_action') in {'ask', 'practice', 'ask_transfer'}:
        return min(current, suggested)
    return max(current, suggested)
