"""Map V0.2.1 teaching turns onto the existing teaching subplan engine."""

import json
from hashlib import sha256

from . import teaching_methods
from .teaching_contract_v021.contracts import TeachingAction, TeachingTurn, TeachRequest


MASTERY_LEVELS = {
    "unassessed": "unknown",
    "needs_support": "needs_help",
    "guided": "supported",
    "independent": "independent",
    "transfer_verified": "transfer_candidate",
}


def _strategy_assignment(request):
    active = request.active_strategy
    if active is None:
        return request.strategy_candidates[0], "initial", "按已登记候选的顺序开始教学。"
    current = next(s for s in request.strategy_candidates if (s.id, s.version) == (active.id, active.version))
    if request.allow_strategy_switch and request.last_student_message:
        for candidate in request.strategy_candidates:
            if (candidate.id, candidate.version) != (active.id, active.version):
                return candidate, "switched", "收到学生回答后，按授权尝试另一项已登记策略。"
    return current, "continued", "沿用本教学目标已分配的策略。"


def _action_content(action, instruction, request):
    packages = {package.knowledge_point_id: package for package in request.knowledge_packages}
    selected = [packages[key] for key in request.decision.knowledge_point_ids]
    objective = request.decision.objective[:500]
    goal = f"学习目标：{objective}"
    concepts = "；".join(package.concepts[0][:500] for package in selected)[:1500]
    examples = "；".join(package.examples[0][:500] for package in selected if package.examples)[:1500]
    misconceptions = "；".join(
        package.misconceptions[0][:500] for package in selected if package.misconceptions
    )[:1500]
    task = (request.context.project.description or request.context.project.goal)[:400]
    reply = request.last_student_message
    response = f"你刚才的回答：「{reply.content[:200]}」。" if reply else ""
    if action == "explain":
        return f"{goal}\n{response}\n{concepts}\n{instruction}\n结合本轮任务「{task}」，你会怎样用这个原则检查结果？"
    if action == "example":
        material = f"课卡示例：{examples}" if examples else f"可以先用这条原则构造一个例子：{concepts}"
        return f"{goal}\n{instruction}\n{material}\n回到「{task}」，这里有哪些条件需要另外检查？"
    if action == "hint":
        return f"{goal}\n{instruction}\n{misconceptions or concepts}\n先在「{task}」中找一条可以观察的依据。"
    if action == "feedback":
        return f"{goal}\n{response}\n{instruction}\n请对照这个要点核查自己的理由：{concepts}"
    if action == "transfer":
        return f"{goal}\n{instruction}\n换一个与「{task}」不同的场景。描述你会检查什么，以及怎样的结果能支持你的判断。"
    if action == "practice":
        return f"{goal}\n{instruction}\n请在「{task}」中给出一项实际操作和预期结果，说明如何核对。"
    return f"{goal}\n{instruction}\n针对本轮任务「{task}」，你的判断是什么？哪条项目记录支持它？"


def _project_plan(request):
    for item in request.context.evidence:
        if (item.source != "project" or item.id not in request.context.project.evidence_refs
                or item.kind != "plan" or not item.content):
            continue
        try:
            record = json.loads(item.content)
        except ValueError:
            continue
        steps = record.get("plan") if isinstance(record, dict) else None
        if isinstance(steps, list) and all(isinstance(step, str) for step in steps):
            return steps
    return []


def make_teaching_turn(request: TeachRequest, planner_state: dict) -> TeachingTurn:
    strategy, selection, reason = _strategy_assignment(request)
    decision = request.decision.model_dump(mode="json")
    decision["goal_id"] = request.decision.capability_id
    decision["objective"] = request.decision.objective[:500]
    steps = [
        {"action": "ask_transfer" if step.action_type == "transfer" else step.action_type,
         "purpose": step.instruction[:500]}
        for step in strategy.steps
    ]
    strategy_input = {"id": strategy.id, "version": strategy.version, "content": {"steps": steps}}

    # Public teaching history remains bounded. Keep the current subplan in
    # backend state so retries and later turns retain the same step position.
    plans = planner_state.setdefault("assignments", {}).setdefault(request.decision.decision_id, {})
    learner = plans.setdefault(strategy.id, {}).setdefault(str(strategy.version), {})
    learner["learning"] = {"knowledge_state": {
        state.knowledge_point_id: {"level": MASTERY_LEVELS[state.level.value], "evidence_ids": state.evidence_refs}
        for state in request.context.learner.knowledge_states
    }}
    # Evaluation is still a test stub. Progress comes from delivered actions,
    # while the student's actual reply is available for the next action.
    history = request.teaching_history.recent_turns
    learner["hint_level"] = min(3, sum(turn.action.type == "hint" for turn in history))
    project = {
        "stage": request.context.project.stage.value,
        "coding_plan": _project_plan(request),
        "valid_evidence_refs": [item.id for item in request.context.evidence],
    }
    method = teaching_methods.teach(decision, learner, strategy_input, project)
    step = method["next_step"]
    action = "transfer" if step["action"] == "ask_transfer" else step["action"]
    turn_id = "teach-" + sha256(request.request_id.encode()).hexdigest()
    if action == "pause":
        if step["status"] not in {"awaiting_evaluation", "completed"}:
            raise ValueError(step["instruction"])
        action = "feedback"
        content = step["instruction"]
        recommendation = "finish_lesson" if step["status"] == "completed" else "request_evaluation"
    else:
        content = _action_content(action, step["instruction"], request)
        recommendation = "wait_for_student"

    turn = TeachingTurn(
        request_id=request.request_id,
        turn_id=turn_id,
        decision_id=request.decision.decision_id,
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        strategy_selection_mode=selection,
        strategy_selection_reason=reason,
        phase=request.phase,
        action=TeachingAction(
            type=action,
            content=content,
            knowledge_point_ids=request.decision.knowledge_point_ids,
            evidence_refs=request.decision.evidence_refs,
            hint_level=learner["hint_level"] + 1 if action == "hint" else None,
        ),
        next_recommendation=recommendation,
    )
    teaching_methods.store_subplan(learner, method)
    if step["step_id"] and step["action_source"] == "subplan":
        teaching_methods.record_step(learner, method, {
            "execution_id": turn_id,
            "subplan_id": method["subplan"]["id"],
            "subplan_version": method["subplan"]["version"],
            "step_id": step["step_id"],
            "action": step["subplan_action"],
            "success": True,
            "result_ref": turn_id,
        })
    return turn
