"""运行：python demo_mock.py。仅验证四接口的异步契约与样例，非真实教学。"""
import asyncio
import json
from pathlib import Path
from contracts import DecideRequest, TeachRequest, EvaluateRequest, EvolveRequest
from mock_service import MockTeachingService
from validate_contract import semantic_validate

ROOT = Path(__file__).resolve().parent / "fixtures"
def load(name, model):
    return model.model_validate_json((ROOT / f"{name}.json").read_text(encoding="utf-8"))

async def main():
    service = MockTeachingService()
    tasks = [
        ("decide", DecideRequest), ("teach", TeachRequest),
        ("evaluate", EvaluateRequest), ("evolve", EvolveRequest),
    ]
    for name, cls in tasks:
        req = load(f"{name}_request", cls)
        res = await getattr(service, name)(req)
        semantic_validate(f"{name}_response", res, req)
        print(f"OK {name}(): {res.__class__.__name__} / request_id={res.request_id}")
    print("注意：Mock 评价结果不可当作真实学习评价或进化效果")

if __name__ == "__main__":
    asyncio.run(main())
