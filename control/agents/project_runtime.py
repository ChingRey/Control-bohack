"""Managed local Python/Node web processes, launched by explicit student action."""
import atexit
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from . import project_files, project_runner, project_safety, workflow

SESSIONS={}
def status(tid):
 row=SESSIONS.get(tid)
 if not row:return {'status':'stopped'}
 process=row['process'];code=process.poll()
 row['log'].flush()
 output=project_safety.redact(row['logpath'].read_text(encoding='utf-8',errors='replace'))[-6000:]
 return {'status':'running' if code is None else 'exited','exit_code':code,'url':row['url'],'hash':row['hash'],'output':output,'notice':'本机项目副本，未继承模型密钥；不是操作系统安全沙箱。'}
def stop(tid):
 row=SESSIONS.pop(tid,None)
 if not row:return
 p=row['process']
 if p.poll() is None:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
 row['log'].close();row['workspace'].cleanup();row['home'].cleanup()
def start(tid,files,assets,kind,entry):
 if kind not in ('python','node') or not project_files.allowed(entry) or entry not in files:raise ValueError('请选择当前项目的Python或Node入口文件')
 if kind=='python' and not entry.endswith('.py') or kind=='node' and not entry.endswith(('.js','.mjs','.cjs')):raise ValueError('入口扩展名与运行器不匹配')
 stop(tid)
 workspace=tempfile.TemporaryDirectory(prefix='control-runtime-',ignore_cleanup_errors=True);home=tempfile.TemporaryDirectory(prefix='control-runtime-env-',ignore_cleanup_errors=True)
 root=Path(workspace.name)
 try:
  for name,value in files.items():
   p=project_files.target(root,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value.encode('utf-8'))
  for name,value in assets.items():
   p=project_files.target(root,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(project_files.decode(value))
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  env=project_runner.clean_env(home.name);env.update(PORT=str(port),HOST='127.0.0.1',CONTROL_PROJECT_PORT=str(port))
  command=[sys.executable,'-u',entry] if kind=='python' else [shutil.which('node') or 'node',entry]
  logpath=Path(home.name)/'runtime.log';log=logpath.open('wb')
  process=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  SESSIONS[tid]={'process':process,'workspace':workspace,'home':home,'log':log,'logpath':logpath,'url':f'http://127.0.0.1:{port}/','hash':workflow.digest(files,assets)}
  for _ in range(50):
   if process.poll() is not None:break
   try:
    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
   except OSError:time.sleep(.1)
  return status(tid)
 except Exception:
  stop(tid);workspace.cleanup();home.cleanup();raise
@atexit.register
def close_all():
 for tid in list(SESSIONS):stop(tid)
