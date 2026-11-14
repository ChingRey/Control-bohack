# V0.2.1 独立接口集成（2026-11-14）

项目可显式启用独立教学接口。`decide()` 根据检查点、课程和学习状态选课，`teach()`、`evaluate()`、`evolve()` 使用 Mock 联调。启动、恢复与验收见 [接口交接说明](docs/TEACHING_V021_INTEGRATION.md)。

Teaching单次网络等待默认90秒、整轮预算240秒，可配置；Coding默认900秒不变。教师失败提示已区分服务HTTP状态、超时和网络错误。旧文档中30秒/120秒描述不再适用于本版本。

# 硅基流动双模型接入补充（2026-11-14）

已融合用户双模型API交接包：Coding和Teaching均可选择硅基流动，默认模型分别沿用包中的Qwen/Qwen3-Coder-30B-A3B-Instruct与zai-org/GLM-5.3。保留按需教学资料和只读Teacher；两侧分别填写Key，保存不等于真实调用已验证。见docs/SILICONFLOW_API.md。

# 当前融合版本（2026-11-14）

- Coding：保留百炼/硅基流动配置，开放项目内文件工具；先出计划，聊天内 ✓ 确认并执行 / ✕ 修改，阶段结束暂停。计划批准不依赖聊天关键词。
- Teacher：真实项目采用只读自然交流，可查看两侧聊天、计划、按行源码和检查点；不预设课程、评分或改代码。
- 教学结束整理与 evolve() 为可替换接口，当前使用 Mock；Mock 知识不能进入 Coding 检索。真实候选需要审核，检索仍限当前项目；Coding Skill 加载关闭。
- 校验：127项自动测试、JavaScript语法检查通过；真实CLI模拟服务写入/二进制保留通过；已有真实模型文件写入与Teacher只读核对记录。
- 接口见 docs/CHECKPOINT_HANDOFF.md、docs/POST_TEACHING_KNOWLEDGE.md；当前架构见 docs/FRAMEWORK_INTEGRATION.md。旧示例说明仅适用于 sample。
- 本机 API Key 仅在进程内保存，重启需重填；data/、缓存、日志不交付。模型可用性以各自账户为准。

---

# Control 开发交接

一个教人 Vibe Coding 的本地工作台：学生指挥 Coding Agent 开发，Teaching Agent 帮助学生理解技术、审查计划和代码，并记录学习过程。

**当前重点：验证教学交互。Teaching 可接 DeepSeek / OpenAI；Coding 仍是固定待办示例，没有接真实编程模型。**

## 已经实现了什么

| 功能 | 当前做法 |
|---|---|
| 从需求到计划 | 初始只有“设置计划”；输入需求后生成固定草稿，学生讨论、编辑并确认后才能执行 |
| 分步开发、停下审查 | 每次确认只执行一步，真实修改本地项目文件，然后暂停 |
| 连续教学对话 | 教师能看两侧聊天、需求、计划、源码、改动和学习记录；按当前情况选择追问、讲解、提示、总结或迁移检查 |
| 技术选学 | 页面结构、事件、输入处理、本地存储；可选“学一下”或“稍后”，不阻挡开发 |
| 看代码和运行结果 | 文件编辑保存、真实网页预览、页面加载与 JavaScript 异常反馈 |
| 记忆与学习记录 | 分段整理旧对话，保留当前提示词和原话证据；SQLite保存版本，支持导出Markdown |
| 能力画像与个人经验 | 五项能力分别记录待复核表现；经验先为草稿，学生确认后可提供给Coding，也可停用 |
| 思维导图和布局 | 教师输出结构化导图；前端画 SVG；面板宽高可拖动，教程安排默认折叠 |
| Skill对应与申请 | 三个候选Skill对应学生能力要求；证据满足后可申请复核。候选均未完成Coding效果验证，**不能安装或宣称能力跃升** |

## 整个流程

1. 从头体验 → 学生说想做什么 → 出现计划草稿。
2. 与 Teaching Agent 讨论目标、拆分、验收方式；学生确认计划。
3. 确认执行当前一步 → 示例 Coding 写文件 → 停下。
4. 看代码和运行结果 → 与教师交流，按需学习技术、找问题、说明理由和验证办法。
5. 学生手动修改或继续执行示例步骤；教师持续记录本项目的教学安排。
6. 教师可提出新情境题；学生明确提交后，产生掌握建议，满足条件才可申请后续能力改进。

“教学示例”按钮是直接进入含预置遗漏的审查版本，方便测试教师，不是从头开发流程。示例第三步会写入预设修复，不能当作模型学会的证据。

## 启动与验证

需要 Python 3.10+，不需要 pip 或 npm。双击 `启动工作台.cmd`，或在本目录运行：

```powershell
python -X utf8 backend.py --port 8772
```

打开 http://127.0.0.1:8772 ，点击“连接模型”，选择 DeepSeek 或 OpenAI，填写自己的 API Key 和账户可用的模型 ID。密钥只在后端进程中保存，重启需重填；代码与对话会发送到配置的模型服务。没有配置时为明确标注的固定示例回复。

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
# 可选，需要本机有 Node：
node --check frontend/app.js
```

自动测试用临时数据库和模拟模型响应；不代表真实模型教学质量已验证。

## 目录与交接

```text
control/
├─ backend.py              # HTTP 接口、流程协调、SQLite、文件与预览服务
├─ agents/
│  ├─ coding.py            # 固定示例编程执行器，后续替换真实 Coding Agent
│  ├─ teaching.py          # 教学上下文、只读工具、校验与课程记录
│  ├─ providers.py         # DeepSeek Chat Completions / OpenAI Responses 接口适配
│  ├─ memory.py           # 分段摘要、原话选择、范围记录与Markdown导出
│  ├─ learning.py         # 能力观察、经验确认/停用、Skill申请
│  ├─ learning_assets/    # 候选Skill与能力的对应表
│  └─ teaching_assets/     # 教师提示词、摘要提示词、5份教学 Skill
├─ frontend/               # 原生 HTML / CSS / JavaScript 工作台
├─ tests/                  # 接口、记录保护、教学校验等测试
├─ docs/
│  ├─ API.md               # 当前真实接口和模块输入输出
│  ├─ TEACHING.md          # 教学设计、约束、实验方法与来源
│  └─ CLEANUP.md           # 本次清理范围
├─ scripts/package.py      # 生成不含学生记录的交接压缩包
├─ AGENTS.md               # 给接手开发的 Agent 的说明
└─ data/workbench/         # 本机运行数据，自动创建，不随源码交接
```

给组员发 `dist/Control-source.zip` 即可；在本目录运行 `python scripts/package.py` 可重新打包。包含源码、提示词、教学 Skill、测试和文档，不含本机聊天、项目记录或缓存。

开发先读 [AGENTS.md](AGENTS.md)，接接口读 [docs/API.md](docs/API.md)，调整教学读 [docs/TEACHING.md](docs/TEACHING.md)。当前仅供本机实验，没有账户系统、通用代码执行环境或公网部署能力。

本轮实现与验证见 [MEMORY_IMPLEMENTATION](docs/MEMORY_IMPLEMENTATION.md)；原始设计见 [MEMORY_DESIGN](docs/MEMORY_DESIGN.md)。主程序仍无第三方依赖，LangMem SDK只用于可选对照实验。

## 本轮验证到哪里

41项自动测试通过；201条合成消息的离线实验验证了原话保留、当前提示词保留和输入量控制。真实DeepSeek实验已产生历史摘要、提示词反馈、能力观察与待确认经验，并验证确认/停用。第一次教学请求失败，保留摘要后重试完成；原始失败也记录在实验报告中。

这些是小样本集成验证，不证明学习评价准确、教学长期有效或Coding能力提升。Coding目前仅接收并记录经验输入，不按经验改变固定代码；没有自动安装Skill。

在右侧“教程安排 → 学习记录·经验与能力”查看；新学习记录出现依赖模型按结构返回有效证据，并非每轮一定产生。

## OpenAI API Key接入

在“连接模型”选择OpenAI，填写API Key和模型ID，再保存。必须使用该账户可调用、支持工具调用与JSON输出的模型；不会替你猜测模型权限。保存配置不等于验证成功，点击“审查代码”才会实际调用。

OpenAI使用官方Responses API，记忆摘要也使用同一服务商；不需要登录Codex或读取Codex凭据。此接入只切换Teaching模型，Coding依然是固定示例。提供商URL固定，密钥不写入数据库或浏览器持久化。

当前共53项自动测试；OpenAI网络部分使用模拟响应验证，真实账户调用需本机填写密钥后验证。详见[OpenAI接入说明](docs/OPENAI_SETUP.md)。

## Coding → Teaching 检查点

OpenCode 阶段执行或计划生成成功保存并暂停后，自动发送一次检查点给 Teaching；固定示例执行同样提供该事件，普通聊天和失败执行不发送。教师失败保留开发成果，可用“审查代码”重试。事件字段、版本与只读源码接口见 [API](docs/API.md#coding--teaching-检查点契约)。这不表示已通过行为测试或学生已掌握。
双向检查点现支持学生确认的修改要求、一次性恢复、每轮修改后再次返回检查点、Skill通知与未启用回执。可新建 `checkpoint_delivery=manual` 的任务，在不连接Teaching Agent时通过HTTP接收事件并恢复下一阶段；[协议与验收](docs/CHECKPOINT_HANDOFF.md)包含字段、状态、错误和重试约定。

已修复明确创建JS文件被分入只读聊天的问题；项目内文本源码和配置支持创建、修改、重命名、删除。计划/讨论仍只读。Shell和外部联网工具尚未开放；实际OpenCode写文件可用 `python scripts/verify_opencode_write.py` 通过本机模拟模型验证，无真实模型费用。

通用项目文件接续：已移除扩展名/文件名白名单，任意项目内文件路径均可创建写入；文本与二进制分别保存和传输，binary_files快照只含元数据。明确开发授权在未确认计划时也进入可写执行，不将“执行/继续”静默降为只读。执行超时保持900秒；health.coding公开file_access=project_all_types、permission_revision=2和execution_timeout_seconds以核对运行版本。Shell和外部联网权限未改变。

## Skill 隔离评估

见 [评估报告](docs/experiments/skill-audit-20261113/REPORT.md)：64项加载成功，有效真实效果样本为0，不能据此宣称提升。

## 五阶段工作流

左侧“项目材料与阶段”维护需求、设计、经验和教学记录，确认需求后可生成可见原型；代码栏提供改动查看、版本保存/恢复和行为验证记录。Teaching仍只读，按当前阶段结合六类应用教学方法交流。参见[实现范围](docs/WORKFLOW_IMPLEMENTATION.md)，已接入实际浏览器/项目测试、Python/Node服务、证据交付包与显式个人经验留存；公网部署账户及真实模型/教学效果仍需独立验收。

完整本地流程现已包括消息排队、真实材料整理与审核、经验修订/停用、当前功能验收、真实浏览器用例、项目测试、Python/Node服务、交接包及个人通用经验。Teaching继续只读；真实模型效果和公网平台发布单独验收。真实页面复测：`python -X utf8 scripts/verify_workflow_browser.py`。

## 按需教学资料

已将筛选后的31条来源及21张课卡接入只读Teaching，按问题和阶段最多提供两张；选学、稍后与最近参考来源均在现有页面中可用。资料已提供不代表教学效果已验证，见[教学资料接入](docs/TEACHING_LIBRARY.md)。
