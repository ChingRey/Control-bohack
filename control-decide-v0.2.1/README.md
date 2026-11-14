# Control · decide() 接入包

适用接口版本为 V0.2.1，Python 3.10+。规则版可直接执行，无需模型账号。

| 文件 | 用途 |
| --- | --- |
| `decide_service.py` | 异步选课实现 |
| `teaching_service.py` | 四接口联调服务，`decide()` 走规则，另外三个接口走 Mock |
| `semantic_ranker.py` | 可选语义复核，接收团队已有的异步模型调用函数 |
| `fixtures/decide_request.json` | 与 Mock 教学资料配套的验收条件示例 |
| `fixtures/decide_pilot_request.json` | 基于正式资料的 8 张课卡试验目录，示例选中 L13 |

## 已有 V0.2.1 适配层

将 `decide_service.py` 放在网站后端现有 `contracts.py` 和 `validate_contract.py` 所在的导入目录。按项目的包布局调整导入路径，调用时使用同一份 V0.2.1 类型定义。

只替换 `decide()` 时，现有处理函数可以调用以下代码。

```python
from contracts import DecideRequest
from decide_service import DecideService

decider = DecideService()

async def decide(incoming_json: dict) -> dict:
    request = DecideRequest.model_validate(incoming_json)
    decision = await decider.decide(request)
    return decision.model_dump(mode="json")
```

如果目前注入的是整个 `MockTeachingService`，也可以一并复制 `teaching_service.py`，把注入对象换成 `DecideTeachingService()`。`teach()`、`evaluate()` 和 `evolve()` 继续由 V0.2.1 Mock 提供。Mock 独立考核会返回固定满分，仅供联调，正式 Skill 解锁需读取真实考核结果。

## 请求和流程

- 将 Coding Agent 检查点的材料放入 `context.evidence`。项目证据的 `source` 填 `project`，并在 `context.project.evidence_refs` 中引用对应 ID。阶段和材料类型必须匹配。
- `context.course.catalog_version` 需与 `catalog.version` 一致。非 `unassessed` 的学生状态需引用评价证据。
- `teach=false` 时走网站已有的跳过教学分支。发起下一轮教学时沿用返回的 `decision_id`、`context_id` 和所选知识点 ID，按知识点 ID 查找 `knowledge_packages`，按 `capability_id` 提供策略候选。
- 包内 L13 示例用于验收选课。用试验课卡连到 `teach()` 时，需按所选课卡准备相同知识点 ID 的知识包和能力对应的策略。试验目录的阶段、先修和评分条件是临时映射。

## 本地验证

```bash
python -m pip install -r requirements.txt
python smoke_test.py
```

脚本检查选中验收条件、无项目证据时跳过、选中 L13，以及规则选课结果传入 Mock 教学与评价。它还用样例历史验证 Mock 迭代调用。网站上的真实检查点、暂停和恢复需在目标项目验证。

离线版按学生状态、阶段、先修和项目证据类型筛选与排序。`ContentPolicy` ID 和版本会随结果返回，规则版暂未执行其中的自然语言条款。证据相关性仍有已知限制，类型匹配的无关测试记录可能触发教学。语义复核代码随包提供，本次运行使用离线模式。
