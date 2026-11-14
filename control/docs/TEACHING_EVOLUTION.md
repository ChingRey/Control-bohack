# Teaching Agent 经验进化初版

本次新增真实模型适配的教学经验闭环，与旧 `teaching/evolve` Mock端口分开。代码在 `agents/teaching_evolution.py`，无新增第三方依赖，不训练模型权重，不改Coding执行权限。当前是工程闭环，不是已证明有效的教学算法。

## 从页面使用

从当前 control 目录启动：`python -X utf8 backend.py --port 8782`（也可用默认8772，避免占用现有服务）。已有后台需重新启动才能加载新Python代码；进程内Key重启后须重新配置。此次开发未停止已有服务。

顶部“设置 → 教学工具与经验 → 教学反思与经验库 → 查看与管理”。右侧仅保留聊天记录和输入框。可查看六维分数、原话证据、反思、经验来源、支持/反对/不确定计数；可手动“分析新交互”、停用、重新试用、人工启用、恢复历史版本。

- 默认 adaptive：读取初始经验；每轮至多提供一个匹配的试用条目，不自动修改稳定父策略。
- observe：只注入已启用条目；新经验保存为候选，不自动试用。
- off：不注入经验，也不启动新反思。
- 自动反思默认开启：教师完成且至少两条新的学生消息后触发；材料整理与经验反思有各自运行锁，不互相阻塞，也不阻塞前台。
- 自动反思发生在后台，不阻止聊天保存。新增交互和代码变更不会让已读取快照作废；仅原话被修改或经验版本冲突时拒绝旧更新。后台只合并自己的建议和经验，不覆盖前台状态。
- 恢复经验版本保留所有原话、评分、使用记录和游标；关闭自动反思并切入observe，避免立即再次演化。恢复不撤回已给学生的讲解。

## 论文与官方仓库参考

查阅时间：2026-11-14。以下是机制适配，不是安装官方框架，也未声称复现论文效果；本项目实现为原创代码。

- ACE论文：https://arxiv.org/html/2510.04618v1
- ACE官方仓库：https://github.com/ace-agent/ace
- 仓库关键实现：https://github.com/ace-agent/ace/blob/main/ace/ace.py 、https://github.com/ace-agent/ace/blob/main/playbook_utils.py
- Reflexion论文：https://arxiv.org/abs/2303.11366
- Reflexion官方仓库：https://github.com/noahshinn/reflexion
- 反思读取与再次尝试实现：https://github.com/noahshinn/reflexion/blob/main/hotpotqa_runs/agents.py

借鉴：Reflexion的轨迹/反馈→自然语言反思→后续上下文；ACE的Generator/Reflector/Curator分工、带ID经验条目、helpful/harmful计数、增量操作与去重。

本地适配：Teaching是Generator；独立评价调用形成反馈；第二次模型调用完成Reflector及语义Curator建议；确定程序校验并执行增量。修订已有条目会创建带parent_id的候选分支，保留稳定父条目；无整本策略覆盖。

## 初始经验

`agents/teaching_assets/evolution/seeds-v1.json` 包含5条初始教法：具体例子先行、一次一个重点、补必要前置、回到当前作品、逐步减少提示。来源是既有教学课卡和应用初版设计，不是经学生实验验证的结论，verified始终为false。

经验字段包括ID、内容版本、适用条件when、动作action、验证目标verify、限制limits、检索tags、来源、原话、父条目、状态、三类反馈计数、修改历史。经验仅在当前项目共享给Teacher，不自动跨学生或跨项目，不送入Coding项目规则库。

检索为确定的词项匹配，参考近期学生话语和当前计划，匹配数量优先、有限反馈排序辅助，最多两条，其中最多一个trial。加载记录只说明提交过，不证明采用。提示词要求Teacher自行检查适用性，不机械执行。

## 评分：从实际交互取证

规则文件 `agents/teaching_assets/evolution/rubric-v1.json`。评价对象是一个有界、连续的新交互片段（两侧聊天），允许读取前4条作为上下文。本批最多约36000字符原话；长历史按有界批次推进；queued/needs_retry消息不提前进入分析，编号记录在deferred_ids，之后送达时补分析，不阻塞后面的已处理对话。

每维最多一个综合条目：0未达到、0.5部分达到、1达到，null缺证据。计算：`score = 100 * mean(非null条目)`。第一版每批每维只有一项，因此分数是0/50/100，不伪装成精确连续能力值；跨批次没有直接相加或宣称提升，不计算总分。

| 维度 | 0 | 0.5 | 1 | 主要证据 |
|---|---|---|---|---|
| 理解效果 | 明确核心错误 | 部分正确或仅自述懂了 | 有具体独立正确解释/预测 | 学生原话 |
| 难度适配 | 有明确过难/重复已会且未处理 | 部分适配 | 有基础和表现支持匹配 | 学生基础/反馈及教师接续 |
| 信息量与节奏 | 明确跳步/重复/过载且未处理 | 部分处理 | 有具体适配或处理证据 | 教学顺序与自然反馈 |
| 项目相关性 | 偏离当前任务/错误关联 | 仅通用说明 | 正确联系当前功能 | 计划和对话；无源码时不认证行号 |
| 独立应用 | 核心错误或完整答案后复述 | 提示后完成/独立部分正确 | 无关键答案帮助提出合理要求或验证 | 学生给Coding的要求、教学回答、检查描述 |
| 反馈调整 | 困惑后仍无效重复 | 针对调整后部分改善/仅自述懂 | 有具体相近任务改善证据 | 调整前后对话 |

没有观察机会、沉默、无按钮点击都不能给满分或0分。点击阶段验收、复制Teacher完整指令不是独立掌握。字数、停留时间、提问次数、代码测试通过不能直接当理解成绩。评分结果是模型观察，尚未人工样本校准。

每个非null观察必须提供本批原话连续引用和消息ID；学生效果维度必须包含学生引用。伪造/越界引用、重复维度、非允许分值拒绝整批；返回失败保留旧经验。每批保存量表快照/hash、对话hash、代码hash、计划阶段、加载记录，便于以后复核。

## 经验反馈与验证

只有同时提供某经验所提交的Teacher回复、之后的新学生原话，且经验内容版本匹配，才接受helpful/harmful/uncertain记录。评价器需判断是否真正执行；无法归因用uncertain或不反馈。系统可校验证据来源与顺序，不能确定语义判断必然正确。

helpful/harmful只是观察计数，不是因果效果；不自动把trial晋升为active或认证有效。trial累计至少两次负面、且负面不少于正面时停用，这是可解释的工程止损阈值，未经统计校准。反思最多两条操作；重复when+action不重复加入，最多40条，满时保留报告而不新增。

新增经验始终未验证；修订稳定条目生成独立候选；模型只能直接停用试用条目，不能自行退休初始/稳定策略。人工可启用或停用，但verified仍为false。

下一阶段应做：真实模型评分抽查、学生小样本使用、固定基线比较、全局策略发布门槛。本版没有保证整体单调改善，也没有离线模拟冒充真实学生验证。

## 接口与持久化

P=`/api/tasks/:id`。

- `POST P/teaching/experience-review`，正文 `{}`：202异步评价与反思。无模型、关闭状态、重复运行或无新交互明确拒绝。
- `POST P/teaching/experience-manage`：必须带 `expected_revision`。
  - `{action:"options", mode:"adaptive"|"observe"|"off", auto:true|false}`。
  - `{action:"status", entry_id, status:"active"|"trial"|"inactive"}`。
  - `{action:"restore", target_revision:历史经验版本}`。
- `GET P` 返回 `teaching_evolution` 和用于轮询的 `experience_run`。

保存在既有tasks SQLite JSON，独立于聊天摘要、已审核Coding规则和旧Mock evolve端口。每次变更保存条目快照，不删除评价审计。当前未实现数据库分页、跨进程并发和无限历史压缩，长项目仍有存储增长成本。

单批评价与反思各一个逻辑模型调用，底层失败可能重试；与正常Teacher回复分开。sample不假装完成真实反思；模型失败不切Mock。后台重启标失败，不自动重放付费请求。

## 验证

- `python -X utf8 -m unittest discover -s tests -p test_teaching_evolution.py`
- `node --check frontend/evolution.js`
- `python -X utf8 scripts/verify_teaching_evolution.py`

浏览器验收创建隔离临时库，使用确定的模拟模型响应；真实浏览器覆盖评价入口→引用证据→候选进入下一轮Teacher→停用→回退且保留评分。模拟模型/自动测试证明工程链路，不证明真实教学质量。输出：`data/verification/teaching-evolution-ui.json` 和PNG。

## 后台独立运行补充

材料整理与经验反思不属于task_busy，不锁聊天、代码操作或✓。每类每项目至多一批运行，完成后若有新输入再合并为下一批，不做无输入无限循环。材料整理只追加待审核proposals，不替换整个workflow；经验更新基于冻结原话、量表和经验版本，新增消息和代码版本变化不使旧批次失效，使用时仍检查适用条件。已确认规则、材料、经验版本变更的冲突保护保留。

## snapshot-v2运行与超时

`GET /api/health` 公开background_revision=snapshot-v2，可区分磁盘源码与已启动进程。新增 `POST /api/settings/timeouts`，四个整数teacher_request_seconds/teacher_total_seconds/background_request_seconds/background_total_seconds；默认60/120/60/180。请求5—300秒、总时限5—900秒，请求不得大于总时限；设置保存至data/workbench/model-timeouts.json（无密钥），下次任务生效。设置页“模型超时”可调整，Coding原900秒上限不变。

模型传输单次使用socket超时，整轮共用deadline和最多5次请求预算；后台评价和反思共用总预算，不各自重新计时。超时不自动无限重试；后台失败不覆盖前台状态。request_trace仅保存次数、阶段、结果、耗时及HTTP码，不保存请求头、Key或模型隐式推理。

后台任务使用preparing/evaluating/evaluation_ready/reflection_ready阶段。评价完成但反思失败时保留评价；失败分provider_timeout/provider_connection/provider_http/invalid_json/validation_failed/internal_error。不能因同时有新消息把超时改写成冲突。来源原话确实被修改、或经验内容版本冲突时，保留未合并的结果供回查，不覆盖新版。最近50次后台运行审计保存在background_run_history；正式reviews及原话另外保留。

queued/needs_retry消息在本批记为deferred，不将其用于评分；后续已送达交互继续处理。早先消息重试送达后，根据deferred_ids补分析一次，不重算其他已处理消息。UI展示本批新消息ID、待补分析编号、错误原因、请求耗时与已完成评价。

验收：220项回归（0失败，1项可选跳过）；隔离浏览器验证超时设置保存和经验闭环。真实工作台已通过health确认snapshot-v2；实际课程38条消息保留，反思输入包含消息32/34等最新反馈，19/20记为deferred。本轮未凭模拟测试宣称模型反思质量或教学提升已得到验证。
