# V0.2.1 接口集成实际检查报告

日期：2026-11-14。仓库：C:\Users\momo\Desktop\Control-bohack-workflow-fetch。分支：integration/teaching-v021。

当前基线提交：1e6b124003ae8f4a3db7ec92e91b9aa0fc882268。本轮修改未提交、未推送；保留接手时已有的教学改动。完整工作区文件和SHA-256见 ACTUAL_FILES.json，其中明确包含此前保留的修改，不能全部归因于本轮接口集成。

## 已实现

独立V0.2.1边界及四个公共Mock，原内部schema_version=1保留。公共contracts.py、Schema及交接包原文件不修改，外层命名空间加载胶水独立。

从真实项目数据库记录构建任务/检查点、不可变证据来源、context_id；从已保存执行动作、学生原话、评价构造第二轮历史；从后台审批的Mock演示策略库取候选，持久化initial/continued/switched分配。只在操作者授权后允许切换，保留分配历史。

带项目范围会话和单独操作者权限的HTTP端点、前端联调对话框、失败显式重试、过期源码拒收和已有Coding状态机的幂等恢复已接入。已启用项目支持Coding检查点自动交接。Mock结果不写正式掌握、不解锁Skill、不发布候选策略，演化实验独立登记为pending。

## 实际测试

| 验证 | 结果与范围 |
|---|---|
| 公共包pytest | 41项通过，原测试源文件未修改；有依赖插件弃用警告，不影响结果 |
| 项目全量unittest | 180项通过，已启用可选浏览器测试，0失败、无跳过；最终日志无后台线程异常 |
| 前端语法 | app.js、workflow.js、teaching-v021.js通过node --check |
| 原生Windows asyncio | asyncio.open_connection向实际HTTP后台发请求并收到200，使用真实原生事件循环与套接字 |
| HTTP链路 | 四接口、学生提交、评价反馈、授权切换、请求幂等、匿名拒绝、真实上下文映射通过 |
| 原生OpenCode CLI | 真实CLI接本机合成模型服务，先创建src/products.js并暂停，教学后显式恢复创建src/cart.js；重复恢复不再推进 |
| 浏览器 | 真实Chromium 21步通过，无运行时错误；打开入口、项目会话、教学动作、学生回答、形成性评价和续轮均验证 |
| 故障与权限 | 未授权切换/虚构证据/虚构课程拒绝；失败恢复显式重试不重复加步；跨项目会话和学生越权拒绝 |

测试数据和最初开发计划是隔离夹具，教学服务是公共确定性Mock，Coding模型是本机合成服务。上述测试是真实进程、HTTP、浏览器和文件写入联调，不是真实付费模型或教学效果验收。未将Mock固定满分当作学生学会。

测试初期发现并修复：旧文件系统PermissionError被误映射403；模拟服务对转义阶段字段识别错误；临时任务销毁与后台收尾竞争。最终结果以上表为准，早期失败不隐藏为通过。

## 主要修改文件

- backend.py：新增受权限保护路由、自动检查点交接、重启恢复、旧快照不暴露独立上下文，保留任务锁与旧接口。
- agents/teaching_v021.py：映射、持久化、幂等、公共语义校验、策略分配、失败重试、服务注入入口。
- agents/teaching_contract_v021/：未修改公共包及独立加载胶水。
- frontend/teaching-v021.js、frontend/index.html：独立Mock联调入口；frontend/app.js显示具体教师错误。
- tests/test_teaching_v021.py、tests/test_failure_diagnostics.py、scripts/verify_teaching_v021.py：自动回归及真实进程/浏览器验收。
- scripts/start_teaching_v021.ps1、docs/TEACHING_V021_INTEGRATION.md、docs/API.md、README.md：部署及接口说明。
- agents/opencode_executor.py、agents/coding_workflow.py、agents/teaching.py：同期用户反馈的故障修正，详见下文。

## 实际调用路径与样例

POST /api/tasks/:id/teaching-v021/decide、teach、evaluate、evolve。

GET /api/tasks/:id/teaching-v021 查看后台生成的公共请求和响应；外层HTTP收据另有mode及禁止认证标记。http-examples.json保留本轮隔离HTTP请求、收据以及四接口完整公共请求/响应，既有首次也有带真实持久化回答/反馈的续轮。

详细会话、策略授权、respond、resume和配置接口见 TEACHING_V021_INTEGRATION.md。

## 部署状态

已在本机 http://127.0.0.1:8772 启动最终后台，联调JS返回200。Teaching单次等待90秒、整轮240秒，Coding900秒，实际健康检查见 DEPLOYMENT.json。

当前服务Teaching为sample、Coding未配置：模型密钥仅进程保存，未读取其他软件凭据，未自动重放付费模型请求。使用真实两侧模型需要在工作台重新连接。

当前服务未设置 CONTROL_V021_ACCESS_TOKEN，V0.2.1受保护调用因此保持关闭；不是匿名开放。操作者可关闭当前后台，再运行 scripts/start_teaching_v021.ps1，输入自行设置的访问令牌，在联调窗口连接项目后启用。隔离验收中该授权流程已实际验证。没有公网部署，也未设置多用户身份系统。

## 同期Teaching/Coding故障说明

最近教师失败记录为30.2秒后结束，旧代码把多种网络异常统一成配置错误，无法从旧记录确认具体HTTP状态；与旧30秒超时吻合，但不能据此断言服务商账户异常。已增加明确的HTTP/超时/连接错误提示和可配置90秒等待，未声称真实模型已恢复。

Coding失败记录包含oldString与newString相同的无变化edit，和另一次glob的ripgrep执行错误；不代表写入权限被重新关闭。已修复无变化编辑误报、保留真实错误原因，并避免无计划直接写文件的索引越界。项目任意正常文件类型写入能力、讨论只读、Teacher只读与Coding900秒保留；项目外目录和shell等权限没有在此轮扩大。

## 尚存问题

1. 正式课程/稳定ID/Rubric/独立考核题及维护人待课程组确认；当前审批库只允许Mock联调，不能替代正式课程。
2. 真实模型服务未接入V0.2.1，未实现教学算法；可通过可信install_service入口替换服务，必须另行提供已审核完整课程资产。
3. 单进程每任务串行；调用时持锁，正式慢服务可能阻塞同项目操作。没有多进程/远程事务，远程服务需自行request_id去重，文件与SQLite仍无跨资源事务。
4. 旧站总体仍是本机原型，不具备公网多用户鉴权。当前V0.2.1访问令牌需操作者配置，生产身份/角色体系未提供。
5. 演化实验仅独立登记pending，未实现生产实验观察导入、策略发布、Skill安装或认证；Mock不能跨入这些状态。
6. 后台保存并提供显示动作不证明学生已阅读，资料加载不证明实际采用或掌握。
