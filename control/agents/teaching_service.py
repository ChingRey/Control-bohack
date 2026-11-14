"""V0.2.1 service for rule-based selection and planned teaching turns."""

from .teaching_contract_v021.contracts import (
    DecideRequest, EvaluateRequest, EvaluationResult, EvolveRequest,
    EvolutionProposal, TeachingDecision, TeachingTurn, TeachRequest,
)
from .decide_service import DecideService, SemanticRanker
from .teaching_contract_v021.mock_service import MockTeachingService
from .teaching_turn_adapter import make_teaching_turn


class DecideTeachingService:
    """Run the selection and teaching modules with the existing evaluation stubs."""

    def __init__(self, ranker: SemanticRanker | None = None) -> None:
        self._decider = DecideService(ranker=ranker)
        self.planner_state = {}
        self._mock_assessment = MockTeachingService()

    async def decide(self, request: DecideRequest) -> TeachingDecision:
        return await self._decider.decide(request)

    async def teach(self, request: TeachRequest) -> TeachingTurn:
        return make_teaching_turn(request, self.planner_state)

    async def evaluate(self, request: EvaluateRequest) -> EvaluationResult:
        return await self._mock_assessment.evaluate(request)

    async def evolve(self, request: EvolveRequest) -> EvolutionProposal:
        return await self._mock_assessment.evolve(request)
