# Coding 从弱到强：第一轮实验

2026-11-13。现有主程序不变；Coding 仍是 SampleCodingAgent，尚未接入真实模型。

## 选择与依据

| 方案 | 优点 | 本轮判断 |
|---|---|---|
| Aider | 已有文件编辑、diff、单次 message 后退出，支持脚本调用 | 首选隔离验证；并不意味着已通过效果评估 |
| mini-SWE-agent | 简短工具循环、轨迹、环境接口，适合工具反馈研究 | 后续备选；默认 shell 权限与 Windows 隔离需要额外处理 |
| 自写 JSON 全文件替换 | 可复用当前 providers，依赖少 | 容易重造编辑和修复循环，暂不选 |

资料：[Aider scripting](https://aider.chat/docs/scripting.html)、[选项](https://aider.chat/docs/config/options.html)、[mini-SWE-agent](https://mini-swe-agent.com/latest/quickstart/)。这是工程适配判断，不是横向性能实验。

基础模型候选固定 `gpt-4.1-mini-2025-04-14`，以账户实际可用性为准；不可用必须记录失败，不能自动换模型。[官方模型页](https://developers.openai.com/api/docs/models/gpt-4.1-mini)。小模型与明确预算可构成弱而可用的起点，不能保证自然产生某类错误，更不能植入错误冒充模型失败。

## 当前实测与复现

原有 53 项 unittest 全部通过（本轮运行）；与真实 Coding 效果无关。

独立环境安装 `python -m venv .venv-coding`，随后 `.venv-coding/Scripts/python.exe -m pip install aider-chat`。
执行 `.venv-coding/Scripts/python.exe scripts/verify_coding_aider.py`；报告在 `docs/experiments/coding-aider-offline.json`。
脚本仅在临时目录通过 Aider 的 apply 模式应用明确标注的合成响应，然后执行独立行为断言。没有模型请求，不代表模型读项目、规划或自然修复成功。报告保留 stdout/stderr 与前后代码。不要对含真实学生信息的响应直接复用原样日志策略。

## 第一个模型对照实验（尚未实施）

限定一个独立 Python 计数器/小型任务列表项目；不改工作台 data。固定 Aider 版本、模型快照、编辑格式、提示词、文件与 token/调用预算。每次重建相同起点、全新会话；禁止恢复聊天、自动 commit、自动 lint/test 和 shell 建议。Aider 不是安全沙箱，进入产品前还需在受限环境执行，不能用工作目录替代权限隔离。

先基线 3 次，再在相同任务集交错运行以下条件，每项至少 3 次：A 无经验；B 一条有来源和适用限制的确认经验；C 固定版本 verification-before-completion 工作流程；D 提供独立测试失败反馈并允许一次修复。D 的额外调用必须为其他组提供等预算对照，否则只能称资源增加。每个任务至少记录成功率、回归失败数、调用/耗时/用量、改动和未完成原因；保留所有失败。无自然失败则换更有区分度的任务，不能修改模型输出制造失败。

先用训练任务产生经验草稿，由 Teaching 引导学生解释证据和适用范围，学生确认。冻结经验后用至少两个未见任务（如重复标题与删除后编号语义）及原有回归集测试迁移。任务验收测试由实验方保管，不能让 Agent 改测试通过。单任务一次成功不能解锁 Skill；学生达标证据与 Coding 效果报告独立。

[Reflexion](https://arxiv.org/abs/2303.11366) 支持研究文本反馈与跨试次记忆这一方向；论文成绩不能外推为本项目收益。经验检索先保留当前标签 top-3；少量经验无需向量库。Skill 是版本化流程干预，工具/测试是外部可验证反馈，模型替换属于配置升级，均不等于参数学习。

## 接口与回退下一步

只有隔离模型实验完成才新增兼容 `step(task,instruction,learning_context=None)` 的可选适配器，默认仍 sample。计划须单独生成草稿和确认；每次 step 只提交已确认的一项，子进程退出即暂停，不在后台继续后续步骤。先在 staging 读写允许的三个网页文件，校验路径、大小、编码与完整结果，再按现有 changes 写入 before/after；运行结果另记实际命令、退出码和输出，供 Teaching 审查。现有独立来源预览继续使用，不能把静态标记检查写成行为测试。

失败不得静默回退 sample；保留失败记录和工作副本。经验停用/Skill禁用在下一轮生效；代码回退使用明确的 before 快照并检查当前哈希，避免覆盖学生后续修改。扩展入口允许学生提交未预设的问题和经验，但仍需来源、限制和新任务验证。候选 catalog 继续 not_evaluated，不安装。
