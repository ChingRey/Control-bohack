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
