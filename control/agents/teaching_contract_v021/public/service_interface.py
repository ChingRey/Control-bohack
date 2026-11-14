"""教学智能服务的异步端口：基础流程组仅依赖该接口。"""
from typing import Protocol
from contracts import (
    DecideRequest, TeachingDecision,
    TeachRequest, TeachingTurn,
    EvaluateRequest, EvaluationResult,
    EvolveRequest, EvolutionProposal,
)


class TeachingService(Protocol):
    async def decide(self, request: DecideRequest) -> TeachingDecision: ...
    async def teach(self, request: TeachRequest) -> TeachingTurn: ...
    async def evaluate(self, request: EvaluateRequest) -> EvaluationResult: ...
    async def evolve(self, request: EvolveRequest) -> EvolutionProposal: ...
