"""Real Chromium checks on an isolated static project copy and private browser profile."""
import functools
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from . import project_files, project_runner, project_safety

ROOT=Path(__file__).resolve().parents[1]
def binary():
 for p in [os.environ.get('CONTROL_BROWSER',''),r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',r'C:/Program Files/Google/Chrome/Application/chrome.exe',shutil.which('chromium'),shutil.which('google-chrome')]:
  if p and Path(p).is_file():return str(p)
 return None
def validate(cases):
 if not isinstance(cases,list) or not 1<=len(cases)<=50:raise ValueError('请提供1至50个浏览器步骤')
 if not any(isinstance(s,dict) and str(s.get('action','')).startswith('assert_') for s in cases):raise ValueError('至少需要一个明确断言；页面加载或点击本身不算行为通过')
 actions={'click','fill','assert_count','assert_text','assert_exists','assert_absent','assert_value','reload','wait'}
 for s in cases:
  if not isinstance(s,dict) or s.get('action') not in actions:raise ValueError('浏览器操作无效')
  if s['action'] not in ('reload','wait') and (not isinstance(s.get('selector'),str) or not 1<=len(s['selector'])<=500):raise ValueError('请填写CSS选择器')
  if s['action']=='assert_count' and (type(s.get('count')) is not int or not 0<=s['count']<=100000):raise ValueError('数量断言无效')
  if s['action'] in ('fill','assert_value') and (not isinstance(s.get('value'),str) or len(s['value'])>4000):raise ValueError('输入值无效')
  if s['action']=='assert_text' and (not isinstance(s.get('text'),str) or len(s['text'])>4000):raise ValueError('文本断言无效')
  if s['action']=='wait' and (type(s.get('ms',200)) is not int or not 0<=s.get('ms',200)<=3000):raise ValueError('等待时间无效')
 return cases
def run(files,assets,cases,path='index.html',screenshot=None,handler=None,accept_dialogs=False):
 validate(cases);exe=binary();node=shutil.which('node')
 if not exe or not node:raise ValueError('需要本机Chrome/Edge和Node 22+；未执行浏览器验证')
 if not project_files.allowed(path):raise ValueError('页面路径无效')
 class Quiet(http.server.SimpleHTTPRequestHandler):
  def log_message(self,*a):pass
 with tempfile.TemporaryDirectory(prefix='control-browser-project-') as folder,tempfile.TemporaryDirectory(prefix='control-browser-profile-',ignore_cleanup_errors=True) as profile:
  root=Path(folder)
  for name,value in files.items():
   p=project_files.target(root,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value.encode('utf-8'))
  for name,value in assets.items():
   p=project_files.target(root,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(project_files.decode(value))
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler or functools.partial(Quiet,directory=folder))
  threading.Thread(target=server.serve_forever,daemon=True).start();proc=None
  try:
   browser_env=project_runner.clean_env(profile)
   for name in ('USERPROFILE','APPDATA','LOCALAPPDATA','PROGRAMDATA','PROGRAMFILES','PROGRAMFILES(X86)','COMMONPROGRAMFILES','USERNAME','USERDOMAIN'):
    if name in os.environ:browser_env[name]=os.environ[name]
   proc=subprocess.Popen([exe,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=browser_env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   marker=Path(profile)/'DevToolsActivePort'
   for _ in range(150):
    if marker.exists() and marker.stat().st_size:break
    if proc.poll() is not None:raise ValueError('浏览器启动失败')
    time.sleep(.1)
   if not marker.exists():raise ValueError('浏览器调试端口未就绪')
   port=int(marker.read_text().splitlines()[0]);packet={'debug':f'http://127.0.0.1:{port}','url':f'http://127.0.0.1:{server.server_port}/','path':path,'cases':cases,'acceptDialogs':accept_dialogs,'screenshot':str(screenshot) if screenshot else None}
   result=subprocess.run([node,str(ROOT/'scripts/browser_cases.cjs')],input=json.dumps(packet).encode(),capture_output=True,timeout=120,env=project_runner.clean_env(profile),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if result.returncode:raise ValueError('浏览器未完成：'+project_safety.redact(result.stderr.decode(errors='replace'))[:400])
   return json.loads(project_safety.redact(result.stdout.decode('utf-8')))
  finally:
   server.shutdown();server.server_close()
   if proc is not None:
    if proc.poll() is None:proc.terminate()
    try:proc.wait(timeout=8)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
