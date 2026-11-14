# 双 Agent 框架融合记录

底稿为当前 control-front-integration/control，前端 CSS 未替换，保留 Coding 的百炼/硅基流动配置及 Teaching 的 DeepSeek/OpenAI 配置、代码定位和计划展示。

吸收 origin/main@18ccbd8 的项目内文件权限、各种类型文件和二进制传输、删除/重命名结果接收、失败回滚、900秒执行超时、检查点与只读源码范围接口。

压缩包 Control-source(1).zip 的 FlowController 已审阅。采用其独立流程状态、学生确认、版本证据与恢复回执思路，以已集成的 checkpoint_control 为实际控制器；不另建第三套控制器，不导入固定待办教案、前后测、策略试教或 Skill 流程。

## 当前行为

- 学生与 Coding 的执行请求进入可写执行，普通讨论只读；仅当前项目，Shell、联网、外部文件和子 Agent 不开放。
- 真实项目（mode=opencode）Teacher 使用 project_chat：共享两侧对话、计划、文件索引、带行号源码片段与按需只读文件/历史工具；自然文本回复，不要求教学JSON，不评分，不加载教学Skill，不强制课程，不改文件。
- Teacher 接收完成检查点时只进行项目交流，不决定学生必须学习什么。旧 sample 教程仅用于显式示例兼容，未迁入真实项目模式。
- Coding 仅接收已审核知识/经验；Skill 内容提交强制为空。旧 Skill 协议代码暂保留兼容，不进入 Coding 执行。
- /checkpoints、/project-file 为新版接口，协议见 CHECKPOINT_HANDOFF.md。原 /bridge/* 保留以免打断已交付的接口调用；新接入优先使用新版，不混用两套恢复指令。
- 文件未变化时不会把明确要求写入的任务冒充完成。请求重试、检查点版本与过期结果保护保留。

## 验证

118项自动测试通过，前端JavaScript语法通过。
verify_opencode_write.py 使用真实 OpenCode CLI + 本机模拟模型服务：write 工具创建 src/main.js、二进制文件保留均通过。不是实际模型效果测试。
Teacher 测试覆盖两侧聊天/子目录源码可见、自然文本返回、工具只读、无固定课程注入。真实 Teacher 模型仍需配置账户后验证。

## 本地清理原则

GitHub 仅保护已推送内容。本地旧目录若含未提交修改或学生数据，不直接删除。只删除本轮创建、已验证无独有工作内容的临时审查工作树；忽略验证缓存，保留真实项目 data。当前融合修改尚未推送时不得删除本目录。
