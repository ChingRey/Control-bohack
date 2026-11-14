"""Integration service exposing rule-based decide and Mock downstream methods."""

from .teaching_contract_v021.contracts import DecideRequest, TeachingDecision
from .decide_service import DecideService, SemanticRanker
from .teaching_contract_v021.mock_service import MockTeachingService


class DecideTeachingService(MockTeachingService):
    """Use during integration while downstream teaching methods are Mock."""

    def __init__(self, ranker: SemanticRanker | None = None) -> None:
        self._decider = DecideService(ranker=ranker)

    async def decide(self, request: DecideRequest) -> TeachingDecision:
        return await self._decider.decide(request)
