"""Run with python smoke_test.py from the extracted bundle."""

import asyncio
import json
from pathlib import Path

from contracts import DecideRequest, EvaluateRequest, EvolveRequest, TeachRequest
from teaching_service import DecideTeachingService
from validate_contract import semantic_validate


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


async def main() -> None:
    service = DecideTeachingService()

    payload = load("decide_request")
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

    teach_payload = load("teach_request")
    teach_payload["context"] = decide_request.context.model_dump(mode="json")
    teach_payload["decision"] = decision.model_dump(mode="json")
    teach_request = TeachRequest.model_validate(teach_payload)
    turn = await service.teach(teach_request)
    semantic_validate("teach_response", turn, teach_request)
    print("OK rule-based decision -> Mock teach")

    evaluate_payload = load("evaluate_request")
    evaluate_payload["context"] = teach_payload["context"]
    evaluate_payload["decision"] = teach_payload["decision"]
    evaluate_payload["turn_id"] = turn.turn_id
    evaluate_request = EvaluateRequest.model_validate(evaluate_payload)
    evaluation = await service.evaluate(evaluate_request)
    semantic_validate("evaluate_response", evaluation, evaluate_request)
    print("OK Mock teach -> Mock evaluate")

    evolve_request = EvolveRequest.model_validate(load("evolve_request"))
    proposal = await service.evolve(evolve_request)
    semantic_validate("evolve_response", proposal, evolve_request)
    print("OK Mock evolve with fixture history")

    pilot_request = DecideRequest.model_validate(load("decide_pilot_request"))
    pilot_decision = await service.decide(pilot_request)
    semantic_validate("decide_response", pilot_decision, pilot_request)
    assert pilot_decision.knowledge_point_ids == ["L13"]
    print("OK pilot course catalog: L13")


if __name__ == "__main__":
    asyncio.run(main())
