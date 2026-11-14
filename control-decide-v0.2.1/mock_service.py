"""供基础流程组联调用的确定性 Mock。返回值完全不代表实际教学效果。"""
from contracts import (
    DecideRequest, TeachingDecision, TeachRequest, TeachingTurn, TeachingAction,
    EvaluateRequest, EvaluationResult, ScoredCriterion,
    EvolveRequest, EvolutionProposal, ExperimentDesign,
)


class MockTeachingService:
    async def decide(self, request: DecideRequest) -> TeachingDecision:
        ids = set(request.context.course.candidate_capability_ids)
        cap = next((c for c in request.catalog.capabilities if c.id in ids and all(
            p in request.context.course.completed_capability_ids for p in c.prerequisite_capability_ids
        )), None)
        evidence = request.context.evidence
        can_teach = cap is not None and bool(evidence)
        return TeachingDecision(
            request_id=request.request_id, decision_id=f"mock-decision-{request.request_id}",
            context_id=request.context.context_id, teach=can_teach,
            capability_id=cap.id if can_teach else None,
            knowledge_point_ids=[cap.knowledge_point_ids[0]] if can_teach else [],
            evidence_refs=[evidence[0].id] if can_teach else [],
            reason="MOCK：预设教学目标" if can_teach else "MOCK：当前无可用候选或项目证据，跳过教学",
            objective="MOCK：完成一个知识点练习" if can_teach else None,
            content_policy_id=request.content_policy.id,
            content_policy_version=request.content_policy.version,
        )

    async def teach(self, request: TeachRequest) -> TeachingTurn:
        if not request.decision.teach:
            raise ValueError("教学目标为空时不应该调用 teach")
        # Mock 仅用于检验显式策略分配与切换流程：绝非真实教学策略算法。
        candidates = request.strategy_candidates
        assigned = request.active_strategy
        if assigned is None:
            choice = candidates[0]
            mode, reason = "initial", "MOCK：首次分配候选列表中的第一条策略"
        else:
            choice = next(s for s in candidates if (s.id, s.version) == (assigned.id, assigned.version))
            mode, reason = "continued", "MOCK：默认保持已分配的策略版本"
            if request.allow_strategy_switch and len(candidates) > 1 and request.teaching_history.recent_evaluations:
                # 有授权且出现历史反馈时演示切换，服务端仍须校验决定。
                alternate = next((s for s in candidates if (s.id, s.version) != (assigned.id, assigned.version)), None)
                if alternate:
                    choice = alternate
                    mode, reason = "switched", "MOCK：根据允许切换标志与反馈存在性，演示策略切换"
        return TeachingTurn(
            request_id=request.request_id, turn_id=f"mock-turn-{request.request_id}",
            decision_id=request.decision.decision_id,
            strategy_id=choice.id, strategy_version=choice.version,
            strategy_selection_mode=mode, strategy_selection_reason=reason,
            phase=request.phase,
            action=TeachingAction(type="ask", content="【MOCK 教学问题】请描述你会如何验证本次功能。",
                                  knowledge_point_ids=[request.decision.knowledge_point_ids[0]]),
            next_recommendation="wait_for_student",
        )

    async def evaluate(self, request: EvaluateRequest) -> EvaluationResult:
        # 为方便验收解锁事件，独立考核 Mock 固定给满分；绝不可当作真实掌握依据！
        is_transfer = request.assessment_mode == "independent_transfer"
        return EvaluationResult(
            request_id=request.request_id,
            evaluation_id=f"mock-eval-{request.request_id}",
            decision_id=request.decision.decision_id,
            turn_id=request.turn_id,
            assessment_id=request.assessment_id,
            assessment_mode=request.assessment_mode,
            rubric_id=request.rubric.id, rubric_version=request.rubric.version,
            criteria=[ScoredCriterion(
                criterion_id=c.id, score=c.max_score if is_transfer else 0,
                evidence_refs=[request.student_response.message_id],
                reason="MOCK：固定评分，仅用于链路测试") for c in request.rubric.criteria],
            reason="MOCK：不代表真实学习结果",
            knowledge_gaps=[] if is_transfer else list(request.decision.knowledge_point_ids),
            confidence="low",
            proposed_mastery_level="transfer_verified" if is_transfer else "needs_support",
            next_recommendation="finish_lesson" if is_transfer else "continue_teaching",
            suggested_pass=True if is_transfer else None,
        )

    async def evolve(self, request: EvolveRequest) -> EvolutionProposal:
        new_policy = request.current_policy.model_copy(update={"version": request.current_policy.version + 1})
        return EvolutionProposal(
            request_id=request.request_id,
            proposal_id=f"mock-proposal-{request.request_id}",
            target_type=request.current_policy.type,
            current_policy_id=request.current_policy.id,
            from_version=request.current_policy.version,
            candidate_policy=new_policy,
            hypothesis="MOCK：演示产生候选版本，不代表真实优化",
            supporting_record_ids=[request.history[0].record_id],
            expected_outcome="MOCK：有待进行的迁移验证",
            failure_criteria=["未表现出改善"],
            experiment_design=ExperimentDesign(comparison="paired_tasks", primary_metric="transfer_score",
                                              guardrails=["使用固定 Rubric"]),
        )
