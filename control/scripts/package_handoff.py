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
    files.extend(p for p in (root / directory).rglob('*') if p.is_file() and not p.is_symlink() and not p.name.startswith('.env')
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

readme = '''# Control 当前融合交付版（2026-11-14）

## 已融合
- main 合并提交 0e3aa9d，包含 Decide（37e441d）、教学子计划与 turn adapter、主线教学策略、经验反思和独立后台处理。
- 包含随后未提交的首页按钮修复：欢迎语不显示“这版可以”，后端未声明支持时不显示普通回复确认。
- 包含教师调用链精简、指定文件预读、共享材料去重、OpenAI自然语言模式修复、后台整理请求合并和耗时记录。
- Coding保留计划确认和阶段验收、项目内文件工具以及默认900秒执行预算；Teaching保持只读。

## 启动（Windows x64）
1. 完整解压到可写目录，安装 Python 3.10+。
2. 双击“启动工作台.cmd”，打开 http://127.0.0.1:8772/ 。
3. 或在本目录运行 python -X utf8 backend.py --port 8782，然后访问对应端口。
4. 附 OpenCode 1.18.34 Windows x64执行器，常规启动无需安装npm依赖。
5. 页面分别配置Coding和Teaching的服务商、模型与自己账户的API Key；模型请求需要联网。
6. Key只在后台进程内保存，重启后重填。请停止旧后端再启动本包，避免新前端连接旧接口。

## 接口与功能边界
- V0.2.1 decide()与teach()已接入；独立教学接口需要显式启用，不表示普通自然聊天每轮都调用decide。
- V0.2.1 evaluate()/evolve()仍为Mock联调；新的经验反思使用teaching/experience-review，不把Mock当真实效果。
- 模型超时可在设置页调整，默认前台60/120秒、后台60/180秒。
- 尚未验证真实学生的长期教学提升，教师回复仍整段显示。
- 说明见docs/TEACHING_V021_INTEGRATION.md、docs/MERGE_EVOLUTION_MAIN.md、docs/TEACHING_LATENCY.md。

## 验证与隐私
- main合并后完整回归247项，0失败、1项可选跳过；按钮修复后6项接口测试及3种显示条件检查通过。
- 未在本轮调用收费模型；不宣称真实模型速度提升比例。
- 不含API Key、学生项目、聊天数据库、.git、运行日志或缓存。
- PACKAGE_SHA256.json提供文件完整性校验。
'''

manifest = {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
manifest.update({name: hashlib.sha256(readme.encode('utf-8')).hexdigest() for name in ('README.md', '交接说明.txt')})
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
