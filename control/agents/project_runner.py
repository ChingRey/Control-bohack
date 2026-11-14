"""Explicit local test recipes; no shell interpolation or inherited provider secrets."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from . import project_files, project_safety

def clean_env(home):
 keep=('SYSTEMROOT','WINDIR','PATH','PATHEXT','COMSPEC','TEMP','TMP','LANG')
 env={k:v for k,v in os.environ.items() if k.upper() in keep}
 env.update(HOME=home,USERPROFILE=home,APPDATA=home,LOCALAPPDATA=home,PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
 return env
def run(files,assets,recipe):
 recipes={'python-unittest':[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],'node-test':[shutil.which('node') or 'node','--test']}
 if recipe not in recipes:raise ValueError('仅支持显式的python-unittest或node-test；静态项目使用浏览器验证')
 with tempfile.TemporaryDirectory(prefix='control-test-') as folder, tempfile.TemporaryDirectory(prefix='control-env-') as home:
  root=Path(folder)
  for name,value in files.items():
   p=project_files.target(root,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value.encode('utf-8'))
  for name,value in assets.items():
   p=project_files.target(root,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(project_files.decode(value))
  try:
   result=subprocess.run(recipes[recipe],cwd=root,env=clean_env(home),capture_output=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  except subprocess.TimeoutExpired:raise ValueError('本地测试超过120秒；不标记通过') from None
  output=(result.stdout+result.stderr).decode('utf-8',errors='replace')
  return {'recipe':recipe,'exit_code':result.returncode,'passed':result.returncode==0 and not re.search(r'Ran 0 tests|# tests 0\b',output),'output':project_safety.redact(output)[-12000:],'source':'executed_project_tests_not_mastery','notice':'在项目副本运行；不是操作系统安全沙箱，也不自动安装依赖。'}
