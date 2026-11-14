import json
from pathlib import Path
import sys
import pytest
from jsonschema import Draft202012Validator
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contracts import EXPORT_MODELS
from validate_contract import validate

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("contract", list(EXPORT_MODELS))
def test_valid_fixtures(contract):
    content = json.loads((ROOT / "fixtures" / f"{contract}.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas" / f"{contract}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(content)
    request = None
    if contract.endswith("_response"):
        request = json.loads((ROOT / "fixtures" / contract.replace("_response", "_request").__add__(".json")).read_text(encoding="utf-8"))
    validate(contract, content, request)


def load(name):
    return json.loads((ROOT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))

@pytest.mark.parametrize("name,modify", [
    ("decide_response", lambda d: d.update(capability_id="nonexistent")),
    ("decide_response", lambda d: d.update(evidence_refs=["invented-evidence"])),
    ("teach_response", lambda d: d.update(strategy_version=999)),
    ("evaluate_response", lambda d: d["criteria"][0].update(score=100)),
    ("evolve_response", lambda d: d.update(supporting_record_ids=["fake-record"])),
])
def test_semantic_rejection(name, modify):
    obj = load(name)
    modify(obj)
    with pytest.raises((ValueError, AssertionError)):
        validate(name, obj, load(name.replace("_response", "_request")))


def test_skip_teaching_does_not_have_target():
    d = load("decide_response")
    d.update(teach=False,capability_id=None,knowledge_point_ids=[],objective=None,evidence_refs=[],reason="没有合适证据")
    validate("decide_response", d, load("decide_request"))


def test_formative_not_transfer_mastery():
    d = load("evaluate_response")
    d["proposed_mastery_level"] = "transfer_verified"
    with pytest.raises(ValueError):
        validate("evaluate_response", d, load("evaluate_request"))


def test_mock_service_all_four_interfaces():
    import asyncio
    from mock_service import MockTeachingService
    from validate_contract import semantic_validate
    from contracts import DecideRequest, TeachRequest, EvaluateRequest, EvolveRequest

    async def check():
        service = MockTeachingService()
        for name, model in [("decide", DecideRequest), ("teach", TeachRequest), ("evaluate", EvaluateRequest), ("evolve", EvolveRequest)]:
            req = model.model_validate(load(f"{name}_request"))
            res = await getattr(service, name)(req)
            semantic_validate(f"{name}_response", res, req)
    asyncio.run(check())
