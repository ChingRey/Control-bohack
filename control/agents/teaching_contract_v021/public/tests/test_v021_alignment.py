"""V0.2.1 新增的两项约定：策略选择/切换，历史回合/评价反馈。"""
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import TeachRequest, TeachingTurn
from validate_contract import validate, semantic_validate
from mock_service import MockTeachingService

ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def raw(name):
    return json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))


def test_initial_assignment():
    req = TeachRequest.model_validate(raw("teach_request"))
    res = TeachingTurn.model_validate(raw("teach_response"))
    assert req.active_strategy is None
    assert len(req.strategy_candidates) == 2
    semantic_validate("teach_response", res, req)
    assert res.strategy_selection_mode == "initial"


def test_allowed_switch_with_real_history_shape():
    req = TeachRequest.model_validate(raw("teach_request_followup"))
    res = TeachingTurn.model_validate(raw("teach_response_followup"))
    assert req.teaching_history.recent_turns[0].student_reply is not None
    assert len(req.teaching_history.recent_evaluations[0].criteria) == 2
    semantic_validate("teach_response", res, req)
    assert res.strategy_selection_mode == "switched"


def test_unchanged_strategy_continues_without_authorization():
    req = raw("teach_request_followup")
    req["allow_strategy_switch"] = False
    res = raw("teach_response_followup")
    res.update(strategy_id="guided-discovery", strategy_version=1, strategy_selection_mode="continued")
    semantic_validate("teach_response", TeachingTurn.model_validate(res), TeachRequest.model_validate(req))


@pytest.mark.parametrize("change, expected", [
    ({"allow_strategy_switch": False}, "未经后端授权"),
    ({"strategy_candidates": [raw("teach_request_followup")["strategy_candidates"][0]]}, "候选集合"),
])
def test_reject_illegal_switch_request(change, expected):
    req = raw("teach_request_followup")
    req.update(copy.deepcopy(change))
    res = raw("teach_response_followup")
    with pytest.raises((ValueError, ValidationError), match=expected):
        validate("teach_response", res, req)


def test_wrong_mode_cannot_claim_switch():
    res = raw("teach_response_followup")
    res["strategy_selection_mode"] = "continued"
    with pytest.raises(ValueError, match="switched"):
        validate("teach_response", res, raw("teach_request_followup"))


def test_strategy_must_be_from_candidates():
    res = raw("teach_response")
    res["strategy_id"] = "invented-policy"
    with pytest.raises(ValueError, match="候选"):
        validate("teach_response", res, raw("teach_request"))


def test_duplicate_candidates_forbidden():
    req = raw("teach_request")
    req["strategy_candidates"].append(copy.deepcopy(req["strategy_candidates"][0]))
    with pytest.raises(ValidationError, match="不得重复"):
        TeachRequest.model_validate(req)


def test_missing_history_for_followup_forbidden():
    req = raw("teach_request_followup")
    req["teaching_history"] = {"recent_turns": [], "recent_evaluations": []}
    req["latest_evaluation_id"] = None
    with pytest.raises(ValidationError, match="历史回合"):
        TeachRequest.model_validate(req)


def test_missing_active_strategy_on_followup_forbidden():
    req = raw("teach_request_followup")
    req["active_strategy"] = None
    req["allow_strategy_switch"] = False
    with pytest.raises(ValidationError, match="必须提供"):
        TeachRequest.model_validate(req)


def test_future_history_turn_forbidden():
    req = raw("teach_request_followup")
    req["teaching_history"]["recent_turns"][0]["turn_index"] = req["turn_index"]
    with pytest.raises(ValidationError, match="未来回合"):
        TeachRequest.model_validate(req)


def test_foreign_history_evaluation_forbidden():
    req = raw("teach_request_followup")
    req["teaching_history"]["recent_evaluations"][0]["decision_id"] = "foreign-decision"
    with pytest.raises(ValidationError, match="当前教学决策"):
        TeachRequest.model_validate(req)


def test_latest_eval_id_must_resolve():
    req = raw("teach_request_followup")
    req["latest_evaluation_id"] = "unresolved"
    with pytest.raises(ValidationError, match="最近评价"):
        TeachRequest.model_validate(req)


def test_recent_history_order_and_unique():
    req = raw("teach_request_followup")
    dup = copy.deepcopy(req["teaching_history"]["recent_turns"][0])
    req["teaching_history"]["recent_turns"].append(dup)
    with pytest.raises(ValidationError, match="不得重复"):
        TeachRequest.model_validate(req)


def test_history_evaluation_criterion_bounds():
    req = raw("teach_request_followup")
    req["teaching_history"]["recent_evaluations"][0]["criteria"][0]["score"] = 100
    with pytest.raises(ValidationError, match="上限"):
        TeachRequest.model_validate(req)


def test_explicit_truncation_allows_missing_old_turn_details():
    req = raw("teach_request_followup")
    req["teaching_history"]["recent_turns"] = []
    req["teaching_history"]["truncated"] = True
    # 历史评价仍可以通过 ID 与不可变存储中更早的回合关联。
    parsed = TeachRequest.model_validate(req)
    assert parsed.teaching_history.truncated


@pytest.mark.asyncio
async def test_mock_initial_continue_switch():
    service = MockTeachingService()
    initial = TeachRequest.model_validate(raw("teach_request"))
    initial_result = await service.teach(initial)
    semantic_validate("teach_response", initial_result, initial)
    assert initial_result.strategy_selection_mode == "initial"

    next_req_data = raw("teach_request_followup")
    next_req_data["allow_strategy_switch"] = False
    next_req = TeachRequest.model_validate(next_req_data)
    continued = await service.teach(next_req)
    semantic_validate("teach_response", continued, next_req)
    assert continued.strategy_selection_mode == "continued"

    switch_req = TeachRequest.model_validate(raw("teach_request_followup"))
    switched = await service.teach(switch_req)
    semantic_validate("teach_response", switched, switch_req)
    assert switched.strategy_selection_mode == "switched"


def test_followup_fixtures_match_exported_json_schema():
    from jsonschema import Draft202012Validator
    root = ROOT.parent
    for contract, example in [
        ("teach_request", "teach_request_followup"),
        ("teach_response", "teach_response_followup"),
    ]:
        schema = json.loads((root / "schemas" / f"{contract}.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(raw(example))


def test_version_is_v021_across_four_requests():
    for name in ["decide", "teach", "evaluate", "evolve"]:
        assert raw(f"{name}_request")["schema_version"] == "0.2.1"
        assert raw(f"{name}_response")["schema_version"] == "0.2.1"


def test_version_rejection_of_old_payload():
    req = raw("teach_request")
    req["schema_version"] = "0.2.0"
    with pytest.raises(ValidationError):
        TeachRequest.model_validate(req)
