# 本次整理

整理范围仅为 control 项目，不修改同级调研资料或其他项目。

## 保留并重新归类

- backend.py继续作为唯一服务启动入口。
- Teaching实现、提示词和教学Skill移入agents；固定Coding示例从backend.py拆入agents/coding.py。
- workbench前端改名为frontend；测试移入tests；教学细节移入docs。
- README重写为当前功能与启动说明；AGENTS.md供其他同学的Agent接手；docs/API.md描述实际已实现接口。
- 本机data/workbench中的数据库、项目和学生记录全部保留，源码包不包含它们。

## 删除

- server.py、web/、data/scenario.json、启动.cmd：更早的纯前端固定演示，已被当前工作台替代。
- WORKBENCH.md、docs/contracts.md、docs/backend-v1.md：过时的初版介绍或未落地架构设想，容易和真实实现混淆；已由新README、AGENTS、API说明替代。
- 根目录的7张开发预览PNG及Python缓存：非运行资源。
- SampleCodingAgent.plan：从未使用的旧方法；真实计划入口仍在backend.py。

## 发给组员

运行 `python scripts/package.py`，发送dist/Control-source.zip。压缩包只选源码、提示词、Skill、测试、文档和启动入口；不复制本机data、截图、缓存或环境配置。
