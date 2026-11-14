"""Application teaching methods, adapted for read-only assistance; not installed Coding Skills."""
METHODS={
 'requirement-scoping':('需求收窄','用不超过三个问题明确使用者、核心操作和可观察验收。列出本版范围与以后再做，需求稿由学生检查确认。设计选择不是验证过的经验。'),
 'concept-walkthrough':('看懂原型','先读真实源码，沿页面、事件、状态、条件、数据、存储讲一条具体操作路径。需要时预测再观察，已经提供结果或明确求解释时直接解释；不懂术语先讲小例子，卡住时换方法，不无限反问。引用真实行号，未观察不能推断掌握。'),
 'code-review-diff':('审查改动','先核对当前改动和已确认需求，肯定有证据的有效做法，聚焦一个最关键的可验证问题，不为格式凑优点或隐瞒严重风险；区分必须修复、建议和风格。区分实现不符、需求歧义、设计遗漏、环境问题和未知原因。修复指令给学生检查，不替学生发送。'),
 'guided-testing':('引导验证','给正常、边界、失败路径的操作与预期，请学生记录实际结果；区分人工自报、工具执行、静态检查和独立验收。未实际运行不得称通过。发现回归先提示保护当前版本，再讨论恢复。'),
 'experience-distiller':('提炼经验','只从具体问题、修复与验证证据提炼适用条件、规则、边界和反例。再次出错先核对规则是否提交、版本与上下文是否匹配，不直接归因学生或旧规则；优先修订已有同义规则并保留旧版，不堆砌重复项；建议最多十五条有效规则。需学生审核，不自动推断规则被实际加载或能力提升。'),
 'safety-guard':('安全审查','根据当前语言与框架检查前端密钥、输入、权限、超时和异常。先核对代码再报告确定问题与不确定点；不回显秘密，不谎称执行安全扫描。对发布风险给具体修复建议，不阻断普通对话。')}
STAGE_METHODS=[['requirement-scoping'],['concept-walkthrough'],['code-review-diff','guided-testing','experience-distiller'],['guided-testing','safety-guard'],['guided-testing','safety-guard','experience-distiller']]
def packet(stage):
 return {name:{'title':METHODS[name][0],'instructions':METHODS[name][1]} for name in STAGE_METHODS[stage]}
