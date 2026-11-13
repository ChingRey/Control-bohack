# 阶段工作流接入状态

2026-11-13：已接现有前后端的模型无关工作流骨架，不是已安装/连接的 OpenCode。

运行 backend.py 后点击“新建 OpenCode 项目”。输入每行一个阶段的计划草稿，保存后与教师讨论，再确认。可编辑当前三个项目文件、预览；教师沿用只读工具并能看相同的 plan/plan_draft。连接预检产生真实工作台事件和能力装载预检，不产生虚构工具轨迹、不推进阶段、不写示例代码。

新 API：POST /api/tasks {coding_mode:opencode}；任务路径下 POST coding/plan-draft {plan:[...]}、coding/capabilities {experience_enabled:bool}、coding/preflight {}。既有 plan/confirm 与文件编辑接口兼容。steps/run 对未接通模式明确拒绝。示例模式不变。

agents/coding_workflow.py 定义阶段、事件、能力版本和 transport 注入接口。小提升复用 learning.coding_packet 的已确认经验，支持禁用，记录版本与 payload 哈希；预检 submitted/applied 均 false。大提升保留 skill_bindings 接口，当前强制过滤所有 Skill，catalog 仍未验证、不可安装。Teaching 自动审批与有效性报告验证器尚未实现，不能宣称已自动升级。

本轮没有安装 OpenCode、选择模型或接入 API。后续必须锁定框架版本，连接真实 transport，补充后台执行、事件映射、改动收集、中断、受限环境和检查点等待集成测试，再启用执行；不能只去掉未连接拦截就上线。现在前端可试计划讨论与预检，不能试真实开发。未进行浏览器视觉验收。
