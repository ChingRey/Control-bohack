# 当前模型+Agent能力：首轮评估

2026-11-13，实际health模型qwen3.6-plus，OpenCode现有运行中配置（不是尚未重启的源码补丁）。2个独立空白项目+1次同项目需求变更，无经验/Skill加载。固定任务规格，测试在模型产出前由实验端制定且不传给Agent。模型未运行测试；实验端在Node VM执行纯JS测试，无浏览器/依赖环境。小样本每任务仅1次，不可当官方排行榜分数或中小项目胜任证明。

任务：money精确分币计价；todos标题清理/ID/快照隔离；revision增加完成状态切换和筛选并保留旧功能。

结果：初版money8项和todos5项共13项通过；变更后5项组合检查通过（含旧功能回归）。3个Agent轮次均完成，write/read/edit事件均completed。最终回复没有宣称已运行测试；未发现本样本虚假测试完成声明。无本轮生成失败样本，不能为了教学制造Bug。

五点评价：功能正确通过；已覆盖边界通过；一次需求变更回归通过；本轮文件工具完成但不覆盖shell/构建/安装/网络/子目录；完成声明本轮未见虚假测试声明，仍需更大样本。代码还有未测限制，例如金额大数溢出、存储并发、长轮重构；不能把规格没定义的输入事后直接判成缺陷。

官方依据：SWE-bench用真实仓库issue+补丁+容器测试，%Resolved；https://www.swebench.com/SWE-bench/guides/evaluation/ 。Terminal-Bench报告resolution rate、cost、tokens及置信区间，https://www.tbench.ai/ 。ProgramBench通过文档和参考程序重建软件，用隐藏行为测试，https://programbench.com/ 。Anthropic建议独立验收、轨迹检查、多次试验，https://www.anthropic.com/research/demystifying-evals-for-ai-agents 。这些是方法参照，本轮任务不是直接抽取的官方基准题。

研究线索：SlopCodeBench研究连续需求变化下结构与冗余退化（https://arxiv.org/abs/2603.24755）；Engineering Pitfalls研究工具自身集成故障（https://arxiv.org/abs/2603.20847），两者不能混为模型自然犯错。我们已有EPERM、权限拒绝、文件提交限制、引用跳转问题属于集成问题，不应作为学生模型缺陷教学成绩。

原始数据raw.json/revision.json；执行测试checks.json/revision-checks.json；脚本scripts/verify_coding_baseline.py、check_coding_baseline.cjs、check_coding_revision.cjs。需求变更调用原文在revision.json。下一步选真实多文件小游戏3个连续需求，正常/边界/回归固定测试，各3次；再固定相同环境比较更小模型。先恢复足够正常项目工具，避免环境故障污染能力评价。
