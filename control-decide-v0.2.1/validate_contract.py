"""校验请求/响应数据：Pydantic 结构 + 跨对象语义引用。

用法：python validate_contract.py decide_response fixtures/decide_response.json --request fixtures/decide_request.json
"""
import argparse
import json
from pathlib import Path
from pydantic import ValidationError
from contracts import (
    EXPORT_MODELS, DecideRequest, TeachingDecision, TeachRequest, TeachingTurn,
    EvaluateRequest, EvaluationResult, EvolveRequest, EvolutionProposal,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def semantic_validate(contract: str, obj, request=None) -> None:
    """跨文档/枚举关系由业务层校验，不能仅依赖 JSON Schema。"""
    if request is None:
        return
    if obj.request_id != request.request_id:
        raise ValueError("响应必须回显 request_id")

    if contract == "decide_response":
        require(isinstance(request, DecideRequest), "语义引用或上下文不匹配")
        require(isinstance(obj, TeachingDecision), "语义引用或上下文不匹配")
        require(obj.context_id == request.context.context_id, "context_id 必须对应当前上下文")
        require((obj.content_policy_id, obj.content_policy_version) == (request.content_policy.id, request.content_policy.version), "内容策略引用不匹配")
        if obj.teach:
            candidates = set(request.context.course.candidate_capability_ids)
            require(obj.capability_id in candidates, "能力必须属于候选集合")
            cap = next((c for c in request.catalog.capabilities if c.id == obj.capability_id), None)
            require(cap is not None, "能力 ID 必须在课程目录中")
            require(all(k in cap.knowledge_point_ids for k in obj.knowledge_point_ids), "知识点不属于目标能力")
            require(all(req in request.context.course.completed_capability_ids for req in cap.prerequisite_capability_ids), "先修能力未完成")
            require(set(obj.evidence_refs) <= {e.id for e in request.context.evidence}, "决策引用了不存在的证据")

    elif contract == "teach_response":
        require(isinstance(request, TeachRequest), "语义引用或上下文不匹配")
        require(isinstance(obj, TeachingTurn), "语义引用或上下文不匹配")
        require(request.decision.teach, "无教学目标时不能调用 teach")
        require(request.decision.context_id == request.context.context_id, "语义引用或上下文不匹配")
        require(obj.decision_id == request.decision.decision_id, "语义引用或上下文不匹配")
        candidates = {(x.id, x.version) for x in request.strategy_candidates}
        picked = (obj.strategy_id, obj.strategy_version)
        require(picked in candidates, "返回策略必须来自后端提供的授权候选集合")
        assigned = request.active_strategy
        if assigned is None:
            require(obj.strategy_selection_mode == "initial", "首轮策略选择必须标记 initial")
        elif picked == (assigned.id, assigned.version):
            require(obj.strategy_selection_mode == "continued", "沿用策略必须标记 continued")
        else:
            require(request.allow_strategy_switch, "未经后端授权，不允许切换策略")
            require(obj.strategy_selection_mode == "switched", "换策略必须标记 switched")
        require(obj.phase == request.phase, "教学动作所属阶段不匹配")
        require({p.knowledge_point_id for p in request.knowledge_packages} >= set(request.decision.knowledge_point_ids), "语义引用或上下文不匹配")
        require(set(obj.action.knowledge_point_ids) <= set(request.decision.knowledge_point_ids), "动作超出本次知识点")
        require(set(obj.action.evidence_refs) <= {e.id for e in request.context.evidence}, "动作引用了不存在的证据")

    elif contract == "evaluate_response":
        require(isinstance(request, EvaluateRequest), "语义引用或上下文不匹配")
        require(isinstance(obj, EvaluationResult), "语义引用或上下文不匹配")
        require(request.decision.teach, "语义引用或上下文不匹配")
        require(obj.decision_id == request.decision.decision_id, "语义引用或上下文不匹配")
        require((obj.turn_id, obj.assessment_id, obj.assessment_mode) == (request.turn_id, request.assessment_id, request.assessment_mode), "语义引用或上下文不匹配")
        require((obj.rubric_id, obj.rubric_version) == (request.rubric.id, request.rubric.version), "语义引用或上下文不匹配")
        require(request.rubric.capability_id == request.decision.capability_id, "语义引用或上下文不匹配")
        expected = {c.id: c.max_score for c in request.rubric.criteria}
        actual = [c.criterion_id for c in obj.criteria]
        require(len(actual) == len(expected) and set(actual) == set(expected), "必须按正式 Rubric 所有 criterion 完整打分")
        accepted_evidence = {e.id for e in request.context.evidence} | {request.student_response.message_id}
        for item in obj.criteria:
            require(item.score <= expected[item.criterion_id], f"评分 {item.criterion_id} 超出上限")
            require(set(item.evidence_refs) <= accepted_evidence, "评分引用了不存在的证据")
        if obj.assessment_mode == "formative":
            require(obj.proposed_mastery_level != "transfer_verified", "形成性评价不能直接认定迁移掌握")
            require(obj.suggested_pass is not True, "形成性评价不能建议通过独立考核")
        else:
            require(obj.suggested_pass is not None, "独立考核必须提交通过建议")
            total = sum(c.score for c in obj.criteria)
            if obj.suggested_pass:
                require(total >= request.rubric.pass_score, "建议通过但未达到 Rubric 及格线")
        require(set(obj.knowledge_gaps) <= set(request.decision.knowledge_point_ids), "知识缺口只能引用当前教学知识点")

    elif contract == "evolve_response":
        require(isinstance(request, EvolveRequest), "语义引用或上下文不匹配")
        require(isinstance(obj, EvolutionProposal), "语义引用或上下文不匹配")
        require(obj.current_policy_id == request.current_policy.id, "语义引用或上下文不匹配")
        require(obj.target_type == request.current_policy.type, "语义引用或上下文不匹配")
        require(obj.from_version == request.current_policy.version, "语义引用或上下文不匹配")
        require(set(obj.supporting_record_ids) <= {r.record_id for r in request.history}, "改进依据必须来自真实历史记录")


def validate(contract: str, data: dict, request_data: dict | None = None):
    model = EXPORT_MODELS[contract]
    instance = model.model_validate(data)
    if request_data is not None:
        require(contract.endswith("_response"), "语义引用或上下文不匹配")
        request_contract = contract.replace("_response", "_request")
        request_obj = EXPORT_MODELS[request_contract].model_validate(request_data)
        semantic_validate(contract, instance, request_obj)
    return instance


def main():
    p = argparse.ArgumentParser()
    p.add_argument("contract", choices=EXPORT_MODELS)
    p.add_argument("json_file", type=Path)
    p.add_argument("--request", type=Path, help="对响应进行跨文档语义检查时必须提供对应请求")
    args = p.parse_args()
    data = json.loads(args.json_file.read_text(encoding="utf-8"))
    req = json.loads(args.request.read_text(encoding="utf-8")) if args.request else None
    try:
        validate(args.contract, data, req)
    except (ValueError, ValidationError, AssertionError) as ex:
        raise SystemExit(f"INVALID {args.contract}: {ex}")
    print(f"VALID {args.contract}: {args.json_file.name}")


if __name__ == "__main__":
    main()
