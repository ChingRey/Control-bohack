# 当前本地工作台接口（2026-11-14）

统一前缀 `/api`。本机HTTP，JSON；任务路径 P=`/api/tasks/:id`。无另一个/v1前缀。现有桥接接口兼容保留，新调用优先检查点接口。教学/验证记录不自动认证掌握。

## 配置与项目

| 方法/路径 | 字段及结果 |
|---|---|
| GET /api/health | Coding安装/配置/权限/超时、Teaching模式与服务商；不含密钥 |
| POST /api/settings/coding | provider=bailian/siliconflow、api_key、model、region；仅进程配置 |
| POST /api/settings/teaching | provider=deepseek/openai、api_key、model；地址按服务商固定 |
| GET /api/tasks | 项目id/title列表 |
| POST /api/tasks | coding_mode=opencode创建真实项目；默认sample为固定教材；checkpoint_delivery=automatic/manual |
| GET P | 快照、真实文本文件、二进制元数据、run状态、材料、版本索引、预览及验证记录 |

## 两侧聊天与执行

| POST子路径 | 字段与行为 |
|---|---|
| chat/send | channel=coding/teaching、message、request_id。先保存再串行处理；忙时排队，重复相同ID/内容不重复发送；202返回快照 |
| chat/retry | request_id。只重试needs_retry消息，不新增原话；重启不自动执行队列 |
| coding/messages、teaching/messages | 旧直接入口保留；忙时可能拒绝。新前端用chat/send |
| coding/plan-decision | choice=approve/revise、request_id、expected_plan；结构化批准计划或继续讨论 |
| plan、coding/generate-plan、plan/confirm | 原计划入口兼容，plan/confirm需confirmed和plan数组 |
| steps/run、coding/revise | 原单步/修复，confirmed/expected_step/instruction；完成即暂停 |
| coding/prototype | expected_revision。以最近确认的需求生成最小原型，无需先建立完整计划 |
| files | path/content，保存现有文件，自动保留修改前版本 |
| teaching/review、evaluate | 现有教师审查入口；真实项目自然只读交流，旧sample课程单独保留 |

Coding使用项目文件工具自主创建/修改/重命名/删除任意类型文件，不设逐文件审批，执行900秒。项目外路径和符号链接仍拒绝。Teaching只提供两个只读工具，不写源码或直接调用Coding。文件提交核对运行号、上下文和文本/二进制版本；失败尝试恢复。

## 材料、功能与经验

| POST子路径 | 字段与行为 |
|---|---|
| workflow/material | kind=requirements/design/experiences/coverage/learner，content、expected_revision、confirmed；递增版本历史 |
| workflow/stage | stage=0..4、expected_revision；教学阶段与开发step独立 |
| workflow/options | mode=guided/free、auto_organize；自由模式不强制教学 |
| workflow/organize | 异步调用已配置提供商，引用原始消息产生待审核建议；无模型则明确失败，不切Mock |
| workflow/proposals/review | proposal_id、decision=accept/reject、expected_revision、可选编辑content、replaces_id；确认后更新材料/规则/概念记录 |
| workflow/rules/status | rule_id、status=active/inactive、expected_revision；保留规则旧版，有效最多15条 |
| workflow/feature | action=create/select/accept、expected_revision；create需title；select/accept需feature_id；accept需explanation及当前源码的验证记录 |

workflow包含材料历史、concepts、proposals、rules、features、当前功能和学习者关联。概念unknown/explained/practiced/independent_candidate均不认证掌握。规则的followed/missed/uncertain是模型观察建议。Coding只接共享材料、已审核规则和当前功能，不接教师私有记录。后台整理器独立于Teaching的只读源码工具。

## 版本、实际运行与验证

| POST子路径 | 字段与行为 |
|---|---|
| versions/save | label，保存文本/二进制联合快照 |
| versions/current | 返回hash |
| versions/restore | version_id、expected_hash；先保护当前代码，恢复文件，不恢复聊天/学习记录 |
| behavior/record | expected_hash、operation、expected、actual、result=passed/failed/inconclusive；明确为学生自报 |
| project/browser | expected_hash、cases数组（1..50且至少一个assert）；异步真实Edge/Chrome，外部网络阻断 |
| project/test | expected_hash、recipe=python-unittest/node-test；副本实际运行，不继承模型密钥，不自动安装依赖 |
| project/runtime/start | expected_hash、kind=python/node、entry项目文件；独立副本及PORT环境变量，返回进程状态/URL/日志 |
| project/runtime/stop | 停止本项目管理的服务进程 |

浏览器步骤action：fill/click/assert_text/assert_count/assert_exists/assert_absent/assert_value/reload/wait。除reload/wait外需CSS selector；fill/assert_value需value，assert_text需text，assert_count需count，wait需ms（最多3000）。结果只覆盖提供的用例。零测试不标通过。verification_run为running/completed/failed，执行证据分别保存browser_records/execution_records，包含联合hash和完成时是否仍匹配。snapshot.project_hash用于版本核对。

旧verify是绑定待办示例的源码标记检查，仍不是行为测试，通用项目应使用新验证入口。预览URL使用快照preview_url，不写死端口；独立来源iframe限制保持。

## 个人经验与交付

| 方法/路径 | 字段与行为 |
|---|---|
| GET /api/students | 本地学习者id/name/revision列表 |
| POST /api/students | name创建本机身份；不是账户认证 |
| POST P/student/attach | student_id、confirmed:true；明确载入该人的通用经验，已有身份不能静默切换 |
| POST P/student/promote | confirmed:true、rule_ids、include_profile可选；仅留存所选有效规则和可选教学观察 |
| POST P/delivery/prepare | expected_hash、student_statement={how_to_run,tested,limitations}；安全信号核对，保存最终版本与结项说明 |
| GET P/delivery.zip | 对当前源码重新扫描并生成ZIP；源码/静态启动脚本/运行README/HANDOFF/分类证据，不含.env或依赖缓存 |

仅本机学习者关联，不提供跨设备账户或公网鉴权。下载部署包不代表已发布到外部平台；公网发布需另定目标与账户权限。

## 检查点与兼容接口

GET P/checkpoints、GET P/checkpoints/:checkpoint_id：读取Coding暂停事件和回执；GET P/project-file?path=...&start_line=1&limit=80&checkpoint_id=...：只读带行号当前源码并标注版本匹配。

POST P/checkpoints/:checkpoint_id/revise 或resume：session_id/request_id/confirmed:true/expected_code_hash/instruction；resume另需teaching_completed:true，可携带skill_unlocks。根检查点最终恢复生效一次，重复请求返回原回执；失败以同ID和内容加retry:true。Skill通知不代表实际安装。详见[CHECKPOINT_HANDOFF](CHECKPOINT_HANDOFF.md)。

旧bridge/events、bridge/files、bridge/commands、bridge/retry、bridge/skills以及项目knowledge候选/审核/搜索继续兼容。旧teaching/sessions/open、finish、evolve是单独保留的团队接口，默认Mock产物不进入真实知识检索。当前工作流的真实材料整理走workflow/organize，审核规则由reviewed_project_rules进入Coding；不把旧Mock当作真实提炼。详见[TEACHING_BRIDGE](TEACHING_BRIDGE.md)、[POST_TEACHING_KNOWLEDGE](POST_TEACHING_KNOWLEDGE.md)。

## 持久化、失败和并发

SQLite tasks保留任务原话、材料历史、代码版本和证据；student_libraries单独保存明确留存的本机经验。没有删除学生data或重排原始消息。任务锁串行修改；queued/needs_retry消息不进入当前Coding上下文或使当前执行过期。失败队列显式重试，服务重启标记进行中run失败。后台只合并本轮字段，过期结果拒绝采用。

错误以JSON error返回，常用400输入/版本/忙状态，403非本机Host或跨站写入，404未知资源，413请求超过200000字节，422编码错误，500文件/数据库失败。异步模型/验证错误记录在run，不伪装完成。设置保存不等于模型可调用；真实质量需可用账户验收。
