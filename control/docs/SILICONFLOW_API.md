# 硅基流动双模型接口融合（2026-11-14）

来源：用户提供的Control-双模型API交接版-20261114.zip；来源哈希和实际合并范围见experiments/siliconflow-api-merge-20261114.json。

## 配置

在“连接模型”中分别保存两侧配置：

- Coding：服务商siliconflow，示例默认Qwen/Qwen3-Coder-30B-A3B-Instruct，调用https://api.siliconflow.cn/v1，由原生OpenCode完成项目文件工具调用。
- Teaching：服务商siliconflow，示例默认zai-org/GLM-5.3，调用https://api.siliconflow.cn/v1/chat/completions，使用Chat Completions工具与JSON格式。两种模型名称沿用源包，不保证所有账户当前都有权限；可以填写账户支持的其他模型。

两处可以使用用户明确输入的同一个有权限的Key，但应用不会自动将另一侧或另一服务商的Key拿来补缺。Key只在进程配置中保存，界面不回显；切换服务商会清空待填写Key，重新打开配置保留相应服务商与模型。

Teaching还可通过TEACHING_PROVIDER=siliconflow、SILICONFLOW_API_KEY、TEACHING_MODEL设置。显式选择siliconflow时，TEACHING_ENDPOINT不能把它改发到别处；SILICONFLOW_API_KEY缺失时不回退到DeepSeek/OpenAI/通用Teaching Key。单独提供SILICONFLOW_API_KEY且无其他优先配置时可识别该提供商。Coding仍需独立配置，不自动复用Teaching的环境密钥。

POST /api/settings/teaching：provider/api_key/model；model省略时采用该提供商默认值。POST /api/settings/coding：provider/api_key/model/region（硅基流动固定国内入口，不使用百炼地区选项）。配置保存不等于调用已验证。

## 融合边界

保留新项目的按需教学资料、来源记录、消息队列、代码版本、测试与交付。Teaching保持两个只读工具，Coding项目内任意类型文件工具和900秒执行上限保持。保留模型输入脱敏与OpenAI Responses适配；不会整份覆盖旧providers.py。

源包中phase_contract及review_only执行提示依赖另一版阶段流程，不属于本次API差异，没有混入当前执行器。源包随附的调用记录与本次适配验证分开，不宣称本轮已经消耗用户账户完成真实模型联调。
