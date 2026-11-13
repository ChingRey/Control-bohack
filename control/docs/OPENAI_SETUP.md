# OpenAI API Key接入

## 怎么用

1. 启动工作台，打开 http://127.0.0.1:8772 ，刷新页面。
2. 顶部点击“连接模型”，选择OpenAI。
3. 在本机填写OpenAI API Key和账户可用的模型ID。需要模型支持Responses API、自定义函数调用和JSON输出；模型实际权限取决于账户。
4. 保存后点击“审查代码”，等待真实模型结果。保存只验证字段并写入进程，不自动进行付费测试调用。

这里使用API Key，不读取Codex登录文件，也不把ChatGPT订阅登录令牌当API Key。接入对象是Teaching Agent及其记忆摘要；Coding仍为示例。

## 技术实现

agents/providers.py负责提供商区别：DeepSeek使用Chat Completions；OpenAI使用POST https://api.openai.com/v1/responses。请求携带模型ID、JSON输出要求和只读函数工具；不用不兼容的max_tokens或Chat Completions工具格式。

OpenAI函数输出按call_id回传，并保留该轮模型返回的reasoning等必要项。store=false，include请求encrypted reasoning以支持无服务端会话存储的续接；这些项不进入长期教学记录。JSON mode不等于字段与教学判断正确，后端仍校验引用、权限和评价。

密钥只进入后端进程环境和请求Authorization头；不存SQLite、项目文件、聊天、localStorage或源码包。提供商URL固定；OpenAI密钥不回退到DeepSeek密钥。一个教师任务固定配置，运行中切换不改变该任务的服务商。

## 环境变量方式

使用自己的终端设置OPENAI_API_KEY、TEACHING_PROVIDER=openai、TEACHING_MODEL=账户可用模型ID，然后在同一终端启动backend.py。不要把密钥写进提交的脚本；项目不自动读取.env。

## 验证范围

53项自动测试通过，包含Responses工具循环、记忆摘要、拒绝与未完成响应、密钥隔离、配置不落库和旧DeepSeek请求兼容。OpenAI部分使用模拟HTTP响应，不代表真实账户验证。真实调用失败时保留学生作答；401/403检查密钥与权限，429/5xx按既有预算有限重试，模型不可用时更换账户允许的模型。

官方参考：[Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)、[函数调用](https://developers.openai.com/api/docs/guides/function-calling)、[JSON输出](https://developers.openai.com/api/docs/guides/structured-outputs)。

Windows后台使用独占端口，重复启动会明确失败，避免新页面连接旧后台。
