from pathlib import Path
from contracts import *

FIX = Path(__file__).parent / "fixtures"
FIX.mkdir(exist_ok=True)

def save(name, model):
    (FIX / f"{name}.json").write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")

cap = Capability(
    id="requirements", title="需求与边界判断",
    behaviors=["说清目标用户和功能", "补充边界条件", "提出可验证的验收条件"],
    knowledge_point_ids=["acceptance-criteria", "edge-cases"],
    rubric_id="requirements", skill_id="skill-requirements-review"
)
kps = [
    KnowledgePoint(id="acceptance-criteria", capability_id="requirements",title="验收条件",project_stages=[Stage.planning,Stage.verification]),
    KnowledgePoint(id="edge-cases", capability_id="requirements",title="边界情形",project_stages=[Stage.planning,Stage.verification]),
]
rub = Rubric(id="requirements", version=1, capability_id="requirements", criteria=[
    Criterion(id="identify-boundary", description="能提出至少一个有意义的边界情况", max_score=2),
    Criterion(id="define-acceptance", description="能明确期望结果与验收方式", max_score=2),
], pass_score=3)
catalog = CourseCatalog(version="1", capabilities=[cap], knowledge_points=kps, rubrics=[rub])
ctx = TeachingContext(context_id="ctx-001",session_id="sess-001",checkpoint_id="cp-001",
    project=ProjectSnapshot(stage="planning",task_id="task-001",goal="制作一个可以跳跃躲避障碍的小游戏",evidence_refs=["plan-001"]),
    learner=LearnerSnapshot(student_id="learner-01",prior_help_count=2,knowledge_states=[
        KnowledgeState(knowledge_point_id="acceptance-criteria",level="needs_support", evidence_refs=["eval-001"])
    ]),
    course=CourseSnapshot(catalog_version="1",candidate_capability_ids=["requirements"],target_capability_ids=["requirements"]),
    evidence=[
        Evidence(id="plan-001",source="project",kind="plan",summary="开发计划包含跳跃和障碍生成，但没有验收说明",content="1. 实现跳跃；2. 生成障碍；3. 完成游戏"),
        Evidence(id="eval-001",source="assessment",kind="evaluation",summary="此前回答未说明如何检验功能是否符合需求"),
    ])
content = ContentPolicy(id="default-content",version=1,rules=[Rule(when="学生缺少验收条件概念且当前有计划可审查",action="优先教授验收标准")],stop_conditions=["缺少可靠证据则跳过教学"])
strategy = TeachingStrategy(id="guided-discovery",version=1,capability_ids=["requirements"],learner_condition="需要帮助理解验收条件",steps=[StrategyStep(action_type="ask",instruction="先询问学生如何证明功能完成"), StrategyStep(action_type="explain", instruction="按需讲解可观察的验收条件")],stop_conditions=["学生能独立提出验证方式", "独立迁移考核完成"])

save("course_catalog",catalog)
save("teaching_context",ctx)
save("content_policy",content)
save("teaching_strategy",strategy)
second_strategy = TeachingStrategy(
    id="examples-first", version=1, capability_ids=["requirements"],
    learner_condition="在提问后依然难以提出明确验收条件",
    steps=[StrategyStep(action_type="example", instruction="先对比有无验收条件的例子"),
           StrategyStep(action_type="explain", instruction="讲解可观察、可验证标准")],
    stop_conditions=["学生能独立设计验收条件", "独立迁移评估完成"],
)

dr = DecideRequest(request_id="req-001",context=ctx,catalog=catalog,content_policy=content)
dres = TeachingDecision(request_id="req-001",decision_id="decision-001",context_id=ctx.context_id,teach=True,capability_id="requirements",knowledge_point_ids=["acceptance-criteria"],evidence_refs=["plan-001","eval-001"],reason="本次计划没有明确可检验的完成标准，且学生此前在此项需要帮助",objective="能够独立提出一个可验证的验收条件",content_policy_id=content.id,content_policy_version=content.version)
save("decide_request", dr)
save("decide_response", dres)

tr = TeachRequest(request_id="req-002",context=ctx,decision=dres,phase="diagnosis",turn_index=0,
    strategy_candidates=[strategy, second_strategy],
    active_strategy=None,allow_strategy_switch=False,
    teaching_history=TeachingHistory(),knowledge_packages=[KnowledgePackage(knowledge_point_id="acceptance-criteria",concepts=["验收条件应描述可观察的期望行为"],examples=["按下空格键且角色站在地面时，角色应向上跳起"],misconceptions=["只写功能正常，不说明如何观察和验证"],source_refs=["课程内容组提供"] )])
tres = TeachingTurn(request_id="req-002",turn_id="turn-001",decision_id=dres.decision_id,strategy_id=strategy.id,strategy_version=strategy.version,
    strategy_selection_mode="initial",strategy_selection_reason="当前学生需要初步诊断，先采用引导发现策略",phase="diagnosis",action=TeachingAction(type="ask",content="你准备如何判断游戏的跳跃功能已经完成？",knowledge_point_ids=["acceptance-criteria"],evidence_refs=["plan-001"]),next_recommendation="wait_for_student")
save("teach_request",tr)
save("teach_response",tres)

er = EvaluateRequest(request_id="req-003",context=ctx,decision=dres,turn_id=tres.turn_id,assessment_id="assess-001",assessment_mode="formative",rubric=rub,student_response=StudentMessage(message_id="msg-019",content="要测试按空格能否跳起来，但不知道怎样判断完成"),assessment_task_id="problem-001",assessment_reference="边界情形和验收办法应明确输入与预期行为")
eresp = EvaluationResult(request_id="req-003",evaluation_id="eval-002",decision_id=dres.decision_id,turn_id=tres.turn_id,assessment_id=er.assessment_id,assessment_mode="formative",rubric_id=rub.id,rubric_version=rub.version,criteria=[
    ScoredCriterion(criterion_id="identify-boundary",score=1,evidence_refs=["msg-019"],reason="提出了普通输入，但未明确边界"),
    ScoredCriterion(criterion_id="define-acceptance",score=0,evidence_refs=["msg-019"],reason="未给出验收标准")
],reason="需要补充边界和可检查的预期结果",knowledge_gaps=["acceptance-criteria"],confidence="medium",proposed_mastery_level="needs_support",next_recommendation="continue_teaching",suggested_pass=None)
save("evaluate_request",er)
save("evaluate_response",eresp)

# 多轮追踪案例：第一轮动作已经执行，学生回答及形成性评价被结构化保存。
# 下一轮由可信后端允许策略切换，教学智能模块可选第二条授权策略。
followup_turn = RecordedTeachingTurn(
    turn_id=tres.turn_id, decision_id=dres.decision_id, turn_index=0,
    phase=tres.phase, strategy_id=tres.strategy_id, strategy_version=tres.strategy_version,
    action=tres.action, student_reply=er.student_response, evaluation_ids=[eresp.evaluation_id],
)
feedback = RecordedEvaluation(
    evaluation_id=eresp.evaluation_id,decision_id=dres.decision_id,
    turn_id=tres.turn_id,assessment_mode=eresp.assessment_mode,
    rubric_id=eresp.rubric_id,rubric_version=eresp.rubric_version,
    criteria=[CriterionFeedback(criterion_id=c.criterion_id,score=c.score,
             max_score=next(r.max_score for r in rub.criteria if r.id == c.criterion_id))
             for c in eresp.criteria],
    proposed_mastery_level=eresp.proposed_mastery_level,
    knowledge_gaps=eresp.knowledge_gaps,confidence=eresp.confidence,
    next_recommendation=eresp.next_recommendation,reason=eresp.reason,
)
followup_request = TeachRequest(
    request_id="req-002-followup",context=ctx,decision=dres,
    phase="knowledge_teaching",turn_index=1,
    strategy_candidates=[strategy,second_strategy],
    active_strategy=StrategyRef(id=strategy.id,version=strategy.version),
    allow_strategy_switch=True,
    teaching_history=TeachingHistory(recent_turns=[followup_turn],recent_evaluations=[feedback]),
    knowledge_packages=tr.knowledge_packages,
    last_student_message=er.student_response,
    latest_evaluation_id=eresp.evaluation_id,
)
followup_response = TeachingTurn(
    request_id="req-002-followup",turn_id="turn-002",
    decision_id=dres.decision_id,
    strategy_id=second_strategy.id,strategy_version=second_strategy.version,
    strategy_selection_mode="switched",
    strategy_selection_reason="学生经引导仍缺少可验证标准，切换为对比例子讲授",
    phase="knowledge_teaching",
    action=TeachingAction(type="example",content="对比‘跳跃正常’和‘按空格且角色落地时垂直速度应改变’两种验收描述。",
                          knowledge_point_ids=["acceptance-criteria"],evidence_refs=["plan-001"]),
    next_recommendation="continue_teaching",
)
save("teach_request_followup",followup_request)
save("teach_response_followup",followup_response)

outcome = TeachingOutcome(record_id="outcome-001",session_id="sess-001",capability_id="requirements",applied_policy_id=strategy.id,applied_policy_version=1,baseline_level="needs_support",final_level="guided",hint_count=2,transfer_passed=False,evidence_refs=["eval-002"])
evreq = EvolveRequest(request_id="req-004",current_policy=strategy,history=[outcome],frozen_catalog_version="1",evaluation_rubric_ids=["requirements"])
new_strategy = TeachingStrategy(id="guided-discovery",version=2,capability_ids=["requirements"],learner_condition="需要帮助理解验收条件",steps=[StrategyStep(action_type="example",instruction="先对比有/无验收条件的需求"),StrategyStep(action_type="ask",instruction="请学生自行补充测试方式"),StrategyStep(action_type="explain",instruction="仍不理解时讲授验收条件原理")],stop_conditions=["学生能独立提出验证方式", "独立迁移考核完成"])
evres = EvolutionProposal(request_id="req-004",proposal_id="proposal-001",target_type="teaching_strategy",current_policy_id=strategy.id,from_version=1,candidate_policy=new_strategy,hypothesis="现有提问过于抽象，先比较例子可能降低理解门槛",supporting_record_ids=["outcome-001"],expected_outcome="提升后续相似任务的独立验收条件设计能力",failure_criteria=["迁移表现未改善","提示次数显著增加"],experiment_design=ExperimentDesign(comparison="paired_tasks",primary_metric="transfer_score",secondary_metrics=["hint_count"],guardrails=["固定评价 Rubric","控制新旧任务难度相近"]))
save("evolve_request",evreq)
save("evolve_response",evres)
exr = ExperimentResult(proposal_id="proposal-001",status="pending",current_policy_id=strategy.id,from_version=1,candidate_version=2,observations=[],decision_reason="候选版本尚未进行独立试教，不能宣布优于 V1")
save("experiment_result",exr)
print("Wrote fixtures")
