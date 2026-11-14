"""由 contracts.py 自动导出可供 JS/TS 服务使用的 JSON Schema。"""
from pathlib import Path
import json
from contracts import EXPORT_MODELS

ROOT = Path(__file__).resolve().parent
out = ROOT / "schemas"
out.mkdir(exist_ok=True)
for name, model in EXPORT_MODELS.items():
    schema = model.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://control.example.invalid/contracts/v0.2.1/{name}.schema.json"
    (out / f"{name}.schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Exported {len(EXPORT_MODELS)} schemas to {out}")
