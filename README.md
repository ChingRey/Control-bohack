# Control 集成版

采用 front 分支页面设计，集成 OpenCode Coding、Teaching 后端、计划确认与阶段验收、代码引用定位、经验与审核后项目知识检索。

## 本机启动（Windows x64）

需要 Python 3.10+、Node.js 20+。在 control 目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_opencode.ps1
python -X utf8 backend.py --port 8782
```

打开 http://127.0.0.1:8782 ，在“连接模型”内配置 Coding 或 Teaching。API Key 仅后端内存保存，重启需重填。新建项目不清除配置。不要提交Key或data目录。

## 当前限制

Skill只有申请/预留接口，未验证不可安装；项目二进制资源、删除重命名、shell及依赖安装尚不完整。阶段边界仍需真实模型审查，不代表模型绝不越界。当前75项自动测试通过，不能替代真实模型全流程和教学收益评估。

集成范围及验证见 control/docs/FRONT_INTEGRATION.md。教学策略V2试验分支未包含在此集成中。
