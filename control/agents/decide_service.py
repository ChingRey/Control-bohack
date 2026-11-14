"""Real, rule-based decide() with an optional (bounded) semantic ranking hook.

Implements TeachingService.decide while preserving public contract V0.2.1.
No side effects: never alters learner state, unlocks skills, or resumes agents.

A semantic ranker is optional. Without one this is a functioning, testable
conservative rules baseline, NOT an LLM-enabled teaching engine.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Protocol

from .teaching_contract_v021.contracts import (
    DecideRequest, TeachingDecision, Mastery, Stage,
)
from .teaching_contract_v021.validate_contract import semantic_validate


# These are application heuristics, not research-derived measured weights.
MASTERY_PRIORITY = {
    Mastery.needs_support: 45,
    Mastery.guided: 36,
    Mastery.unassessed: 30,
}
VALID_ARTIFACT_KINDS = {
    Stage.planning: {"plan"},
    Stage.implementation: {"plan", "code_diff", "runtime"},
    Stage.debugging: {"code_diff", "runtime", "test"},
    Stage.verification: {"plan", "code_diff", "runtime", "test"},
}
# Soft preferences only. An untrustworthy evidence snippet must not create a gap.
KIND_PREFERENCE = {"plan": 5, "test": 5, "code_diff": 4, "runtime": 4}
SEMANTIC_OVERRIDE_BUDGET = 20  # relative points; never overrides hard constraints


@dataclass(frozen=True)
class Opportunity:
    selection_id: str
    capability_id: str
    knowledge_point_id: str
    evidence_id: str
    evidence_kind: str
    evidence_summary: str
    evidence_content: str
    capability_title: str
    knowledge_title: str
    student_level: str
    score: int


class SemanticRanker(Protocol):
    """Return a selection_id from opportunities; 'none' to abstain.

    Used ONLY after hard eligibility filtering. Model output is always checked.
    """
    async def select(self, request: DecideRequest, opportunities: list[Opportunity]) -> str | None: ...


class DecideService:
    def __init__(self, ranker: SemanticRanker | None = None):
        self.ranker = ranker

    async def decide(self, request: DecideRequest) -> TeachingDecision:
        self._check_inputs(request)
        opportunities = self.enumerate_opportunities(request)
        if not opportunities:
            return self._skip(request, self._skip_reason(request))

        opportunities.sort(key=lambda o: (-o.score, o.capability_id, o.knowledge_point_id, o.evidence_id))
        chosen = opportunities[0]
        if self.ranker is not None:
            try:
                proposed = self.ranker.select(request, opportunities)
                proposed = await proposed if inspect.isawaitable(proposed) else proposed
                if proposed == "none":
                    return self._skip(request, "语义复核未找到与当前项目证据充分相关的教学机会；不强制教学。")
                eligible = {o.selection_id: o for o in opportunities}
                if proposed in eligible and chosen.score - eligible[proposed].score <= SEMANTIC_OVERRIDE_BUDGET:
                    chosen = eligible[proposed]
            except Exception:
                # Model/network/malformed-response failure does not break the workflow.
                # Deployment should log this fallback without logging secrets/content.
                pass

        label = {
            Mastery.unassessed.value: "尚未评价",
            Mastery.needs_support.value: "需要支持",
            Mastery.guided.value: "在引导下掌握",
        }[chosen.student_level]
        result = TeachingDecision(
            request_id=request.request_id,
            decision_id=f"decide-{request.request_id}",
            context_id=request.context.context_id,
            teach=True,
            capability_id=chosen.capability_id,
            knowledge_point_ids=[chosen.knowledge_point_id],
            evidence_refs=[chosen.evidence_id],
            reason=(f"阶段={request.context.project.stage.value}；依据项目证据 {chosen.evidence_id} "
                    f"({chosen.evidence_kind})，学生对「{chosen.knowledge_title}」的状态为「{label}」。"
                    "以项目审查/验证作为教学切入点；不预设 Coding Agent 有错误。"),
            objective=(f"围绕项目证据 {chosen.evidence_id}，学生能够解释「{chosen.knowledge_title}」"
                       "并独立提出一项可验证的工程判断或检查方法。"),
            content_policy_id=request.content_policy.id,
            content_policy_version=request.content_policy.version,
        )
        semantic_validate("decide_response", result, request)
        return result

    @staticmethod
    def _check_inputs(request: DecideRequest) -> None:
        if request.catalog.version != request.context.course.catalog_version:
            raise ValueError("课程目录版本不匹配，拒绝基于混合版本作决策")
        points = {k.id: k for k in request.catalog.knowledge_points}
        if len(points) != len(request.catalog.knowledge_points):
            raise ValueError("课程目录中知识点 ID 重复")
        caps = {c.id: c for c in request.catalog.capabilities}
        if len(caps) != len(request.catalog.capabilities):
            raise ValueError("课程目录中能力 ID 重复")
        evid_ids = [e.id for e in request.context.evidence]
        if len(evid_ids) != len(set(evid_ids)):
            raise ValueError("上下文证据 ID 重复")
        for cap in request.catalog.capabilities:
            for kp_id in cap.knowledge_point_ids:
                if kp_id not in points or points[kp_id].capability_id != cap.id:
                    raise ValueError(f"能力 {cap.id} 引用了非法知识点 {kp_id}")
        for point in request.catalog.knowledge_points:
            if any(prereq not in points for prereq in point.prerequisites):
                raise ValueError(f"知识点 {point.id} 包含未知先修知识点")

    @staticmethod
    def enumerate_opportunities(request: DecideRequest) -> list[Opportunity]:
        stage = request.context.project.stage
        candidates = set(request.context.course.candidate_capability_ids)
        completed = set(request.context.course.completed_capability_ids)
        targets = set(request.context.course.target_capability_ids)
        points = {p.id: p for p in request.catalog.knowledge_points}
        mastery = {s.knowledge_point_id: s.level for s in request.context.learner.knowledge_states}
        artifacts = {e.id: e for e in request.context.evidence
                     if e.source == "project" and e.kind in VALID_ARTIFACT_KINDS[stage]}
        # Only checkpoint-linked project evidence can anchor a decision. Historical
        # learner evaluations never substitute for real project artifacts.
        available = [artifacts[eid] for eid in request.context.project.evidence_refs if eid in artifacts]
        available = sorted({e.id: e for e in available}.values(), key=lambda e: e.id)
        results: list[Opportunity] = []
        for cap in sorted(request.catalog.capabilities, key=lambda cap: cap.id):
            if cap.id not in candidates or cap.id in completed:
                continue
            if not set(cap.prerequisite_capability_ids) <= completed:
                continue
            for point_id in cap.knowledge_point_ids:
                kp = points[point_id]
                if stage not in kp.project_stages:
                    continue
                level = mastery.get(point_id, Mastery.unassessed)
                if level not in MASTERY_PRIORITY:  # independent or transfer_verified
                    continue
                if any(mastery.get(pre) not in {Mastery.independent, Mastery.transfer_verified}
                       for pre in kp.prerequisites):
                    continue
                for e in available:
                    score = MASTERY_PRIORITY[level] + (8 if cap.id in targets else 0) + KIND_PREFERENCE[e.kind]
                    # Weak token overlap is a tie-breaker, not evidence of a defect.
                    corpus = e.summary + " " + (e.content or "")
                    if kp.title in corpus:
                        score += 5
                    results.append(Opportunity(
                        selection_id=f"{cap.id}|{point_id}|{e.id}",
                        capability_id=cap.id, knowledge_point_id=point_id, evidence_id=e.id,
                        evidence_kind=e.kind, evidence_summary=e.summary,
                        evidence_content=(e.content or "")[:2000],
                        capability_title=cap.title, knowledge_title=kp.title,
                        student_level=level.value, score=score,
                    ))
        return results

    @staticmethod
    def _skip_reason(request: DecideRequest) -> str:
        stage = request.context.project.stage
        sources = {e.id for e in request.context.evidence
                   if e.source == "project" and e.kind in VALID_ARTIFACT_KINDS[stage]}
        if not sources.intersection(request.context.project.evidence_refs):
            return "当前检查点缺少可核验、与阶段相关的项目证据；不根据学生评价记录推断项目缺陷。"
        if not request.context.course.candidate_capability_ids:
            return "当前课程候选能力为空，不强制创建教学目标。"
        return "当前没有同时满足课程候选、先修条件、阶段适用和学习缺口的教学机会。"

    @staticmethod
    def _skip(request: DecideRequest, reason: str) -> TeachingDecision:
        result = TeachingDecision(
            request_id=request.request_id, decision_id=f"decide-{request.request_id}",
            context_id=request.context.context_id, teach=False,
            capability_id=None, knowledge_point_ids=[], evidence_refs=[],
            reason=reason, objective=None,
            content_policy_id=request.content_policy.id,
            content_policy_version=request.content_policy.version,
        )
        semantic_validate("decide_response", result, request)
        return result
