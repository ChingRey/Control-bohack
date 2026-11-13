# 本轮稳定性补丁

2026-11-13：8774原先无监听服务，已启动并验证首页、JS和health返回200。新增统一中断恢复函数，修复仅Coding运行中状态未写回的问题；前端显示Coding运行/失败，配置状态不再始终显示未连接。61项测试通过，JS语法通过；未进行浏览器视觉验证或真实API调用。

借鉴项目：remotty（https://github.com/mirkomaselli/remotty）将OpenCode工具事件展示为卡片和权限请求；opencode-webui（https://github.com/cinagroup/opencode-webui）明确项目与会话关联；opencode-container（https://github.com/tbrandenburg/opencode-container）区分一次性run与长期serve生命周期。此次采用生命周期失败恢复与事件呈现原则，没有复制未经验证的项目代码。保持当前每阶段一次run，不切换serve，不引入Docker。

真实试用：刷新8774，新建OpenCode项目，连接Coding模型，填写百炼按量API地区/模型ID/Key。需求写入Coding输入框，点击由Coding生成计划。成功后确认计划，再执行一个阶段，核对真实diff与预览。当前仅三个静态网页文件；无shell、依赖安装或自动行为测试。Key只在本机前端专用输入框填写，不发聊天。API失败保留阶段，不能把配置已保存当成调用成功。
