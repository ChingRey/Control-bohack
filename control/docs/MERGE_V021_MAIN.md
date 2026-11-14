# V0.2.1 与远端 main 合并记录

2026-11-14：将本地 120895f（对齐接口）与远端 e32c3e8 合并。

保留双方功能：独立 V0.2.1 Mock 接口、工程教学接续、90秒单次/240秒整轮Teaching预算、Coding900秒与项目文件权限；同时合入远端教学输入精简、接续记忆、阶段范围和学生验收交互。

三个冲突文件为 coding_workflow.py、teaching.py、backend.py。阶段方法与无计划文件执行防护共存；相同内容edit不当权限失败，真实部分改动伴随工具错误时保留远端待审查行为并记录警告；教师深度提示词加入远端阶段范围和接续笔记协议，保留只读权限。

验证：200项unittest通过（含启用的浏览器用例）；前端JavaScript语法检查通过；scripts/verify_teaching_v021.py在真实Windows asyncio、HTTP、OpenCode CLI及浏览器下通过。模型为本机合成服务/公共Mock，没有付费模型质量验收。

合并前原交接报告描述的是当时的工作区状态；本次以Git实际合并提交和推送结果为准。运行日志仍保留在本机data/verification/v021，不上传学生运行数据。
