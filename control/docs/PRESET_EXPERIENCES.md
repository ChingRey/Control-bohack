# 初始经验库：从已有代码提炼的15条预设

版本presets-from-code-v1。内容在agents/teaching_assets/evolution/presets-from-code-v1.json。没有额外联网搜集新教法，也没有把来源文件中的外链当作本轮已读论文。以下为本地已有设计的结构化整理与适用情景分析，尚未验证效果。

## 来源与整理

- 原seeds-v1.json的5条：具体例子先行、一次一个重点、补必要前置、回到当前作品、逐步减少提示。保留原动作和状态，补来源、设计理由、例子及证据计划；不覆盖人工修改或重新启用已停用条目。
- strategies/initial-v1.json：点明问题→讲原理→回到作品。
- workflow_methods.py requirement-scoping：用核心操作收窄第一版。
- library/catalog.json L02：把愿望写成可观察的验收。
- workflow_methods.py concept-walkthrough：沿一次操作追踪数据路径。
- teach.py ADAPT knowledge/judgment：用最小对比区分相似概念。
- teach.py BASE observe：先预测、再观察、解释差异。从固定待办例子泛化为当前作品，不导入固定答案或强制考核。
- workflow_methods.py guided-testing：正常／边界／失败路径验证。
- workflow_methods.py code-review-diff：围绕本轮改动解释关键问题。
- skills/diagnose/SKILL.md：连续卡住时换解释路径。
- skills/assess-summarize/SKILL.md：换相近情境检查独立应用。

每条含title/when/action/verify/limits/tags/source/rationale/example/source_refs/evidence_plan。source_refs记录文件、段落/函数与SHA256；示例明确为设计示例，不是学生实录；evidence_plan关联当前六维量表的具体条目，说明要观察什么、从哪里取证，不伪装为已有得分或已实现客观指标。

## 状态与迁移

单用户共享SQLite库第一次读到新版时，幂等导入。原五条保持各自状态；新十条为origin=preset、status=trial、verified=false，界面为预设／待验证。内容不超过40条上限，满时记录跳过，不移除旧经验。

导入有独立preset_import变更批次和修改前版本，前端可撤销此项/本轮或恢复历史版本。preset_versions标记在反思、管理、撤销和整库恢复中保留，撤销后刷新不会再次导入或复活已停用经验。

下次选教法先匹配场景；匹配的尚未验证条目优先，同样未提供且匹配时反思生成经验优于预设，每轮最多一条待验证。验证焦点带具体示例与观察计划，不能把这些设计当学生证据或权限。

## 验证

33项针对性测试通过，覆盖目录完整性及来源哈希、既有人工修改/停用保护、导入幂等、撤销/恢复后不重导、场景匹配/停用、原有评价反思入库及跨项目链路。真实Chromium临时库检查初始15条、预设导入记录、来源与验证计划、模型夹具反思新增、第二项目加载及撤销。未调用真实账户，不证明教法有效。
