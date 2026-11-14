"""Run from control with python scripts/smoke_decide.py."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.teaching_contract_v021.contracts import DecideRequest, EvaluateRequest, EvolveRequest, TeachRequest
from agents.teaching_contract_v021.validate_contract import semantic_validate
from agents.teaching_service import DecideTeachingService
from agents.teaching_v021 import fixture
from agents import teaching_library


PILOT_FIXTURE = ROOT / "tests" / "fixtures" / "decide_pilot_request.json"


async def main() -> None:
    service = DecideTeachingService()

    payload = fixture("decide_request")
    decide_request = DecideRequest.model_validate(payload)
    decision = await service.decide(decide_request)
    semantic_validate("decide_response", decision, decide_request)
    assert decision.schema_version == "0.2.1"
    assert decision.teach and decision.knowledge_point_ids == ["acceptance-criteria"]
    assert decision.evidence_refs == ["plan-001"]
    print("OK rule-based decide: acceptance-criteria / plan-001")

    payload["context"]["project"]["evidence_refs"] = []
    skip_request = DecideRequest.model_validate(payload)
    skip_decision = await service.decide(skip_request)
    semantic_validate("decide_response", skip_decision, skip_request)
    assert not skip_decision.teach and not skip_decision.evidence_refs
    print("OK rule-based decide: skip with no checkpoint evidence")

    teach_payload = fixture("teach_request")
    teach_payload["context"] = decide_request.context.model_dump(mode="json")
    teach_payload["decision"] = decision.model_dump(mode="json")
    teach_request = TeachRequest.model_validate(teach_payload)
    turn = await service.teach(teach_request)
    semantic_validate("teach_response", turn, teach_request)
    assert turn.action.type == "ask" and turn.action.evidence_refs == decision.evidence_refs
    assert decision.objective in turn.action.content
    print("OK rule-based decision -> teaching subplan")

    evaluate_payload = fixture("evaluate_request")
    evaluate_payload["context"] = teach_payload["context"]
    evaluate_payload["decision"] = teach_payload["decision"]
    evaluate_payload["turn_id"] = turn.turn_id
    evaluate_request = EvaluateRequest.model_validate(evaluate_payload)
    evaluation = await service.evaluate(evaluate_request)
    semantic_validate("evaluate_response", evaluation, evaluate_request)
    print("OK teaching subplan -> Mock evaluate")

    evolve_request = EvolveRequest.model_validate(fixture("evolve_request"))
    proposal = await service.evolve(evolve_request)
    semantic_validate("evolve_response", proposal, evolve_request)
    print("OK Mock evolve with fixture history")

    pilot_request = DecideRequest.model_validate_json(PILOT_FIXTURE.read_bytes())
    pilot_decision = await service.decide(pilot_request)
    semantic_validate("decide_response", pilot_decision, pilot_request)
    assert pilot_decision.knowledge_point_ids == ["L13"]
    # Use the existing L13 card and a verification strategy for this isolated trial.
    lesson = next(item for item in teaching_library.catalog()["lessons"] if item["id"] == "L13")
    pilot_teach = TeachRequest.model_validate({
        "request_id": "pilot-l13-teach",
        "context": pilot_request.context,
        "decision": pilot_decision,
        "phase": "knowledge_teaching",
        "turn_index": 0,
        "strategy_candidates": [{
            "id": "l13-pilot", "version": 1, "capability_ids": [pilot_decision.capability_id],
            "learner_condition": "需要帮助设计能判别问题的测试",
            "steps": [{"action_type": "explain", "instruction": lesson["main_question"]}],
            "stop_conditions": ["学生给出操作、预期和检查方式"],
        }],
        "knowledge_packages": [{
            "knowledge_point_id": "L13",
            "concepts": [lesson["evidence_to_seek"]],
            "misconceptions": [lesson["common_misconception"]],
            "source_refs": lesson["source_ids"],
        }],
    })
    pilot_turn = await service.teach(pilot_teach)
    semantic_validate("teach_response", pilot_turn, pilot_teach)
    assert pilot_turn.action.knowledge_point_ids == ["L13"]
    assert pilot_turn.action.evidence_refs == ["test-collision"]
    assert lesson["evidence_to_seek"] in pilot_turn.action.content
    print("OK pilot L13 decision -> L13 teaching with collision evidence")


if __name__ == "__main__":
    asyncio.run(main())
