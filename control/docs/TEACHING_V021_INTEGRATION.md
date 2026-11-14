# V0.2.1 TeachingService 接入、验收与部署

## 范围与版本

独立边界为 `agents/teaching_v021.py`，四个异步端口仍是公共 TeachingService 的 decide/teach/evaluate/evolve。旧 checkpoint/learning/memory 的 schema_version=1 保留。公共包统一使用 `agents/teaching_contract_v021/public/`，外层 `__init__.py` 提供命名空间隔离。公共类型、校验器、Mock 和 Schema 由这份包提供。

显式配置 V0.2.1 的项目使用 `agents/teaching_service.py`。其中 `decide()` 使用 `agents/decide_service.py` 的离线规则，`teach()`、`evaluate()` 和 `evolve()` 使用公共 Mock。普通项目继续进入自然语言教学入口。

## 本地启动和身份权限

安装依赖：`python -m pip install -r agents/teaching_contract_v021/public/requirements.txt`。

普通站点仍可 `python -X utf8 backend.py --port 8772` 启动。联调入口需由本机操作者在启动时设置 CONTROL_V021_ACCESS_TOKEN；未配置时接口关闭授权入口，不能匿名调用。

推荐运行 `powershell -ExecutionPolicy Bypass -File scripts/start_teaching_v021.ps1`，在本机终端输入自己设置的至少16字符随机访问令牌。令牌不是模型API Key，仅进程保存，不写数据库或前端持久化。在教师面板打开“V0.2.1 接口联调”，输入同一令牌，连接当前项目会话。输入框随后清空，后续用HttpOnly、SameSite=Strict、8小时有效的项目范围会话Cookie。

服务只监听127.0.0.1，POST继续执行旧站Host/Origin校验。Bearer令牌代表本机操作者；项目会话代表该项目学生操作。allow-switch只接受操作者权限，学生不能提交策略候选、active_strategy、history或allow_strategy_switch。没有接入多用户SSO/远程角色管理，旧站接口也没有统一身份认证，不应当作可公网部署的系统。

## 实际HTTP路径

P=`/api/tasks/:id/teaching-v021`。所有写操作需稳定request_id，重复相同内容返回原收据，冲突拒绝。失败用相同内容及retry=true显式重试；后台保存请求再调用服务，重启将running标记failed，不自动续跑。

| 路径 | 输入 | 后台行为 |
|---|---|---|
| POST /api/teaching-v021/session | task_id；Bearer访问令牌 | 生成该项目范围Cookie，不将令牌入库 |
| GET P | 已授权 | 读取当前教学决策、执行记录、策略分配、请求和响应，以及冻结的上下文与证据来源 |
| POST P/configure | request_id | 配置包内演示课程/策略，明确标为仅Mock联调审批 |
| POST P/decide | request_id | 从已保存的 Coding 检查点、计划、学生消息和当前版本的验证记录生成冻结请求，再按阶段、先修、掌握状态和证据类型选课 |
| POST P/teach | request_id；phase可选 | 从已执行动作/真实回答/评价构造历史，从库读取候选/当前策略，通过语义校验才保存动作和分配 |
| POST P/respond | request_id、message | 保存学生原话，关联最近一个尚未回答的已执行教学动作 |
| POST P/evaluate | request_id、assessment_mode | 使用已保存学生回答、演示Rubric和任务说明调用evaluate，记录建议但不更新正式掌握 |
| POST P/evolve | request_id | 使用真实联调动作和评价记录构建outcome；保留Mock来源，只存候选完整策略及单独pending实验 |
| POST P/allow-switch | request_id、reason；仅Bearer操作者 | 授权下次回合在已登记候选间切换，一次性消费，保留原分配历史 |
| POST P/resume | request_id、confirmed=true、teaching_completed=true；instruction可选 | 跳过教学或已执行教学动作后，学生确认可恢复开发。重复和失败重试复用原操作 |

四端口的公共契约请求/响应位于后台requests内；HTTP外层收据携带mode、applied_mastery=false和空skill_unlocks，不能将外层当公共契约。真实请求响应样例见验收产物 http-examples.json。

## 数据映射与真实性

- session_id/task_id：真实任务UUID；checkpoint_id：Coding后台保存的真实检查点。
- context_id：每次decide生成新UUID，旧上下文不会就地修改。上下文冻结当前文本/二进制哈希，调用前后和失败重试核对。
- evidence_refs/artifact_ref：由后台生成证据ID，指向该context的sources不可变红acted来源快照；包含计划、检查点及代码差异、真实消息，以及当前版本匹配的人工/工具验证记录。保留验证来源，人工自报不当独立验收。不会读取整个仓库进模型。
- stage：原站5阶段映射到公共planning/implementation/verification枚举，仅是阶段提示，不表示验收通过。
- 非unassessed掌握：Mock不会生成正式掌握状态；演示评价/历史提议仅保留在独立边界，不能流入旧学习认证或Skill解锁。
- teaching_history：只映射当前decision下已持久化的动作、学生原话和评价详情，最多20动作/10评价，截断时明确truncated。旧站没有对应公共decision/rubric的历史不伪装成契约回合，原记录继续保留。
- active_strategy：来自数据库已执行分配；候选完整版本来自演示登记库。前端不控制切换授权。首轮initial、继续continued、授权变化switched均经公共语义校验。
- 策略演化与分配切换分开：候选不会自动进入授权策略库，不自动发布。实验单独保存pending，不声称效果验证。

## 接替服务

可信部署代码可调用 `install_service(factory, mode=..., approved_library=...)` 注入符合公共异步协议的服务。生产mode必须提供审核标记的正式课程、内容策略、教学策略和知识包，服务端检查类型和关联。正式服务使用独立项目。

## 验证命令与证据含义

- `python -B -m pytest -q agents/teaching_contract_v021/public/tests`：公共包41项数据/语义/Mock测试，不能当网站端到端。
- `$env:CONTROL_RUN_BROWSER_TESTS='1'; python -B -m unittest discover -s tests -p 'test_*.py' -v`：旧站和新增集成回归。
- `node --check frontend/app.js`、`node --check frontend/workflow.js`、`node --check frontend/teaching-v021.js`。
- `python -B -X utf8 scripts/verify_teaching_v021.py`：隔离数据库，目标Windows原生asyncio实际HTTP，真实OpenCode CLI通过本机合成服务写入两个JS文件，暂停→教学四接口→显式恢复→第二阶段写入，重复恢复不推进；真实浏览器打开界面、项目会话、提交学生回答、评价与续轮。首次开发计划为操作者测试夹具，不是模型自动规划。没有付费模型调用。

验收输出仅写data/verification/v021，不混入学生项目；有RESULTS.json、http-examples.json、v021-browser.png和回归日志。用户此前清空的历史不会恢复。

## 当前边界与尚存问题

1. 正式能力/知识点、课程版本负责人、Rubric及独立考核题尚未确认；包内示例不能替代。
2. 本轮只有Mock教学和本机合成Coding模型服务；没有证明真实模型质量或长期教学有效。
3. 同进程每任务锁串行更新，执行动作和分配随task一次SQLite保存；调用前另存请求。不提供多进程/远程分布式事务，远程服务仍必须以request_id去重；文件与数据库没有跨资源事务。
4. 同步HTTP在服务调用时持有该任务锁，当前Mock很快；正式服务预算最多120秒，会阻塞同项目后续修改。生产异步队列/多用户鉴权需另行设计。
5. 本轮记录“执行教学动作”指后台已保存并通过消息API提供展示，不证明学生已阅读；浏览器实际展示另有验收。
6. 上游不应自报审批标记；install_service是可信部署入口，不能暴露成学生/模型可写API。
7. 演化实验只登记 `pending`。
8. 离线规则按证据类型筛选，标题匹配提高排序分数。无关测试记录仍可能匹配碰撞边界课卡 L13。L13 试验目录需要配套知识包和策略才能用于网站教学，默认演示目录使用验收条件和边界情形两张课卡。

## 同期故障修正

- Coding精确识别 oldString=newString 的无变化编辑，不误报成权限拒绝；真实文件工具错误仍阻止采用，保留具体原因。
- 无计划直接文件操作不再访问不存在的阶段数组。
- 教师自然对话区分HTTP状态、超时和网络连接错误，页面直接显示实际原因；默认单次90秒，可用 CONTROL_TEACHING_REQUEST_TIMEOUT_SECONDS 在30–300秒间配置，整轮预算240秒，最多5次请求的限制保留。Coding默认900秒不变。
- 删除临时任务后后台收尾不再对不存在任务继续排队；不移除任务锁或过期结果保护。
