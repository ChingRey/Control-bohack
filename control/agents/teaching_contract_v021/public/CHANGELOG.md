# 接口版本记录

## V0.2.1 — 2026-11-14

### 新增：Teaching Agent 策略智能选择

- `TeachRequest.strategy` 替换为 `strategy_candidates`（后端提供已批准完整候选策略）。
- `TeachRequest.active_strategy` 记录当前已分配策略 ID/版本。
- `TeachRequest.allow_strategy_switch` 由可信后端决定是否允许本轮切换。
- `TeachingTurn.strategy_selection_mode` 与 `strategy_selection_reason` 显式说明初选、保持、切换。
- 语义校验拒绝未知候选策略、未授权切换、错误选择模式、重复候选策略或非法沿用策略。

### 新增：多轮教学历史与评价反馈

- `TeachRequest.teaching_history` 包含 `RecordedTeachingTurn`、`RecordedEvaluation`、截断说明及可选可信摘要。
- 保留策略版本、已执行动作、学生真实回复、评价来源及逐指标评分摘要。
- 限制最多 20 条近期回合和 10 条评价；增加重复/倒序/跨决策/未来回合/未知引用的输入检查。

### 不变

- 四个异步方法签名不变。
- `decide()`、`evaluate()`、`evolve()` 除统一版本号外业务字段不变。
- 课程目录、Rubric、策略候选发布权限仍由各自负责方维护；模型不得写数据库或决定正式 Skill 解锁。

### 明确限制

- 本包是接口实现与 Mock 测试，不是已部署的网站。
- V0.2.0 与 V0.2.1 **不直接兼容**；应显式升级请求/响应与网站适配层。
