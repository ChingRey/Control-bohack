# 当前接口与模块接入

本文只描述现有代码。统一前缀 `/api`，JSON 请求与响应，仅本机使用，无 `/v1` 前缀。

## 接口按实际流程排列

下表任务路径的前缀为 `/api/tasks/:id`。除特别说明外，成功返回任务快照；失败返回 `{ "error": "原因" }`。

| 顺序 | 方法与路径 | 输入 | 输出或行为 |
|---|---|---|---|
| 连接 | GET `/api/health` | 无 | coding_mode、teaching 的 mode/model、storage |
| 配置 | POST `/api/settings/teaching` | api_key、model（可省略） | configured、provider；不返回密钥 |
| 创建 | POST `/api/tasks` | `{}` | 新任务，无确认计划；`scenario: "teaching"` 则直接载入含遗漏的审查版本 |
| 恢复 | GET `/api/tasks/:id` | 无 | 当前快照；前端也用它轮询教师状态 |
| 草稿 | POST `…/plan` | message | 固定计划草稿，保存学生原话并启动教师审查，返回202 |
| 讨论 | POST `…/coding/messages` | message | 保存补充要求和固定回复；不会驱动真实编程 |
| 确认计划 | POST `…/plan/confirm` | confirmed: true、plan: 字符串数组 | 确认1–12个非空步骤；仅更新计划，不执行代码 |
| 执行一步 | POST `…/steps/run` | confirmed: true、expected_step: 整数、instruction | 写入示例代码、step加一、启动教师审查，返回202 |
| 阅读与保存 | POST `…/files` | path、content | 保存真实文件，记录before/after；清除本代码的候选掌握与迁移状态 |
| 教学对话 | POST `…/teaching/messages` | message | 先保存作答，后台处理，返回202 |
| 主动审查 | POST `…/teaching/review` | `{}` | 启动教师审查，返回202 |
| 掌握检查 | POST `…/evaluate` | `{}` | 启动教师评价，返回202；不会自动发XP |
| 技术选学 | POST `…/teaching/knowledge` | topic、choice: learn/later | learn启动教师讲解返回202；later仅记录偏好并返回200 |
| 新情境作答 | POST `…/teaching/transfer` | message | 必须已有pending_transfer；明确保存为迁移证据，返回202 |
| 当前代码检查 | POST `…/verify` | `{}` | 检查trim/条件判断与localStorage调用的源码标记，不执行行为测试 |
| 改进申请 | POST `…/upgrade-proposals` | confirmed: true | 检查候选掌握、迁移证据、教师建议、代码版本；追加pending_review申请 |
| 历史列表 | GET `/api/tasks` | 无 | id/title列表；当前页面不展示历史选择器 |

当前文件白名单：`app.js`、`index.html`、`style.css`。技术topic：`page-structure`、`events`、`input`、`storage`。前端配置入口接受的模型名以 backend.py 的白名单为准；可用性仍由用户账户及服务决定。

任务动作可附 `runtime_observations` 数组，元素含type（ready/error）、message、line。后端最多取最近20条，标记为浏览器上报，不当作已验证事实。

## 前端如何等教师回复

1. POST返回202和完整快照，学生消息已落库。
2. 查看 `teaching_run.status`：queued / running / completed / failed。
3. queued或running时轮询GET任务；detail/stage描述当前进展。
4. completed从messages展示教师回复；failed显示detail/error和重试入口。

当前同任务教学运行中，修改请求被拒绝；任务状态仍可读取。学生可见失败已由前端处理，不需要再向聊天插入一条伪教师回复。未实现取消接口。

## 快照中各模块要用什么

| 字段 | 用途 |
|---|---|
| id、title、mode、stage | 当前任务标识与示例开发状态 |
| plan_draft、plan、step | 未确认草稿、确认计划、下一次执行序号（从0开始） |
| messages | 两侧原始对话，channel= coding/teaching，role= user/assistant/system |
| files | 文件名 → 当前文本；由磁盘读取，前端编辑此内容 |
| changes | 文件、修改前后文本、确认指令 |
| checks | 源码标记检查结果，不是行为测试报告 |
| preview_url | 当前独立预览来源的实际地址 |
| teaching_provider | 教学模式与模型名；不要用任务mode猜教师是否真实调用 |
| teaching_run | 本轮后台任务编号、状态、进度、错误、耗时 |
| teaching.plan、teaching.course | 当前教学安排、整个项目的目标、接续摘要、检查点、选学偏好 |
| teaching.turns | 最近教学轮次，含加载Skill、工具记录、校验后的结构化结果 |
| teaching.assessment | insufficient / developing / candidate；candidate仍待复核 |
| teaching.pending_transfer、transfer_answer | 教师提出的迁移题及学生明确提交的作答 |
| teaching.upgrade_requests | 待复核能力改进申请；没有安装效果 |
| knowledge_topics | 页面技术选学主题 |

消息证据ID是messages数组下标。当前聊天不裁剪、不重排；扩展存储时必须保留证据ID映射。模型接续摘要不是事实证明。

## 给A/B/C/D的接入约定

**A接真实Coding**：现在入口为 `CODING.step(task, instruction)`，返回回复文本并追加changes、写项目文件；它同步执行且被当前请求持锁包住。接真实长任务时，应先与D增加独立coding_run后台状态，不能直接在这里挂几分钟请求。需求计划生成也要一起替换 backend.py 中固定PLAN草稿逻辑。

**B接能力改进**：读取upgrade_requests中的source_task、source_turn、suggestion、code_hash。当前只能形成待复核申请。确定启用/停用/版本/测试/撤回协议后再增加接口，不要把记录建议直接当安装成功。

**C接教学**：保持 `run(task, action, progress)` 的调用形状；返回字符串，在传入的工作副本中更新teaching。工具权限、输出结构和validate同步调整。progress只用于后台运行进度；不要在教师模块直接存整条任务。

**D接页面与整合**：维护上述快照和动作路径；给其他模块提供项目与文件写入入口。前端显示后端状态，不自行认定掌握或升级；升级、模型运行模式必须如实显示。

## 错误和预览边界

- 400：输入无效、确认缺失、步骤不一致、同任务忙等业务校验；当前没有细分409。
- 403：非本机Host或不允许的跨站写请求。
- 404：不存在的路由、任务或文件。
- 413：请求体超过200000字节。
- 422：文件或请求编码不受支持。
- 500：文件或SQLite读写失败。
- 模型失败一般保存在202任务的teaching_run中，不是把最初POST改成500。

网页预览使用 `preview_url`，优先主端口+1，冲突则自动选空闲端口；独立预览服务不提供API。前端iframe校验上报来源、窗口和任务ID。只支持静态网页，不支持任意Python/Node命令。


## 新增：记忆、画像与两条成长路线

| 方法与任务路径 | 输入 | 当前作用 |
|---|---|---|
| GET `…/learning` | 无 | memory范围与接续、learning画像、经验、候选Skill和申请 |
| GET `…/learning-record.md` | 无 | 由当前数据库记录生成Markdown，页面可下载 |
| POST `…/experiences/:card_id/confirm` | confirmed: true | 确认草稿或重新启用已停用经验 |
| POST `…/experiences/:card_id/disable` | confirmed: true | 停用已确认经验；下次不再提供给Coding |
| POST `…/experiences/:card_id/reject` | confirmed: true | 不保留候选经验，历史仍可追溯 |
| POST `…/skill-unlocks/:skill_id` | confirmed: true | 相关能力证据满足时追加待复核申请；不安装Skill |

快照增加teaching.memory、teaching.learning、learning_overview。profile含5项能力，level为unknown/needs_help/supported/independent/transfer_candidate；所有状态都是provisional_not_certified。不能把independent直接展示为“已认证掌握”。

当前候选Skill均validation_status=not_evaluated，can_install=false。学生证据可申请复核与Agent能力已验证分开。没有接受客户端直接设置verified或installed的接口。

教学结构化输出可增加learning_update，包含observations、experiences、prompt_review，详见教师提示词。引用必须来自本轮实际提供的学生原话并与原文一致；不合法时丢弃该学习更新，不丢弃正常教学回复。每个观察和经验记录source_turn、code_hash与证据编号。

Coding接口暂为step(task, instruction, learning_context=None)。后端从学生已确认经验中按标签选最多3条，传入{rules,skills,scope,note}。当前sample仅记录rule_versions，applied=false；A同学接真实Coding时应明确把资料加入实际请求，并记录使用结果，不能仅因为传参存在就宣布进化。

已有upgrade-proposals仍兼容，它是单轮旧建议出口，不等同于新Skill门槛。新开发应使用catalog与skill-unlocks，不把两者混为安装接口。


## OpenAI配置

POST /api/settings/teaching接收：provider（deepseek/openai，省略仍为deepseek）、api_key、model。OpenAI必须显式填写模型ID；DeepSeek省略model默认deepseek-flash。返回configured与不含密钥的provider元信息（mode、provider、model、protocol）。configured只表示保存完成，不证明账户权限和模型可用。

OpenAI映射到固定Responses端点，DeepSeek映射到固定Chat Completions端点；不接受任意base_url。切换时必须填写对应服务商的密钥，页面切换选项会清空密钥输入；不会回显任何已保存密钥。

## Coding → Teaching 检查点契约

当前采用同进程适配：后端协调器在 Coding 成功提交结果并暂停后，保存 `coding_checkpoints` 事件，再调用 `start_teaching(task, 'checkpoint')`。OpenCode 的阶段执行、显式计划生成以及固定示例的单步执行会产生事件；普通讨论、超时、失败和过期候选不会触发事件。不是网络 webhook，也不开放外部未经验证的检查点写入接口。

```json
{
  "schema_version": 1,
  "event_type": "coding.paused",
  "session_id": "任务UUID（当前原型一个任务对应一个开发会话）",
  "checkpoint_id": "Coding运行UUID，固定示例单独生成UUID",
  "stage": "本轮已确认阶段标题，计划生成时为planning",
  "stage_index": 0,
  "kind": "development",
  "task_description": "本次学生确认的执行指令",
  "user_requirement": "本会话首条Coding学生需求原文，当前补充要求见task_description及原始对话",
  "agent_output": "Coding计划或完成说明原文",
  "project_evidence": {
    "base_code_hash": "执行前源码哈希",
    "code_hash": "本轮提交源码哈希",
    "changes": [{"file":"src/app.js", "before_hash":"...", "after_hash":"...", "diff":"...", "diff_truncated":false}],
    "runtime_observations": [],
    "runtime_notice": "浏览器上报未独立验证，未绑定本轮代码版本",
    "test_records": [],
    "test_status": "not_run",
    "read_file_tool": "read_project_file"
  },
  "delivery": {"status":"queued", "teaching_run_id":"教师任务UUID"}
}
```

- 同一 `checkpoint_id` 只登记一次；事件保存于任务 JSON，GET 任务快照可查看，刷新后仍保留。`delivery` 记录 pending/queued/completed/failed；`teaching_run.checkpoint_id` 和教学轮次 `checkpoint_id` 关联本次事件。不会自动重放失败/重启中的任务；主动“审查代码”可重试最新检查点，不创建新事件。
- Teaching 通过 `checkpoint_event` 接收事件，结合课程接续与学生证据选择 `plan.goal/reason/next_step`。模型输入中的三项长文本各最多4000字符并标明截断；差异正文合计最多12000字符，最多展示40个变更，遗漏数量明确标注。原始聊天和完整修改前后代码仍在任务记录。
- 初始 `files` 是最多16000 JSON字符的完整代码行片段，优先本次变更文件；每文件最多120行。`project_files` 给出最多100个文件的路径、行数、哈希、总数及遗漏数量，不把整个仓库正文传入模型。
- 模型可用只读 `read_project_file(path, start_line=1, limit=120)` 读取本轮工作副本中的项目源码，支持子目录。返回真实行号、项目哈希、总行数及下一行；单次最多12000 JSON字符，整轮累计24000字符。仅允许已加载的当前项目文件，不能读取本机任意路径、执行命令或修改文件。读取过的完整行进入引用校验集合。
- 后续主动审查时按当前源码计算 `stale_for_code`。旧检查点、Coding文字说明和浏览器ready/error都不等于当前行为测试通过。当前执行器没有测试执行权限，因此 `test_records=[]`、`test_status=not_run`，不制造测试记录或掌握证据。
- Teaching 运行失败时保留检查点、学生原话及已完成的 Coding 状态和文件；后端仍按任务锁和源码/任务签名拒绝过期教学结果。不自动推进开发阶段、确认验收或加分。
## Teaching → Coding 操作接口

- 新任务支持 `checkpoint_delivery: "automatic" | "manual"`（默认automatic）；manual不会调用Teaching Agent，事件为 `delivery.status=available`。
- GET `/api/tasks/:id/checkpoints`、GET `/api/tasks/:id/checkpoints/:checkpoint_id` 获取事件及操作回执。
- GET `/api/tasks/:id/project-file?path=...&start_line=1&limit=80&checkpoint_id=...` 只读当前项目代码行，标注版本是否与事件匹配。
- POST `/api/tasks/:id/checkpoints/:checkpoint_id/revise`：`session_id,request_id,confirmed:true,expected_code_hash,instruction`；执行学生确认的当前阶段修改，成功后返回新检查点。
- POST `/api/tasks/:id/checkpoints/:checkpoint_id/resume`：同上，另需 `teaching_completed:true`；instruction可省略，可携带 `skill_unlocks:[{skill_id,assessment_id,unlocked:true}]`。同根检查点最终恢复只生效一次，并仅执行下一阶段后再暂停。
- 操作返回 `{operation,task}`，首次启动202；重复请求返回200和原回执，不重复执行。失败用相同内容与相同request_id加 `retry:true` 显式重试；版本/阶段冲突拒绝采用。错误沿用现有400等JSON格式。
- Skill通知仅为教学端报告；当前实际回执为未启用/未使用，不安装Skill、不加分。双方状态、完整请求示例和不接Teaching的HTTP验收见 [CHECKPOINT_HANDOFF](CHECKPOINT_HANDOFF.md)。
