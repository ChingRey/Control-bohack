# API模型筛选补充（2026-11-13）

建议先保持OpenCode，测试qwen3-coder-flash；第二候选GLM-4.5-Air（需核对当前官方API可用性）。两者都只是适中能力假设。Claude Code作为框架对照而非同时更换框架和模型。MetaGLM官方cookbook确认GLM-4.5系列与Claude Code可集成，但不证明其在OpenCode上有相同成绩，默认主/辅助模型路由必须关闭以保持实验固定。

官方资料：Qwen模型卡 https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct ；GLM报告 https://arxiv.org/abs/2508.06471 ；GLM Claude Code集成 https://github.com/MetaGLM/glm-cookbook/blob/main/vibecoding/glm-4.5-claude-code-integration.md ；MiniMax https://github.com/MiniMax-AI/MiniMax-M2.5 。MiniMax厂商报告M2.5的SWE-bench Verified为80.2%，先用作较强对照，不从价格低推断能力弱。GLM报告64.2%属于完整GLM-4.5，不能归给Air。Qwen开源30B版本与API Flash不假定严格同权重。

未找到足以证明当前OpenCode+上述模型在我们的网页/小游戏任务上适中的官方统一基线。各厂商框架、预算、数据划分不同，不能按跨表分数直接排序。API地区、旧版是否可买、snapshot需账户确认，未核实前不要为旧模型购买长期套餐。

首轮：固定OpenCode版本与正常预算，不启用增强Skill，每模型两个项目各3次，统计交付、回归、越过阶段和可教学自然问题。之后固定模型测试单Skill，不能更换强模型当升级成果。

界面更新：左侧只显示设置计划、开发计划及其阶段、总结预留；中央Coding聊天描述/修改计划，明确输入确认计划、执行当前阶段、继续下一阶段控制。61项回归及JS语法通过，未做浏览器视觉验收。
