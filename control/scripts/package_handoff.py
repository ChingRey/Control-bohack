"""Package current source plus Windows executor, excluding private runtime data."""
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
target = Path(sys.argv[1]).resolve()
files = []
for directory in ('agents', 'frontend', 'docs', 'scripts', 'tests'):
    files.extend(p for p in (root / directory).rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo'))
files.extend(root / p for p in ('backend.py', 'AGENTS.md', '.gitignore', '启动工作台.cmd'))
tool = root / 'tools/opencode-next'
files.extend(tool.glob('package*.json'))
exe = tool / 'node_modules/opencode-windows-x64/bin/opencode.exe'
if not exe.is_file():
    raise SystemExit('Missing verified Windows executor')
files.append(exe)
package = exe.parents[1]
files.extend(p for p in package.glob('*') if p.is_file())
files = sorted(set(files))
for path in files:
    if path.suffix.lower() in ('.py', '.js', '.html', '.md', '.json', '.txt', '.cmd'):
        if re.search(rb'\bsk-[A-Za-z0-9_-]{24,}', path.read_bytes()):
            raise SystemExit('Possible credential: ' + str(path.relative_to(root)))

readme = '''# Control 双智能体交接版（2026-11-14）

Windows 本地运行；附当前源代码和 OpenCode 1.18.34 Windows x64 执行器。
此包不含 API Key、聊天记录、学生项目、SQLite 数据库或本机运行缓存。

## 启动
1. 完整解压到可写目录，不要在压缩包内直接运行。
2. 安装 Python 3.10+，双击“启动工作台.cmd”。常规启动无需 pip/npm。
3. 打开 http://127.0.0.1:8772/ 。也可运行 python -X utf8 backend.py --port 8782，打开对应端口。
4. 在页面分别保存 Coding 和 Teaching 配置：
   - Coding：服务商“硅基流动”，模型 Qwen/Qwen3-Coder-30B-A3B-Instruct。
   - Teaching：服务商“硅基流动”，模型 zai-org/GLM-5.3。
   - 使用自己账户有权限的 API Key；两处可填同一个有对应权限的 Key。
5. Key 仅保存在后台内存，后台重启后需要重填。模型调用需要联网。

## main教学升级融合
- 已融合origin/main@1e6b124：21张教学课卡、31条参考来源、需求/设计材料、功能循环、验证/恢复/交付及聊天队列。
- 同时保留本地精简输入、接续记忆和计划阶段验收；说明见docs/MERGE_TEACHING_MAIN.md。

## 已接通
- 学生聊天生成计划草稿，聊天内 ✓ 批准 / ✕ 修改；执行后暂停等待检查。
- 回复附后端生成的计划项原名和“待检查”状态；不会把本轮结束当成整份计划完成。
- 项目目录内读写文件；需求分析阶段限制提前写实现代码。
- Teacher 可读两边聊天、计划、源码与检查点，不能改代码。
- Teacher 区分当前阶段和后续任务，不应把后续未实现功能当成当前遗漏。
- Teacher 输入已去重：默认只读本轮变更附近代码，普通聊天不附整份审查；新增带消息来源和代码版本的接续记忆，同轮生成、不额外请求摘要。完整历史与只读补查保留。
- 每阶段暂停后，Coding聊天内显示 ✓ 本阶段通过，继续下一阶段 / ✕ 需要修改；最后一阶段显示完成开发。旧文字指令仍兼容。
- 知识候选整理和 evolve() 保留接口与 Mock；没有真实教学策略自动进化，Coding Skill 未启用。

## 验证和限制
187项测试：186通过，1项可选浏览器测试跳过；独立真实浏览器验收通过。真实硅基流动测试已验证：计数器阶段写文件、7→8→9、未提前加入 reset；Teacher 引用计划/代码并保持只读。
模型规划与表述仍不稳定；首次计划可能未被同步器识别。普通编码阶段的语义范围主要依赖提示约束，不能保证任何任务都不越界。
较早 docs 中有历史示例说明，以当前代码及本说明为准。测试脚本里的 8782 是开发测试端口，不影响默认8772启动。
接口文档：docs/CHECKPOINT_HANDOFF.md、docs/POST_TEACHING_KNOWLEDGE.md、docs/FRAMEWORK_INTEGRATION.md。

## 开发验证
python -m unittest discover -s tests
可选 Node.js：node --check frontend/app.js

OpenCode 官方项目：https://github.com/anomalyco/opencode （执行器随附，不含其完整node_modules缓存）。
'''
manifest = {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
target.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
    for path in files:
        archive.write(path, 'Control/' + str(path.relative_to(root)).replace('\\', '/'))
    archive.writestr('Control/README.md', readme)
    archive.writestr('Control/交接说明.txt', readme)
    archive.writestr('Control/PACKAGE_SHA256.json', json.dumps(manifest, ensure_ascii=False, indent=2))
with ZipFile(target) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit('Corrupt archive member: ' + bad)
    assert not any('/data/' in p or '/.git/' in p or '/__pycache__/' in p for p in archive.namelist())
print(json.dumps({'path': str(target), 'size_mb': round(target.stat().st_size/1024**2, 1), 'files': len(files)+3}, ensure_ascii=False))
