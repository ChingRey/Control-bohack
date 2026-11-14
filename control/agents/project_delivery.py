"""Portable project delivery; secrets blocked, actual execution evidence distinguished."""
import io
import json
import zipfile
from . import project_safety, project_files, workflow

EXCLUDED={'.git','node_modules','__pycache__','.venv','venv','.cache'}
def included(path):
 parts=path.replace('\\','/').split('/')
 return not any(p in EXCLUDED for p in parts) and not any(p=='.env' or p.startswith('.env.') and p!='.env.example' for p in parts) and not path.endswith(('.pyc','.pyo'))
def report(task,files,assets,student):
 if not isinstance(student,dict) or any(not isinstance(student.get(k),str) or not student[k].strip() or len(student[k])>4000 for k in ('how_to_run','tested','limitations')):raise ValueError('请填写如何运行、实际测试和已知限制')
 source={n:v for n,v in files.items() if included(n)}
 safety=project_safety.scan(source)
 if safety['publication_blocked']:raise ValueError('交付源码包含疑似凭据，请先处理安全检查中的文件和行号；不会输出凭据内容')
 return {'project_id':task['id'],'hash':workflow.digest(files,assets),'student_statement':student,'safety':safety,'behavior_records':task.get('behavior_records',[]),'browser_records':task.get('browser_records',[]),'execution_records':task.get('execution_records',[]),'rules':workflow.state(task).get('rules',[]),'notice':'学生自报、静态信号、工具执行和浏览器结果分别记录；结项不证明所有功能正确。'}
def build(task,files,assets,student):
 evidence=report(task,files,assets,student)
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for name,value in files.items():
   if included(name):z.writestr('project/'+name,value)
  for name,value in assets.items():
   if included(name):z.writestr('project/'+name,project_files.decode(value))
  z.writestr('HANDOFF.md','# 项目交接\n\n## 如何运行\n'+student['how_to_run']+'\n\n## 学生实际测试说明\n'+student['tested']+'\n\n## 已知限制\n'+student['limitations']+'\n\n代码版本：'+evidence['hash']+'\n\n依赖和密钥需在部署环境另行配置。静态网页可直接由静态服务器托管；包含后端的项目需按照运行说明部署对应进程。\n')
  if 'README.md' not in files:
   z.writestr('project/README.md','# '+task.get('title','Project')+'\n\n'+project_safety.redact(student['how_to_run'])+'\n\nSee ../HANDOFF.md for test observations and known limitations.\n')
  z.writestr('run-static.py','from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler\nfrom functools import partial\nfrom pathlib import Path\nserver=ThreadingHTTPServer(("127.0.0.1",8080),partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).parent/"project")))\nprint("http://127.0.0.1:8080")\nserver.serve_forever()\n')
  z.writestr('evidence.json',project_safety.redact(json.dumps(evidence,ensure_ascii=False,indent=2)))
 return out.getvalue(),evidence
