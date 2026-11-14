# 前台教学提速与开发确认解耦

2026-11-14。保留当前教学提示、主动确认与后台反思，不替换队员整份文件。

## 接入位置

- agents/providers.py 的 request 新增 stream、thinking_budget 可选参数。只有前台 project_chat 显式传入 2048，且为 SiliconFlow GLM-5.3 系列时，发送 enable_thinking=true 和 thinking_budget=2048。后台调用不传此参数，原有预算不变。沿用主机已配置模型，不自动换为 Flash。
- agents/teaching.py 的 project_chat 可见输出 max_tokens=1200，单轮最多3次真实请求（包括工具轮次和HTTP/TLS重试），最后一轮不提供工具。旧 sample 和后台默认5次预算保持。原60秒单次、120秒整轮时限仍有效。
- agents/model_stream.py 读取 Chat Completions SSE 或 Responses typed events。逐段发布正文，隐藏 reasoning、工具参数及 continuity_memory；完整消息和工具参数仍在本轮内存组装。OpenAI加密推理项只随当前工具循环接续，不进入预览、学生记录或经验。普通JSON响应兼容保留。
- Teaching运行进度保存脱敏的 partial_reply，前端350ms取最新快照并显示；完成后替换为唯一正式消息。中断/截断不得冒充完成，保留片段及重试入口。记录首段正文耗时。
- 前端计划/阶段确认不再等待Teacher。后端仍校验学生确认、计划/代码版本、阶段和幂等；不会让Teacher自行继续开发。
- 新的Coding请求/继续开发会将尚未完成的Teacher标记superseded，保留脱敏片段与来源检查点到SQLite teaching_history（kind=run），发出合作式取消信号。旧线程不得更新新任务或学习记忆。流式读到下一事件时退出；若服务尚未返回任何字节，仍受原网络超时限制，不保证撤销上游已接受的计算或计费。下一开发检查点可启动自己的Teacher。
- 整理与经验反思仍独立运行。演化实现未修改，公共provider默认调用不施加前台推理限额。

## 验证与局限

115项针对性回归通过，覆盖版本/确认/幂等、部分回复、EOF/截断、工具参数组装、Responses完成项、取消与预算、3次上限包含重试、前台限额不影响后台。不是完整测试套件；旧学生配置入口相关测试与当前403策略不一致，未列入本次通过统计。

真实Chromium+本机SSE模拟服务验证：正文在完成前出现；Teacher期间按钮可用；点击后Coding完成；旧回复不能覆盖新阶段；无推理/隐藏笔记泄露；完整回复只保存一次。临时数据库，无真实模型调用。结果在 data/verification/teacher-streaming-browser.json。

参数格式参照SiliconFlow官方Chat Completions/Stream Mode文档与OpenAI Responses streaming事件文档。2048/1200/3是工程预算，不是已证明最优的教学参数；服务端是否严格执行推理上限、首字耗时和教学质量仍需真实账户验证，流式不消除模型输出正文前的思考等待。
