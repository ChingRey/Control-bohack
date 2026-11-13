# 当前接口与模块接入

本文只描述现有代码。统一前缀 `/api`，JSON 请求与响应，仅本机使用，无 `/v1` 前缀。

## 接口按实际流程排列

下表任务路径的前缀为 `/api/tasks/:id`。除特别说明外，成功返回任务快照；失败返回 `{ "error": "原因" }`。

| 顺序 | 方法与路径 | 输入 | 输出或行为 |
|---|---|---|---|
| 连接 | GET `/api/health` | 无 | coding_mode、teaching 的 mode/model、storage |
| 策略目录 | GET `/api/strategies` | 无 | 返回已登记的不可变策略版本、正文哈希和当前状态 |
| 配置 | POST `/api/settings/teaching` | api_key、model（可省略） | configured、provider；不返回密钥 |
| 创建 | POST `/api/tasks` | `{}` | 新任务，无确认计划；`scenario: "teaching"` 则创建独立输入审查教学任务并绑定 V1；页面“教学示例”按钮调用此场景 |
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
| task_definition_id、task_definition_version | 教学任务标识与版本；内置空白输入审查示例为 `todo-empty-input-validation` / `1` |
| teaching_session_id、strategy_version_id、teaching_strategy | 会话标识、绑定的策略版本 ID，以及该版本的只读定义；普通项目可为空 |
| teaching.upgrade_requests | 待复核能力改进申请；没有安装效果 |
| knowledge_topics | 页面技术选学主题 |

消息证据ID是messages数组下标。当前聊天不裁剪、不重排；扩展存储时必须保留证据ID映射。模型接续摘要不是事实证明。

## 第二版教学策略记录（当前实现）

- 内置教学示例绑定 `todo-input-v1`；普通新项目暂不绑定该任务专用策略。
- `strategy_versions` 保存策略定义、正文哈希和初始状态；发布后的正文按版本 ID 固定，调整策略要新增版本。
- `teaching_sessions` 保存任务定义 ID/版本、策略版本和会话时间；`teaching_events` 追加保存教师回合、教学频道学生原话和明确提交的迁移作答。
- `teaching_events` 使用确定性事件 ID 与 `INSERT OR IGNORE`，重复保存不会覆盖早先证据。事件携带会话和策略版本，供后续候选分析关联。
- 这一步只建立 V1 注册与证据留存；候选策略生成、审核状态流转、新任务对照试用、策略启用/回退和管理页面尚未实现。

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
