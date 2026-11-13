# 经验是否影响Coding：小样本实测

模型qwen3.6-plus，OpenCode现有执行器，2026-11-13。5个独立新任务/新会话，初始文件均为空。相关任务要求计数器加一、重置、刷新保留；未在任务指令中指定存储键。合成经验规定localStorage键classroom-counter-v1，适用范围仅本实验计数器。经验来源明确是实验夹具，不是学生真实掌握证据，两组都保存同一经验，仅开关不同。运行顺序关、开、开、关。未使用队友尚未合入的knowledge模块，使用当前learning.coding_packet路径。

结果：关闭两次都未加载经验，实际读写键分别counter_value、counter-value；开启两次加载synthetic-storage-convention@1，实际读写均classroom-counter-v1。4次代码在Node VM最小DOM/localStorage桩中均通过加一、重新执行恢复、重置断言；不是浏览器验收。实际文件、回复、工具事件、加载版本保留在experience-uptake/results.json，行为断言记录behavior.json。

不相关控制：经验启用，改做无需存储的静态天气页。加载版本为空，文件未出现经验键。记录experience-uptake-unrelated/results.json。这证明本样本中后端标签检索排除了无关经验，不证明模型读到无关经验也能自行拒绝。

结论：当前小经验加载确实能影响实际编程行为，且一个简单无关场景未被污染。不能据此证明编程能力、教学效果或泛化提高。任意键约定是偏好遵循，不是缺陷修复收益；每条件2次样本很小。当前标签包含匹配不能理解否定、同名异义，仍需更多边界任务及对已召回但不适用经验的模型约束试验。submitted=true只表示已传入，保留applied=false；采用结论由此实验的外部行为检查给出，不自动写学生画像或升级Skill。

复现会产生API费用：先在运行中的8774配置Coding模型，再执行python scripts/verify_experience_uptake.py、python scripts/verify_experience_unrelated.py；node scripts/check_experience_behavior.cjs无需API。脚本只新建隔离实验任务，不改原项目；合成经验通过仅针对新任务的后台保存建立，不作为产品注入接口。
