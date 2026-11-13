# 启动本分支

需要Python 3.10+、Node.js/npm及Windows x64。进入control目录执行：

```powershell
npm ci --prefix tools/opencode-next --ignore-scripts --registry=https://registry.npmjs.org
python -X utf8 backend.py --port 8774
```

打开 http://127.0.0.1:8774 ，点击新建OpenCode项目，在连接Coding模型中输入自己的百炼中国内地按量API Key及模型ID（已用于流程尝试：qwen3.6-plus）。密钥只保存在后端进程，重启需重填；新建项目不清除配置。不要发Key到聊天或提交到Git。

本分支仍是原型：普通聊天、项目内三个静态网页文件编辑、计划同步、分阶段审查入口。Teaching只读代码；经验有来源与启停，Skill尚未验证不可安装。没有证明Skill提升或长期教学效果。原始OpenCode版本/帮助命令启动检查通过，真实计划生成曾成功，完整开发与浏览器视觉验收尚未完成。

检查：python -m unittest discover -s tests -p "test_*.py" -q；node --check frontend/app.js。

本分支取消跟踪原仓库上传的SQLite与pyc，未改写旧提交历史。历史中已有运行数据，如涉及真实私人信息应单独评估处理。
