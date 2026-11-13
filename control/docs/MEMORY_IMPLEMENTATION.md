# 聊天记忆、能力画像与两条成长路线：实现及验证

更新：2026-11-13。

## 1. 这次选什么，为什么

**主程序采用：直接模型整理＋结构化教学记录＋SQLite版本保存。** 借鉴LangMem的增量摘要与原始聊天分离做法，保留现有Teaching Agent；不要求整个团队安装记忆框架或维护向量服务。

| 方案 | 本轮验证深度 | 决定 |
|---|---|---|
| LangMem 0.0.30 | 在独立环境安装、pip check、运行SDK摘要函数；使用固定模型回复核对消息范围 | 可作为替换组件；不直接承担教学判断和持久化规则 |
| 结构化记录＋SQLite | 41项自动测试；201条合成聊天离线实验；实际DeepSeek摘要、教学、经验提取与确认/停用 | 当前主程序方案，接入成本最低，来源和提交范围容易控制 |
| Mem0 | 官方资料比较，未安装、未测实际检索效果 | 暂不引入；等需要跨项目语义检索时再比较 |
| Letta | 官方资料比较，未迁移Agent运行时 | 借鉴分区、按需读取和版本思路，暂不整套迁移 |

这是对**当前项目接入成本和已测试范围**的选择，不是证明本方案普遍优于所有记忆框架。

来源：[LangMem摘要](https://langchain-ai.github.io/langmem/guides/summarization/)、[结构化提取](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)、[Mem0组件](https://docs.mem0.ai/open-source/overview)、[Letta记忆](https://docs.letta.com/agent-sdk/memory)。

## 2. 实际执行流程

1. 两侧原话先保存在任务中，保留原数组消息编号；确认计划和代码修改仍由后端记录。
2. 教师任务开始时，若较旧消息超过约10000个JSON字符，按最多16000字符的连续消息段整理；每次最多两段，与教学共用5次请求、120秒预算。
3. 每段保存from_id、to_id和摘要前原文哈希；完整源段交给模型，记录实际连续范围。模型只产生摘要，不决定开发是否完成。
4. 本轮读取当前Coding提示词、学生当前问题的完整原文，再选少量近期消息与旧学习证据；重复消息不重复注入。当前提示词和问题之外的原话约10000字符预算。
5. 初始context最多80000 JSON字符，超出明确报错，不静默截断当前提示词或源码。这个限制**不是token精确计数**；真实API usage另行记录。
6. 模型输出回复、教学接续，以及可选的学习更新。后台检查学生引用、字段和状态；学习更新不合法只拒绝该更新，不丢普通教学回复。
7. 重新读取最新任务，核对任务编号、原始记录和源码；没有过期才合并结果。记忆与学习版本和任务在同一SQLite事务保存。
8. 后续回复失败时，之前已经校验完成的摘要批次仍保存；失败批次不推进游标。用户可重试。

每轮最多带最近4段摘要、近期原话和目标关联证据；更早摘要不全部常驻。原始旧话可以通过read_message_history按编号回查。未整理且本轮没加载的数量会提供给模型，不能假装全读过。

尚无自动无限补齐历史：积压很大时需要多次整理；本方案保证来源仍可查，不保证任意久远内容每轮都被想起。原始聊天和代码改动仍在任务JSON中，暂未迁移成独立消息表。

## 3. 学生能力怎样接到Skill

catalog.json定义五项能力：需求与验收、代码理解、证据定位、修改要求、验证迁移。

当前三个外部候选：brainstorming、systematic-debugging、verification-before-completion。每个候选明确requires能力列表，来源链接保留；**仅核实材料存在，尚未在当前Coding上验证提升效果。**

| 记录 | 实际状态 |
|---|---|
| 学生能力观察 | needs_help / supported / independent / transfer_candidate，全部是model_suggestion |
| 证据 | 原话编号与片段、教学轮次、代码哈希；教师和Coding的话不能当学生证据 |
| 迁移表现 | 必须引用学生明确提交的迁移作答，不能拿普通聊天充当 |
| Skill申请条件 | 所需能力各有至少两条不同消息证据，包含迁移表现；这是初版复核门槛，不是经校准的掌握标准 |
| 实际安装 | 始终禁止；候选效果为not_evaluated，没有verified导入或安装接口 |

满足学生侧条件只能产生pending_review申请。真实Agent侧还需要固定模型、任务、工具权限、新会话的启用/禁用对照，以及回归与重复运行结果。参照[Agent Skills评估方法](https://agentskills.io/skill-creation/evaluating-skills)。

当前没有自动总分/XP、人工认证流程或独立程度的可靠自动识别，不能把画像当考试成绩。实际模型的一次分类可能不准，需要人工复核和后续反例更新。

## 4. 小经验怎样提供给Coding

学生交互产生的具体方法与个人偏好分开。模型可起草经验卡，包含适用场景、规则、检查办法、限制、标签与原话依据；保存为draft。

学生点“我理解并保留”后变为confirmed；可停用、再启用或不保留，保留操作前版本。按当前指令的标签匹配，最多3条确认经验传入Coding的learning_context。

**当前Coding仍是固定示例。** 它只记录经验ID及版本，applied=false，不会据此改变固定代码。接真实Coding的同学要把learning_context真正加入请求、记录加载情况，并验证遵循程度。经验确认也不等于该规则已被实测证明正确。

目前经验与画像仅限同一个项目，没有账户身份、跨项目经验检索或通用记忆纠错/恢复界面。

## 5. 持久化和页面

- 新增SQLite learning_versions：task_id、revision、digest、body。revision由记忆版本和学习版本组成；同一版本若换内容会拒绝提交。
- tasks仍保存当前任务，teaching_history保留较旧教学轮次与检查点；原数据没有清空。上线前已在本机data/backups做SQLite备份，不随源码包发送。
- 页面入口：“教程安排 → 学习记录·经验与能力”，可看画像、经验状态和候选Skill，下载Markdown。
- Markdown从数据库当前记录生成，不另存一份可以悄悄过时的事实库。
- 没有通用记忆回滚API。经验停用只影响后续选取，旧对话中仍可能出现该规则；若要求完全删除或纠正记忆，必须继续处理原话、派生摘要与检索，不能把停用当作彻底遗忘。

## 6. 验证结果

### 自动测试和离线实验

41项测试通过，覆盖旧功能、学生/Agent来源区分、伪引用拒绝、当前提示词保留、摘要范围连续、失败不推进游标、已完成摘要保留、版本冲突事务回滚、经验确认/停用、Skill防误安装和Markdown导出。

201条合成消息实验中，原方式仅聊天部分为73756个JSON字符；新方式的完整初始context为14581个字符。比较口径不同，不能称作精确同口径性能提升；它证明这个样例下输入量被控制、原话和当前提示词保留。[离线原始结果](experiments/memory-offline.json)

### LangMem SDK实验

默认pip依赖解析耗时较长；最终使用uv和固定依赖完成安装，pip check通过。因此不能把安装耗时直接归为LangMem不可用。

在本轮SDK机械实验中，一次性输入大量积压消息时，最早原话未实际进入摘要模型，但其ID出现在已整理集合；按8条增量调用的对照例保留了最早原话。实验模型返回固定文本，验证的是范围处理，不是模型摘要质量。结论是需要按实际输入范围审计，并分批处理积压，不能只依赖“已整理ID”字段。[SDK实验结果](experiments/langmem-sdk.json)、[所测源码](https://github.com/langchain-ai/langmem/blob/main/src/langmem/short_term/summarization.py)

### 真实DeepSeek小样本实验

只用新建的合成对话项目，没有把本机密钥复制给脚本。

- 成功把消息0–52整理为摘要，保留早期“不联网、刷新保留、先检查输入”的要求，并标明重复消息不代表真实学生能力。
- 第一次摘要后教学请求失败，原因被现有通用错误归为传输/格式类，**未确定具体根因**。摘要和学生原话保留；同任务重试11.2秒完成。
- 下一次交互11.6秒完成，产生一条requirements表现建议、一条经验草稿和当前提示词分析；原话引用校验无警告。
- 在合成实验中确认经验，再停用；最终状态disabled，未给真实Coding安装任何能力。
- 教学首个成功轮包含3次工具/模型请求，API实际输入约8711、9194、9302 tokens；不能把多次请求费用当成只发送一次context。

这些结果支持“小样本流程已接通”，不证明长期教学连贯、能力评价准确、摘要永不遗漏或Coding稳定进化。第一次失败也保留在报告中，没有只展示成功样本。[恢复与用量](experiments/memory-live-recovery.json)、[真实学习更新](experiments/memory-live-learning.json)

## 7. 怎么复现

主程序仍使用Python标准库：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --check frontend/app.js
python scripts/verify_memory.py
python -X utf8 backend.py --port 8772
```

真实实验先在页面连接DeepSeek，然后运行 `python scripts/verify_memory_live.py`。会新建测试项目并消耗模型额度；最多在第一次失败后再重试一次，不冒充真实学生实验。

LangMem独立实验需要uv及单独环境：

```powershell
python -m venv .venv-memory
uv pip install --python .venv-memory/Scripts/python.exe -r scripts/requirements-memory-experiment.txt
.venv-memory/Scripts/python.exe -m pip check
.venv-memory/Scripts/python.exe scripts/verify_langmem.py
```

.venv-memory不随交接包发送；记忆SDK不是运行工作台的必需依赖。后续优先工作：真实Coding适配、独立能力判断的人工复核、Skill对照实验、经验匹配质量与通用记忆纠错。
