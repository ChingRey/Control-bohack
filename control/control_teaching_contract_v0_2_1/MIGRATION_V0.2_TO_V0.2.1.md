# V0.2.0 → V0.2.1 迁移指引

> 本次仅扩展 `teach()` 的两类信息。**属于显式版本升级，不保证旧请求可无修改地直接调用新模型。** 其它三个函数不更改业务字段，但请求/响应版本同步升级为 `0.2.1`。

## 1. 原 `TeachRequest` 对应关系

| V0.2.0 | V0.2.1 | 迁移方法 |
|---|---|---|
| `strategy: TeachingStrategy` | `strategy_candidates: list[TeachingStrategy]` | 至少放入原策略一条；最好提供多条已审核可用策略以支持动态选择 |
| （无） | `active_strategy` | `turn_index=0` 为 `null`；后续由后端读取最近已执行的策略 ID/版本 |
| （无） | `allow_strategy_switch` | 默认 `false`；仅可信后端判断可以切换时设为 `true` |
| （无） | `teaching_history` | 从已持久化的真实教学动作、学生消息和评价记录组装；不得生成伪历史 |
| `last_student_message` | 同名保留 | 传入最新真实学生消息；可与历史回合中的学生回复重合 |
| `latest_evaluation_id` | 同名保留 | 提供时必须能在 `teaching_history.recent_evaluations` 中找到详情 |

**第一轮可机械迁移**：把 `strategy` 转成单元素 `strategy_candidates`，把 `active_strategy` 设为 `null`，`allow_strategy_switch=false`，`teaching_history={}`。

**第二轮及以后不能机械迁移**：必须有已执行动作、学生回答、评价记录，以及基础组保存的 `active_strategy`。若确实只有部分历史，请设 `teaching_history.truncated=true` 并尽可能带上可核实的最新记录。

## 2. 原 `TeachingTurn` 对应关系

保留 `strategy_id`、`strategy_version`、`phase`、`action`、`next_recommendation`，新增两个必填字段：

- `strategy_selection_mode`：`initial`、`continued` 或 `switched`。
- `strategy_selection_reason`：简要说明当前策略选择依据/切换原因。

**不可只信任模型输出**，基础后端必须调用与请求绑定的语义校验，尤其校验是否授权切换、策略是否来自候选集合。

## 3. 两轮实际调用示例

- **首轮**：`fixtures/teach_request.json` → `fixtures/teach_response.json`；智能端在候选中首次选策略。
- **后续轮**：`fixtures/teach_request_followup.json` → `fixtures/teach_response_followup.json`；后端传入上一轮真实动作、学生回复和评价反馈，允许切换后选择新的授权策略。

## 4. 网站适配建议

原站 `schema_version=1` 是内部协议，不要改成 V0.2.1。新增一个独立边界，明确把网站 checkpoint/learning/memory 映射为新契约；保留原前端和状态机控制语义。

建议先升级 Mock 接口及 Schema，然后将真实后端持久化记录映射到 `TeachingHistory`，最后才接通真实模型服务。真实部署要按 `基础流程组_接入与部署清单.md` 验收。
