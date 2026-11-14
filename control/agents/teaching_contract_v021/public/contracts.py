"""Control Teaching Engine 接口契约 V0.2.1。

单一真相源：使用 Pydantic v2 维护模型，导出 JSON Schema Draft 2020-12。
智能端只返回建议/评价；流程状态、学生掌握与版本发布由基础流程端执行。
"""
from __future__ import annotations
from enum import Enum
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.2.1"
Name = Annotated[str, Field(min_length=1, max_length=128)]
Note = Annotated[str, Field(min_length=1, max_length=4000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RequestBase(StrictModel):
    schema_version: Literal["0.2.1"] = SCHEMA_VERSION
    request_id: Name


class ResponseBase(StrictModel):
    schema_version: Literal["0.2.1"] = SCHEMA_VERSION
    request_id: Name  # 原样回显请求 ID，便于幂等与匹配


class Stage(str, Enum):
    planning = "planning"
    implementation = "implementation"
    debugging = "debugging"
    verification = "verification"


class Mastery(str, Enum):
    unassessed = "unassessed"
    needs_support = "needs_support"
    guided = "guided"
    independent = "independent"
    transfer_verified = "transfer_verified"


class Evidence(StrictModel):
    id: Name
    source: Literal["project", "learner", "assessment", "interaction"]
    kind: Literal["plan", "code_diff", "runtime", "test", "student_message", "evaluation", "other"]
    summary: Note
    content: str | None = None  # 小体量摘要/片段，不装整个代码仓库
    artifact_ref: Name | None = None  # 外部不可变快照/文件引用（需接入端保证可解析）


class ProjectSnapshot(StrictModel):
    stage: Stage
    task_id: Name
    goal: Note
    description: str | None = None
    evidence_refs: list[Name] = Field(default_factory=list)


class KnowledgeState(StrictModel):
    knowledge_point_id: Name
    level: Mastery
    evidence_refs: list[Name] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence_if_assessed(self):
        if self.level != Mastery.unassessed and not self.evidence_refs:
            raise ValueError("非 unassessed 状态必须附评价证据 ID")
        return self


class LearnerSnapshot(StrictModel):
    student_id: Name
    knowledge_states: list[KnowledgeState] = Field(default_factory=list)
    prior_help_count: int = Field(default=0, ge=0)


class CourseSnapshot(StrictModel):
    catalog_version: Name
    candidate_capability_ids: list[Name] = Field(min_length=0)
    target_capability_ids: list[Name] = Field(default_factory=list)
    completed_capability_ids: list[Name] = Field(default_factory=list)


class HistorySnapshot(StrictModel):
    recent_decision_ids: list[Name] = Field(default_factory=list)
    recent_evaluation_ids: list[Name] = Field(default_factory=list)


class TeachingContext(StrictModel):
    context_id: Name
    session_id: Name
    checkpoint_id: Name
    project: ProjectSnapshot
    learner: LearnerSnapshot
    course: CourseSnapshot
    history: HistorySnapshot = Field(default_factory=HistorySnapshot)
    evidence: list[Evidence] = Field(default_factory=list)


class Capability(StrictModel):
    id: Name
    title: Name
    behaviors: list[Note] = Field(min_length=1)
    prerequisite_capability_ids: list[Name] = Field(default_factory=list)
    knowledge_point_ids: list[Name] = Field(min_length=1)
    rubric_id: Name
    skill_id: Name | None = None


class KnowledgePoint(StrictModel):
    id: Name
    capability_id: Name
    title: Name
    prerequisites: list[Name] = Field(default_factory=list)
    project_stages: list[Stage] = Field(min_length=1)


class Criterion(StrictModel):
    id: Name
    description: Note
    max_score: float = Field(gt=0)


class Rubric(StrictModel):
    id: Name
    version: int = Field(ge=1)
    capability_id: Name
    criteria: list[Criterion] = Field(min_length=1)
    pass_score: float = Field(ge=0)

    @model_validator(mode="after")
    def check_pass_threshold(self):
        if self.pass_score > sum(x.max_score for x in self.criteria):
            raise ValueError("pass_score 不能超过评分满分")
        return self


class CourseCatalog(StrictModel):
    version: Name
    capabilities: list[Capability] = Field(min_length=1)
    knowledge_points: list[KnowledgePoint] = Field(min_length=1)
    rubrics: list[Rubric] = Field(min_length=1)


class KnowledgePackage(StrictModel):
    knowledge_point_id: Name
    concepts: list[Note] = Field(min_length=1)
    examples: list[Note] = Field(default_factory=list)
    misconceptions: list[Note] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class Rule(StrictModel):
    when: Note
    action: Note


class ContentPolicy(StrictModel):
    type: Literal["content_policy"] = "content_policy"
    id: Name
    version: int = Field(ge=1)
    rules: list[Rule] = Field(min_length=1)
    stop_conditions: list[Note] = Field(default_factory=list)


class StrategyStep(StrictModel):
    action_type: Literal["ask", "explain", "example", "practice", "hint", "feedback", "transfer"]
    instruction: Note
    trigger: str | None = None


class TeachingStrategy(StrictModel):
    type: Literal["teaching_strategy"] = "teaching_strategy"
    id: Name
    version: int = Field(ge=1)
    capability_ids: list[Name] = Field(min_length=1)
    learner_condition: Note
    steps: list[StrategyStep] = Field(min_length=1)
    stop_conditions: list[Note] = Field(min_length=1)


Policy = Annotated[Union[ContentPolicy, TeachingStrategy], Field(discriminator="type")]


class DecideRequest(RequestBase):
    context: TeachingContext
    catalog: CourseCatalog
    content_policy: ContentPolicy


class TeachingDecision(ResponseBase):
    decision_id: Name
    context_id: Name
    teach: bool
    capability_id: Name | None
    knowledge_point_ids: list[Name] = Field(default_factory=list)
    evidence_refs: list[Name] = Field(default_factory=list)
    reason: Note
    objective: str | None = None
    content_policy_id: Name
    content_policy_version: int = Field(ge=1)

    @model_validator(mode="after")
    def check_decision(self):
        if self.teach and (not self.capability_id or not self.knowledge_point_ids or not self.objective or not self.evidence_refs):
            raise ValueError("teach=true 时必须有能力、知识点、目标与证据")
        if not self.teach and (self.capability_id is not None or self.knowledge_point_ids or self.objective is not None):
            raise ValueError("teach=false 时不应返回目标能力/知识点/学习目标")
        return self


class TeachPhase(str, Enum):
    diagnosis = "diagnosis"
    knowledge_teaching = "knowledge_teaching"
    guided_practice = "guided_practice"
    transfer_assessment = "transfer_assessment"
    summary = "summary"


class StudentMessage(StrictModel):
    message_id: Name
    content: Note


class TeachingAction(StrictModel):
    type: Literal["ask", "explain", "example", "practice", "hint", "feedback", "transfer"]
    content: Note
    knowledge_point_ids: list[Name] = Field(min_length=1)
    evidence_refs: list[Name] = Field(default_factory=list)
    hint_level: int | None = Field(default=None, ge=1, le=4)

    @model_validator(mode="after")
    def check_hint(self):
        if self.type == "hint" and self.hint_level is None:
            raise ValueError("hint 动作必须有 hint_level")
        if self.type != "hint" and self.hint_level is not None:
            raise ValueError("只有 hint 动作可使用 hint_level")
        return self


class StrategyRef(StrictModel):
    """后端记录的当前有效策略分配；模型不得自行构造权限或发布版本。"""
    id: Name
    version: int = Field(ge=1)


class RecordedTeachingTurn(StrictModel):
    """已执行并由后端持久化的教学动作；不包含未来步骤。"""
    turn_id: Name
    decision_id: Name
    turn_index: int = Field(ge=0)
    phase: TeachPhase
    strategy_id: Name
    strategy_version: int = Field(ge=1)
    action: TeachingAction
    student_reply: StudentMessage | None = None
    evaluation_ids: list[Name] = Field(default_factory=list)


class CriterionFeedback(StrictModel):
    criterion_id: Name
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)

    @model_validator(mode="after")
    def check_score(self):
        if self.score > self.max_score:
            raise ValueError("历史评价得分不得超过评分上限")
        return self


class RecordedEvaluation(StrictModel):
    """历史形成性/迁移评价精简快照，保留教学自适应所需信息。"""
    evaluation_id: Name
    decision_id: Name
    turn_id: Name
    assessment_mode: Literal["formative", "independent_transfer"]
    rubric_id: Name
    rubric_version: int = Field(ge=1)
    criteria: list[CriterionFeedback] = Field(default_factory=list)
    proposed_mastery_level: Mastery
    knowledge_gaps: list[Name] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]
    next_recommendation: Literal["continue_teaching", "begin_transfer", "finish_lesson", "needs_review"]
    reason: Note


class TeachingHistory(StrictModel):
    """当前教学决策的最近已执行回合，输入快照由基础流程组提供。"""
    recent_turns: list[RecordedTeachingTurn] = Field(default_factory=list, max_length=20)
    recent_evaluations: list[RecordedEvaluation] = Field(default_factory=list, max_length=10)
    truncated: bool = False
    summary: str | None = None
    summary_evidence_refs: list[Name] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_history(self):
        turns = self.recent_turns
        if len({x.turn_id for x in turns}) != len(turns):
            raise ValueError("历史 turn_id 不得重复")
        if len({x.turn_index for x in turns}) != len(turns):
            raise ValueError("历史 turn_index 不得重复")
        if [x.turn_index for x in turns] != sorted(x.turn_index for x in turns):
            raise ValueError("历史教学回合必须按 turn_index 正序提供")
        if len({x.evaluation_id for x in self.recent_evaluations}) != len(self.recent_evaluations):
            raise ValueError("历史 evaluation_id 不得重复")
        if self.summary_evidence_refs and not self.summary:
            raise ValueError("历史摘要引用了证据时，必须提供摘要文本")
        return self


class TeachRequest(RequestBase):
    context: TeachingContext
    decision: TeachingDecision
    phase: TeachPhase
    turn_index: int = Field(ge=0)
    # 后端仅发送通过授权/发布检查、适用于当前能力的候选策略。
    # 初次调用由智能模块选择；之后默认沿用已分配策略。
    strategy_candidates: list[TeachingStrategy] = Field(min_length=1, max_length=12)
    active_strategy: StrategyRef | None = None
    allow_strategy_switch: bool = False  # 仅可信后端可以设置 true
    teaching_history: TeachingHistory = Field(default_factory=TeachingHistory)
    knowledge_packages: list[KnowledgePackage] = Field(min_length=1)
    last_student_message: StudentMessage | None = None
    latest_evaluation_id: Name | None = None

    @model_validator(mode="after")
    def check_teach_input(self):
        if not self.decision.teach:
            raise ValueError("teach=false 不可调用 teach()")
        if self.decision.context_id != self.context.context_id:
            raise ValueError("教学决策与上下文不匹配")
        if self.decision.capability_id not in self.context.course.candidate_capability_ids:
            raise ValueError("教学决策能力不是当前候选能力")
        keys = [(s.id, s.version) for s in self.strategy_candidates]
        if len(set(keys)) != len(keys):
            raise ValueError("策略候选 id/version 不得重复")
        if any(self.decision.capability_id not in s.capability_ids for s in self.strategy_candidates):
            raise ValueError("策略候选不适用于当前教学能力")
        if self.active_strategy and (self.active_strategy.id, self.active_strategy.version) not in keys:
            raise ValueError("已分配的策略必须存在于策略候选集")
        if self.allow_strategy_switch and self.active_strategy is None:
            raise ValueError("初次策略选择不需要 allow_strategy_switch")
        if {p.knowledge_point_id for p in self.knowledge_packages} < set(self.decision.knowledge_point_ids):
            raise ValueError("知识包未覆盖本次教学知识点")
        turns = self.teaching_history.recent_turns
        if turns and turns[-1].turn_index >= self.turn_index:
            raise ValueError("历史回合不得覆盖当前或未来回合")
        if any(t.decision_id != self.decision.decision_id for t in turns):
            raise ValueError("历史回合必须属于当前教学决策")
        if any(e.decision_id != self.decision.decision_id for e in self.teaching_history.recent_evaluations):
            raise ValueError("历史评价必须属于当前教学决策")
        ids = {t.turn_id for t in turns}
        if any(e.turn_id not in ids for e in self.teaching_history.recent_evaluations) and not self.teaching_history.truncated:
            raise ValueError("历史评价引用的教学回合必须存在；缺省回合须显式 truncated=true")
        valid_evaluations = {e.evaluation_id for e in self.teaching_history.recent_evaluations}
        if self.latest_evaluation_id and self.latest_evaluation_id not in valid_evaluations:
            raise ValueError("latest_evaluation_id 应能在最近评价详情中找到")
        if self.turn_index == 0 and (turns or self.active_strategy):
            raise ValueError("首轮教学不得提供历史回合或已分配策略")
        if self.turn_index > 0 and self.active_strategy is None:
            raise ValueError("后续教学必须提供后端持久化的 active_strategy")
        if self.turn_index > 0 and not turns and not self.teaching_history.truncated:
            raise ValueError("后续教学需要真实历史回合或显式截断说明")
        if turns and self.active_strategy and (
            turns[-1].strategy_id, turns[-1].strategy_version
        ) != (self.active_strategy.id, self.active_strategy.version):
            raise ValueError("active_strategy 必须与最近一次已执行教学回合一致")
        return self


class TeachingTurn(ResponseBase):
    turn_id: Name
    decision_id: Name
    strategy_id: Name
    strategy_version: int = Field(ge=1)
    strategy_selection_mode: Literal["initial", "continued", "switched"]
    strategy_selection_reason: Note
    phase: TeachPhase
    action: TeachingAction  # 单轮一个动作，真实执行由后端记录
    next_recommendation: Literal["wait_for_student", "continue_teaching", "request_evaluation", "begin_transfer", "finish_lesson"]


class ScoredCriterion(StrictModel):
    criterion_id: Name
    score: float = Field(ge=0)
    evidence_refs: list[Name] = Field(min_length=1)
    reason: Note


class EvaluateRequest(RequestBase):
    context: TeachingContext
    decision: TeachingDecision
    turn_id: Name
    assessment_id: Name
    assessment_mode: Literal["formative", "independent_transfer"]
    rubric: Rubric
    student_response: StudentMessage
    # 独立考核对应的题目/参考判据由课程侧持有，模型不得自行修改
    assessment_task_id: Name
    assessment_reference: Note


class EvaluationResult(ResponseBase):
    evaluation_id: Name
    decision_id: Name
    turn_id: Name
    assessment_id: Name
    assessment_mode: Literal["formative", "independent_transfer"]
    rubric_id: Name
    rubric_version: int = Field(ge=1)
    criteria: list[ScoredCriterion] = Field(min_length=1)
    reason: Note
    knowledge_gaps: list[Name] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]
    proposed_mastery_level: Mastery
    next_recommendation: Literal["continue_teaching", "begin_transfer", "finish_lesson", "needs_review"]
    suggested_pass: bool | None = None  # 不是最终解锁决定


class TeachingOutcome(StrictModel):
    record_id: Name
    session_id: Name
    capability_id: Name
    applied_policy_id: Name
    applied_policy_version: int = Field(ge=1)
    baseline_level: Mastery
    final_level: Mastery
    hint_count: int = Field(ge=0)
    transfer_passed: bool | None = None
    evidence_refs: list[Name] = Field(min_length=1)


class EvolveRequest(RequestBase):
    current_policy: Policy
    history: list[TeachingOutcome] = Field(min_length=1)
    frozen_catalog_version: Name
    evaluation_rubric_ids: list[Name] = Field(min_length=1)


class ExperimentDesign(StrictModel):
    comparison: Literal["A_B", "before_after", "paired_tasks"]
    primary_metric: Name
    secondary_metrics: list[Name] = Field(default_factory=list)
    guardrails: list[Note] = Field(min_length=1)


class EvolutionProposal(ResponseBase):
    proposal_id: Name
    status: Literal["candidate"] = "candidate"
    target_type: Literal["content_policy", "teaching_strategy"]
    current_policy_id: Name
    from_version: int = Field(ge=1)
    candidate_policy: Policy  # 候选完整定义，而不是只有 summary
    hypothesis: Note
    supporting_record_ids: list[Name] = Field(min_length=1)
    expected_outcome: Note
    failure_criteria: list[Note] = Field(min_length=1)
    experiment_design: ExperimentDesign

    @model_validator(mode="after")
    def check_candidate(self):
        p = self.candidate_policy
        if p.type != self.target_type or p.id != self.current_policy_id or p.version <= self.from_version:
            raise ValueError("候选策略需同 ID、同类型且版本递增")
        return self


class ExperimentObservation(StrictModel):
    session_id: Name
    policy_version: int = Field(ge=1)
    baseline_score: float | None = None
    transfer_score: float | None = None
    hint_count: int = Field(ge=0)
    incomplete: bool = False
    evaluation_refs: list[Name] = Field(default_factory=list)


class ExperimentResult(StrictModel):
    proposal_id: Name
    status: Literal["pending", "insufficient_evidence", "validated", "rejected"]
    current_policy_id: Name
    from_version: int = Field(ge=1)
    candidate_version: int = Field(ge=1)
    observations: list[ExperimentObservation] = Field(default_factory=list)
    decision_reason: Note


EXPORT_MODELS = {
    "course_catalog": CourseCatalog,
    "teaching_context": TeachingContext,
    "content_policy": ContentPolicy,
    "teaching_strategy": TeachingStrategy,
    "decide_request": DecideRequest,
    "decide_response": TeachingDecision,
    "teach_request": TeachRequest,
    "teach_response": TeachingTurn,
    "evaluate_request": EvaluateRequest,
    "evaluate_response": EvaluationResult,
    "evolve_request": EvolveRequest,
    "evolve_response": EvolutionProposal,
    "experiment_result": ExperimentResult,
}
