# Control：边开发，边理解自己的项目

Control 是一个本地运行的 AI 编程学习工作台。你向 Coding Agent 描述想做的作品、讨论计划并推进开发；Teaching Agent 结合项目代码与两侧对话，帮助你理解实现、检查思路和设计验证。它把项目、代码、交流和学习记录放在同一个空间里，方便下次继续。

这是一个可运行的教学原型。AI 生成的代码和解释需要检查；教学经验的积累不等于已经证明学习效果提升。

## 里面有什么

| 模块 | 可以做什么 |
|---|---|
| 项目首页 | 新建并命名项目，搜索历史，继续学习、重命名、查看教学记录 |
| Coding 聊天窗 | 讨论需求与计划、确认后推进开发；聊天框可以拖动、缩放，新建项目恢复默认位置 |
| 工作区与代码区 | 查看文件、编辑并保存代码、查看改动、运行网页预览 |
| Teaching 学习区 | 结合当前代码与讨论解释问题、审查方案、帮助设计验证；不直接改写项目代码 |
| 经验库 | 在当前演示身份的不同项目间积累教法，查看来源仓库、变更、评分证据及撤销记录 |

## 第一次启动

目前主要面向 Windows x64。准备 Python 3.10+、Node.js 20+（含 npm）。下载或克隆仓库后，在 `control` 目录打开 PowerShell：

```powershell
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts/install_opencode.ps1
```

OpenCode 依赖需要每台电脑安装一次，不随 Git 仓库附带 `node_modules`。下载失败时检查网络后重试。

然后双击 `配置模型.cmd`，填写两侧模型配置；再双击 `启动工作台.cmd`。也可以用命令行启动：

```powershell
python -X utf8 backend.py --port 8772
```

浏览器打开 [http://127.0.0.1:8772](http://127.0.0.1:8772)。不要重复启动同一个端口；端口占用时先确认旧服务，或用 `--port` 另选端口。

## API 配置：改哪个文件

**实际配置文件是 `control/data/workbench/host-models.json`（相对于仓库根目录）。** 如果已经在 `control` 目录内，对应路径就是 `data/workbench/host-models.json`。首次使用时文件可能不存在；运行配置窗口会创建它。

推荐双击 `control/配置模型.cmd` 填写。也可在 `control` 目录运行：

```powershell
python -X utf8 scripts/configure_host_models.py
```

需要手动编辑时，按下面的结构创建 JSON，替换占位内容；示例也保存在 [配置模板](docs/host-models.example.json)。不要直接使用占位 Key。

```json
{
  "teaching": {
    "provider": "siliconflow",
    "model": "zai-org/GLM-5.3-Flash",
    "api_key": "YOUR_TEACHING_API_KEY"
  },
  "coding": {
    "provider": "siliconflow",
    "model": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    "api_key": "YOUR_CODING_API_KEY",
    "region": "cn"
  }
}
```

- Teaching 支持 `siliconflow`、`deepseek`、`openai`；Coding 支持 `siliconflow`、`bailian`。模型名称填该服务商账户实际可调用的完整模型 ID，示例不保证你的账户有权限。
- 两侧分别配置；同一服务商可按账户权限使用同一个 Key。服务地址由程序按服务商固定，不需要修改 Python 源码或填写自定义 API 地址。
- Coding 使用百炼时，`region` 填 `cn` 或 `intl`，与 Key 所属站点一致；硅基流动保持 `cn`。
- 配置由主机负责人统一管理，学生网页不提供模型修改接口。保存后启动服务或发下一条聊天时读取；保存成功不等于连接成功，请实际发消息确认。
- 文件在本机保存明文 Key，请只留在自己的电脑。`data/` 已被 Git 忽略，不能上传到 GitHub、发到聊天或交接压缩包。仓库仅提供无密钥模板。

## 怎么操作

1. 在首页上方点“开启新项目”，可填写仓库名，也可留空使用“未命名仓库一、二……”自动编号。之后可重命名。
2. 在 Coding 聊天中说明目标、需要的功能和你期望的效果。先讨论需求与计划，再通过界面明确确认执行；普通讨论不会自动批准计划。
3. 执行过程中等待状态更新，完成后查看代码和改动；网页项目可打开运行预览，实际试用功能。不要只因 AI 说“完成”就认为已经验收。
4. 在 Teaching 区提出具体问题，例如“为什么这样拆分”“这个边界怎么验证”。它能结合项目材料回答，也会保存学习记录。
5. 返回首页后，从历史项目继续学习。“···”菜单可以重命名和查看教学记录；最近打开的项目排在前面。
6. 点“经验库”查看跨项目教法。卡片默认折叠，来源显示加入/修改的仓库；展开可看策略、证据和变更记录。

## 使用注意事项

- 手动编辑代码后先保存，再切换项目或发起执行，避免未保存内容丢失。
- 运行中的项目不要直接删文件、清空数据或强制重启服务；重启不会自动接着执行中断的任务。
- 项目与历史保存在 `control/data/`，其中任务库为 `data/workbench/records.sqlite3`。备份前先停止服务，再备份整个 `data` 目录；不要只拷贝源码当成数据备份，也不要覆盖别人的数据。
- AI 调用可能计费、超时或失败。检查 Key、模型权限与网络后再重试；不要把错误回复当成已完成改动，也不要重复点击制造多次请求。
- Coding 可修改项目内文件，但并未开放任意系统命令和外部联网，Teaching 保持只读；不要期待它自动安装所有依赖或完成任何类型程序的运行部署。
- 经验评分、加载记录和模型观察都不是教学收益的证明；预览加载成功也不代表完整功能测试通过。
- 当前使用共享演示身份，没有正式的多用户登录隔离。默认只在本机访问，适合个人使用和受控演示；不要直接当作公网多人平台部署。

## 开发与验证

在 `control` 目录执行：

```powershell
node --check frontend/app.js
python -m unittest discover -s tests -p "test_*.py"
python -X utf8 scripts/verify_homepage.py
```

首页专项脚本使用临时数据库、真实 Chromium 和模拟模型，不写真实学生历史，也不证明真实模型质量。需要本机 Chrome/Edge 和支持原生 WebSocket 的 Node.js 22+。

进一步开发先读 [AGENTS.md](AGENTS.md)。接口见 [API.md](docs/API.md)，共享经验机制见 [SHARED_EXPERIENCE_LIBRARY.md](docs/SHARED_EXPERIENCE_LIBRARY.md)。旧开发记录见 [README_HISTORY.md](docs/README_HISTORY.md)，与本页冲突时以当前源码和本页为准。
