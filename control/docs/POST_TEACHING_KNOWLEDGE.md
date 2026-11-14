# 教学结束整理与策略进化预留接口

当前范围：只实现流程、存储和适配接口，不实现新的教学策略，也不声称 Mock 学到了知识。

## 教学结束后写入经验

前缀 P=`/api/tasks/<项目session_id>`。

1. `POST P/teaching/sessions/open`，正文 `{"request_id":"lesson-open-1"}`。返回 teaching_session_id。一个项目同时最多一个 active 教学会话。第一轮包含已有两边对话，后续轮从新会话开启位置记录。
2. 正常调用已有 `POST P/teaching/messages` 多轮交流。不在每轮自动向 Coding 知识库写经验。
3. 教学端确认本轮教学结束后调用 `POST P/teaching/sessions/finish`：

```json
{"request_id":"lesson-finish-1","teaching_session_id":"步骤1返回的ID","confirmed":true}
```

输入由后端组织：本会话范围内全部 Coding/Teaching 原始对话（不按近期窗口裁剪）、当前计划、文本源码和代码版本。知识库整理与日常聊天上下文选取是不同入口。实际模型适配器未来须自行处理长文本分批，不应静默丢弃历史。

输出记录包括候选ID、来源消息ID、对话哈希、代码哈希、模式与状态。重复同一完成请求返回原结果，不重复入库；失败不结束会话，修正原因后可原请求重试。完成后不重新整理新加入的消息，应新建下一轮教学会话。

4. 当前 `agents/teaching_sessions.py` 的 DISTILLER 为 Mock。Mock 仅验证数据流，返回 mock_only 候选，不能审批成真实知识、不能被 Coding 搜索。空学生对话返回空候选。
5. 未来将 DISTILLER 替换为实现 `extract(packet)` 的后端适配器，返回 mode=model 和 items。每项包含 type、title、content、when、limits、evidence_ids、quotes。所有引用必须对应本轮原始对话；教师说明可以作为来源，不当成学生独立掌握的证据。
6. 真实适配器生成 pending_review 候选，经现有 `POST P/knowledge/<id>/review` 明确审核后，才被 Coding 的 project_knowledge 检索加载。适用场景和边界写进检索正文；不会安装 Skill、修改模型参数或由 Teacher 直接写源码。

查询：`GET P/teaching/sessions`。知识保存在原 tasks JSON 的 teaching.learning.knowledge_candidates，同时同步到 SQLite knowledge_items。当前检索仍按项目隔离，不支持自动把一个学生的经验注入另一个项目或学生。

## 策略进化仅留接口

`POST P/teaching/evolve`：

```json
{"request_id":"evolve-1","teaching_session_id":"可选教学会话ID","strategy_version":"v1"}
```

调用 `agents/evolution_port.py` 的 ADAPTER.evolve(packet)。输入包含当前项目与已保存的教学会话记录，返回 Mock 候选编号、父版本、strategy=null、applied=false。不生成实际策略，不改提示词，不切换或回退真实策略。后续团队替换 ADAPTER；发布和策略启用需要单独设计。

GET P/teaching/evolution 查询回执；request_id 重放幂等，同ID不同内容拒绝。

旧 `/upgrade-proposals` 返回410；旧升级申请生成分支与 upgrade-proposal 教学提示文件已移除。旧数据库记录保留，不删除学生历史。Coding Skill 路线不启用。

## 验证界限

124项自动测试通过：结束时覆盖两边对话、来源校验、重复请求不重复入库、Mock不得检索、真实提炼器测试替身可走审核和检索、进化回执不修改策略。未实现真实自动提炼模型或实际教法进化，未验证跨项目经验迁移。
