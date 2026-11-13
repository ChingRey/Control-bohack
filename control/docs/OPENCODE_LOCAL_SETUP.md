# OpenCode 本机配置与首次验证

本项目使用 OpenCode CLI 调用 DashScope 的 OpenAI 兼容接口。Windows 首次运行前，在 Control 根目录打开 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
$env:HTTPS_PROXY = 'http://127.0.0.1:7897'
$env:HTTP_PROXY = $env:HTTPS_PROXY
.\scripts\install_opencode.ps1
```

若 npm registry 可直连，可以不设置前两行。代理只在当前 PowerShell 进程有效。

脚本按 `tools/opencode-next/package-lock.json` 执行 `npm ci`，检查 Node.js 20+，并运行 OpenCode 版本检查。`node_modules` 不提交到 Git；每台运行 Control 的电脑都要安装一次。若 npm 下载失败，检查当前终端是否能访问 npm registry，再重跑脚本。

然后启动后端：

```powershell
$env:CONTROL_CODING_HTTPS_PROXY = 'http://127.0.0.1:7897'
python -X utf8 backend.py --port 8772
```

如果 DashScope 可直连，省略第一行即可。设置该变量后，后端只把这个明确指定的 HTTP(S) 代理传给 OpenCode 子进程；不会继承系统中其他代理变量。不要在 URL 中放代理用户名或密码。

打开 `http://127.0.0.1:8772`，按顺序操作：

1. 选择「配置 Coding 模型」。区域按 API Key 的归属选择：中国区选「中国内地」，国际站 Key 选「国际」。
2. 模型 ID 填 `qwen3.6-plus`，在本机弹窗中粘贴 DashScope API Key 并连接。不要把 Key 写入命令、文件或聊天。
3. 点击「新建 OpenCode 项目」。只有这个项目模式会调用 OpenCode；普通示例项目仍使用 Sample。
4. 发一条清楚的需求，等待后台 Coding 运行完成。可在右侧流程信息中查看模型、OpenCode 安装状态和本轮状态。
5. 查看生成的计划，修改后明确确认；执行阶段每次只运行一个步骤。接口调用失败时查看 Coding 对话中的错误，确认其未提交文件后再修正配置重试。

Coding API Key 只保存在当前后端进程内存中，重启后需重新填写。OpenCode 在临时隔离目录中运行，不继承用户 OpenCode 配置、其他代理变量或其他 API 密钥。应用不会用 Sample 回复掩盖 OpenCode 调用失败。

## 常见问题

- **显示 OpenCode 未安装**：确认安装脚本成功，并且在启动 `backend.py` 的同一份项目目录执行。停止后端再重新启动。
- **模型已配置但还是固定示例回复**：确认当前项目是通过「新建 OpenCode 项目」创建的，并看顶部状态是否显示 OpenCode。
- **401 / invalid_api_key**：检查 Key 所属站点与区域；中国区和国际站的 Key/Endpoint 不能混用。
- **模型不存在或无权限**：确认账号的 Model Studio 服务已开通、Key 可调用 `qwen3.6-plus`，并核对模型 ID 大小写和拼写。
- **连接超时**：检查当前运行机对所选 DashScope 区域的网络连接；需要代理时，在启动后端的 PowerShell 会话设置 `CONTROL_CODING_HTTPS_PROXY`。

本地安装和页面状态只能证明 CLI 可启动、设置已接收；只有实际完成一次 Qwen 请求才能证明账号、区域和模型调用正常。
