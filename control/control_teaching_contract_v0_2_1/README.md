# Control Teaching Engine｜四接口契约 V0.2.1

> **用途**：基础流程组直接使用本包的 Schema、Pydantic 模型、Mock 与测试，将独立的 TeachingService 边界接入现有网站。
>
> **状态**：本包完成了两项接口补充并通过本地测试；**未进行目标 Git 仓库写入、HTTP/浏览器、Windows 原生 asyncio、真实 Coding Agent 暂停恢复或真实模型教学效果的验证**。

## 1. 交付清单

- `contracts.py`：单一模型定义源（Pydantic v2），`SCHEMA_VERSION=0.2.1`。
- `schemas/`：13 份自动生成的 JSON Schema Draft 2020-12；新增的策略分配、历史回合与反馈类型嵌套在 `teach_request`/`teach_response` 中。
- `service_interface.py`：接口保持不变：`TeachingService.decide/teach/evaluate/evolve`，皆为 Python `async`。
- `mock_service.py`：确定性流程 Mock，支持首次策略选择、保持策略、获准后的策略切换；**不是教学算法**。
- `fixtures/`：原四接口样例及新增 `teach_request_followup.json` / `teach_response_followup.json`。
- `validate_contract.py`：Pydantic 结构检查 + 响应与请求之间的语义校验（特别是策略授权与匹配）。
- `tests/`：原测试及新增历史/策略切换的正反例测试。
- `MIGRATION_V0.2_TO_V0.2.1.md`：两项接口的迁移映射与版本规则。
- `基础流程组_接入与部署清单.md`：可直接交给 Agent 执行的集成与验收任务。
- `CHANGELOG.md`：版本差异。

## 2. 本版新增的两项协议

### A. `teach()` 策略选择与显式分配

V0.2.0 的 `TeachRequest.strategy` 是后端预先决定好的唯一策略，和我们要实现的“教学策略自适应选择”不符。

V0.2.1 的 `TeachRequest` 改为：

| 字段 | 说明 | 谁负责 |
|---|---|---|
| `strategy_candidates` | 已审核、适用当前能力的策略**完整版本列表**，至少 1 条、最多 12 条 | 基础流程组根据策略库存取及发布状态提供 |
| `active_strategy` | 当前教学会话已分配的 `{id,version}`；第一轮为 `null` | 基础流程组从**持久化记录**读取 |
| `allow_strategy_switch` | 是否允许本次在候选策略间切换；默认为 `false` | **可信基础流程后端**决定，不能由学生前端或模型决定 |
| `strategy_id` / `strategy_version` | 模型选择的本轮策略，必须在候选列表中 | 教学智能组 `teach()` 输出 |
| `strategy_selection_mode` | `initial` / `continued` / `switched` | 教学智能组 `teach()` 输出 |
| `strategy_selection_reason` | 选择或切换的简要依据，必填 | 教学智能组 `teach()` 输出 |

**调用规则**：

1. `turn_index=0`：`active_strategy=null`，`allow_strategy_switch=false`；教学智能从候选中选择策略，返回 `mode=initial`。
2. 后续回合：必须传入基础流程组保存的 `active_strategy`，模型默认保持原策略，返回 `mode=continued`。
3. 后端明确置 `allow_strategy_switch=true` 时，模型**可以选择**另一条授权候选策略，返回 `mode=switched` 及原因；可以不切换。
4. 后端须对返回结果执行 `semantic_validate("teach_response", response, request)`，确认切换被授权，然后原子化记录本轮动作及新策略分配。
5. 候选版本必须来自**批准发布的策略库**。Schema 无法证明是否已审核、发布或有权访问。

**特别注意**：策略切换不代表策略版本升级。`evolve()` 只产生候选新版本；新版本须先经过发布/审核机制，才可以进入 `strategy_candidates`。

### B. `teach()` 多轮历史与评价反馈

新增 `TeachRequest.teaching_history`，包含：

- `recent_turns`：最近最多 20 条**已经执行并持久化**的动作；每条包含 `turn_id`、`turn_index`、`phase`、策略 ID/版本、`action`、真实 `student_reply`、关联 `evaluation_ids`。
- `recent_evaluations`：最近最多 10 条评价摘要；保留 Rubric ID/版本、逐指标得分、知识缺口、建议掌握程度、反馈原因与下一步建议。
- `truncated`：如果早期回合被截断，需显式 `true`；**不得把丢失记录伪装成不存在**。
- `summary` / `summary_evidence_refs`：可选的可信历史摘要及来源；应由后端生成或审核，不能用它替代真实的当前回合证据。

保留 `last_student_message`（最新学生消息）和 `latest_evaluation_id`（须对应上述近期评价列表中的某条记录）。历史记录仅属于**当前 `decision_id` 的教学回合**；跨教学任务的记忆仍通过 `TeachingContext.history` 等原有机制引用。

`teach()` 每次依然只输出**一个当前教学动作**，基础流程组在动作真实执行后将其写入历史；不要把模型预想的未来动作写成执行过的动作。

## 3. 四接口一览

| 函数 | 主要输入 | 主要输出 |
|---|---|---|
| `decide()` | `TeachingContext`、正式课程目录、内容策略 | 是否教学、目标能力、知识点、证据和目标 |
| `teach()` | 同一上下文、教学决策、授权策略候选、已分配策略、近期历史、知识包、学生消息 | **本轮一个动作**、策略选择/切换说明、下一步建议 |
| `evaluate()` | 当前教学目标、Rubric、考核题与真实学生回答 | 各指标评分、证据、知识缺口、掌握状态建议 |
| `evolve()` | 真实教学历史、当前冻结策略、课程/评价标准版本 | 候选完整策略版本与验证计划 |

其他三个接口的**函数签名未变**，但四个请求和响应的 `schema_version` 均升级为 `0.2.1`。V0.2.0 请求不要冒充 V0.2.1 发送。

## 4. 运行及验证

Python 3.10+，在解压后的包根目录运行：

```bash
python -m pip install -r requirements.txt
python export_schemas.py
python create_fixtures.py
python demo_mock.py
python -m pytest -q
python validate_contract.py teach_response fixtures/teach_response_followup.json --request fixtures/teach_request_followup.json
```

通过测试的含义：本地结构、语义规则及 Mock 调用逻辑成立；并不证明已成功接入现有网站。

## 5. 集成边界与必须由网站处理的工作

1. **保留网站现有** `checkpoint/learning/memory` `schema_version=1` 内部协议；新建 V0.2.1 教学服务适配边界，不要替换旧协议版本。
2. 网站将真实 Coding Agent 检查点与不可变代码/测试记录映射为 `TeachingContext` 和 `evidence_refs`。不能仅凭 Schema 认定数据真实。
3. 每次执行教学动作后，后端记录真实 `RecordedTeachingTurn`；评价落库后，生成 `RecordedEvaluation` 快照；下一轮从实际记录填充 `teaching_history`。
4. 对策略候选版本、切换授权、恢复 Coding、独立考核与 Skill 解锁执行后端权限/状态检查。**Mock 考核满分只能用于隔离测试，不能触发正式 Skill 解锁**。
5. `request_id` 的持久化幂等、超时重试以及真实远程智能服务的重试去重需要分别实现；本包的 `request_id` 校验不提供分布式锁。
6. Python 可以直接运行服务协议；如使用 HTTP/JS，需由基础组建立路由、请求/响应转换及跨文档语义检查。JSON Schema **不能代替** `validate_contract.py` 的业务规则。
7. 课程能力/知识点、正式 Rubric、评分标准版本由课程维护方确认；`fixtures/` 全部是示例，不是正式课程资产。
8. 目标仓库写入、审批、部署、Windows asyncio 和真实浏览器回归测试均属于网站集成阶段。此交付包没有替另一组执行这些操作。

## 6. 建议的双方责任

- **基础流程组**：保留旧协议，新建适配器/HTTP 层，组装上下文及教学历史，提供已批准候选策略，保存策略分配与结果，执行权限、恢复/解锁和真实项目端到端测试。
- **教学智能组**：基于固定 V0.2.1 输入/输出实现真实四个函数，选择具体策略、生成有教育学依据的教学动作与反馈、提出可验证的候选进化策略。
- **课程内容组**：确认课程能力 ID、知识包、评分标准、版本与正式考核题。

本版为双方联调的**可执行契约候选版**，通过现有集成测试后再正式冻结；出现必要改动须双方审批并提升版本。
