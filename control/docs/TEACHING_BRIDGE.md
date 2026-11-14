# Teaching Engine 联调接口 v1

本文件描述新增的真实接口，优先于旧 API 文档中示例 Coding 的描述。
本阶段采用本机 HTTP + SQLite 持久化事件列表，由教学端轮询，不发送 webhook。
只监听 127.0.0.1；队友在自己的电脑启动同一份后端，用其教学服务调用。尚不支持直接跨电脑访问、浏览器跨域调用或生产认证。

## 已实现与缺口

- Coding 的真实执行完成后持久化检查点，暂停等待，不自动执行后续阶段。
- 事件包含 session_id、checkpoint_id、stage（从0开始）、task_description、user_requirement、agent_output、plan、project_evidence。
- project_evidence 包含本轮 before/after 变更、文件哈希、只读文件入口、已有运行上报与检查记录。未运行的测试不会自动生成；浏览器上报、静态检查不能当作行为测试通过。
- 教学端可回传学生确认的修改要求；修改完成产生新的 checkpoint_id，阶段不增加。因此一次教学可以多轮返工，每次引用最新事件。
- 恢复只接受当前检查点，阶段仅前进一次；重放同一 request_id 返回原回执，不重新执行。同一 request_id 更换内容报错，旧 checkpoint_id 使用新请求恢复也报错。
- Skill 提供 Teacher 授权、撤回、版本/哈希检查和执行记录接口。生产目录为空，不加载任何 Skill；请求返回 pending_catalog / applied:false，保留决定供后续接入。未来必须重新发起授权请求，不会因目录新增条目自动启用。
- 项目文件、代码差异、已有运行记录、预览由 Coding 后端提供；Teaching 不直接写文件。

## 最小调用

任务前缀 P=`http://127.0.0.1:8782/api/tasks/<session_id>`。

1. `GET P/bridge/events` → `{events:[...], coding_run:{...}}`。教学端按 checkpoint_id 去重，只处理 `status=waiting_teaching` 且 stage 与当前 task.step 相同的事件。
2. `GET P/bridge/files` → `{files:{"src/game.js":"..."}}`。目前一次读取当前项目文本文件，尚无按路径读取或分页。快照 `GET P` 还提供 plan、preview_url。文件是最新版本，须用事件中的哈希核对是否变化。
3. 需要修改时 `POST P/bridge/commands`：

```json
{"request_id":"student-edit-001","checkpoint_id":"事件里的ID","action":"modify","student_confirmed":true,"instruction":"学生确认的具体修改要求"}
```

4. 教学结束恢复下一阶段：

```json
{"request_id":"resume-001","checkpoint_id":"最新事件里的ID","action":"resume"}
```

执行异步返回202，回执 status=accepted 仅表示接收，不能当作完成。轮询 GET P 的 coding_run.status；只有 completed 后才领取新事件。最后阶段恢复后不启动新任务，返回200，阶段进度已完成。

5. Skill 通知：见下方协议，不影响暂停状态。

## 超时与恢复

- HTTP响应丢失：原样重发同一 request_id，不能生成新编号；运行中当前接口会返回错误，等本轮完成再重发。
- 执行失败：事件与原指令落库。`POST P/bridge/retry`，正文 `{"request_id":"原请求ID"}`，仅允许原请求关联的最近失败执行。它不会再次增加阶段。
- 读取事件超时：继续轮询，事件不会因读取而删除。
- 后端重启后 API Key 需要重新配置；旧 running 任务被启动恢复逻辑标为 failed。接收请求保存与启动线程之间仍有极短故障窗口，尚未提供事务型队列/跨进程 exactly-once 保证。
- 当前无自动推送重试、鉴权、取消任务、事件清理、全量日志分页。Skill 实装留待验证技能确定后开展。

## 不接 Teaching 模型的验收

在 control 目录：

```powershell
python -m unittest discover -s tests -p "test_bridge_api.py" -v
python -m unittest discover -s tests -p "test_teaching_bridge.py" -v
```

前者启动临时 HTTP 后端和模拟 Coding 传输，真实落文件并走完整 API：执行第一阶段→暂停→教学端读取事件与文件→发送恢复→执行第二阶段→重复恢复不重跑。不是实际 Teaching 模型验证。
后者检查恢复去重、多轮返工、学生确认、Skill 不虚报启用。真实 Coding 模型测试另行进行。


## Skill 预留协议（当前不添加任何 Skill）

Teaching 服务调用同一 `POST P/bridge/commands`：

```json
{"request_id":"unlock-001","checkpoint_id":"当前待教学检查点ID","action":"skill_unlock","skill_id":"verification","version":"1.0.0","teacher_decision_id":"assessment-001"}
```

- 当前目录为空：200返回 `status:pending_catalog, applied:false`，授权决定落库。不是加载成功。目录未来补齐后必须使用新的 request_id 再次发起决定。
- 后续目录由 Coding 小队在后端维护，只登记验证过的固定版本内容；客户端不得提交 content/path/url/prompt/skill_body。
- 未来目录匹配时：`status:authorized, applied:false`，绑定版本和内容SHA256；后续执行才解析并提交。哈希变化、未验证或版本缺失时拒绝加载。这里预留的是受控上下文加载适配口，原生 OpenCode skill 工具仍关闭。
- 撤回：同结构，action=`skill_revoke`，新 request_id，停止后续执行的绑定，不撤销已经生成的文件。
- 查询：`GET P/bridge/skills`，返回 catalog、bindings、decisions、runs。目录当前为空。
- runs 关联 run_id、阶段、outcome，以及每个 Skill 的版本、哈希、Teacher 决定ID、load_status、usage_status、effectiveness。
- `load_status:submitted` 仅代表携带内容的执行请求正常返回；失败则 unconfirmed。当前没有原生 Skill 调用事件证据，因此 usage_status 固定为 not_observed、effectiveness 固定为 not_evaluated；不能把提交、模型自述或代码变化当成实际使用证明。
- loaded_now=false 表示不保留常驻 Agent 会话，加载仅按执行轮次记录。
- 这些接口沿用本机联调边界。teacher_decision_id 是审计关联字段，不是身份认证；生产环境仍需服务鉴权。Teaching 模型本身不会自动调用接口，由教学端服务转发决定。
