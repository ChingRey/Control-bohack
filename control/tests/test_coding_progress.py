"""Exercise the real pipe reader with isolated Python child processes."""
import json
import subprocess
import sys
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from agents import opencode_executor as executor

class CodingProgressTests(unittest.TestCase):
 def test_tool_progress_arrives_before_child_finishes_and_contains_no_raw_content(self):
  updates=[]
  event={'type':'tool_use','part':{'type':'tool','tool':'edit','callID':'call-1','state':{'status':'completed','input':{'secret':'never-publish-this'}}}}
  child="import json,time; print("+repr(json.dumps(event))+",flush=True); time.sleep(.4); print(json.dumps({'type':'step_finish','part':{'reason':'stop'}}),flush=True)"
  started=time.monotonic()
  result=executor.run_process([sys.executable,'-u','-c',child],timeout=5,text=True,encoding='utf8',progress=lambda row:updates.append((time.monotonic(),row)))
  tool=next((at,row) for at,row in updates if row['stage']=='tool')
  self.assertLess(tool[0],time.monotonic()-.2)
  self.assertEqual(tool[1]['completed_tools'],1)
  self.assertEqual(result.returncode,0)
  self.assertNotIn('never-publish-this',json.dumps(updates))
  self.assertEqual(updates[-1][1]['model_rounds'],1)
 def test_both_pipes_are_drained_without_deadlock(self):
  child="import sys; sys.stderr.write('x'*100000); sys.stderr.flush(); print('not-json',flush=True)"
  result=executor.run_process([sys.executable,'-u','-c',child],timeout=5,text=True,encoding='utf8',progress=lambda row:None)
  self.assertEqual(len(result.stderr),100000)
  self.assertIn('not-json',result.stdout)
 def test_timeout_terminates_child_promptly(self):
  started=time.monotonic()
  with self.assertRaises(subprocess.TimeoutExpired):
   executor.run_process([sys.executable,'-u','-c','import time; time.sleep(10)'],timeout=.15,text=True,encoding='utf8',progress=lambda row:None)
  self.assertLess(time.monotonic()-started,3)
 def test_observer_is_scoped_and_reset_after_failure(self):
  self.assertIsNone(executor._PROGRESS.get())
  callback=lambda row:None
  with self.assertRaises(RuntimeError):
   with executor.observe_progress(callback):
    self.assertIs(executor._PROGRESS.get(),callback)
    raise RuntimeError('fixture')
  self.assertIsNone(executor._PROGRESS.get())

 def test_search_executable_is_seeded_into_opencode_expected_cache(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'source-rg';source.write_bytes(b'fixture executable')
   with patch.object(executor,'ROOT',root/'no-bundled-tools'),patch.object(executor.shutil,'which',return_value=str(source)):
    self.assertTrue(executor.seed_search_tool(root/'isolated'))
   target=root/'isolated'/'XDG_CACHE_HOME'/'opencode'/'bin'/('rg.exe' if executor.os.name=='nt' else 'rg')
   self.assertEqual(target.read_bytes(),source.read_bytes())
 def test_missing_search_executable_keeps_existing_fallback_available(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(executor,'ROOT',Path(folder)),patch.object(executor.shutil,'which',return_value=None):
   self.assertFalse(executor.seed_search_tool(Path(folder)/'isolated'))

 def test_bundled_search_tool_works_without_rg_on_startup_path(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);binary=root/'tools'/'ripgrep'/('rg.exe' if executor.os.name=='nt' else 'rg')
   binary.parent.mkdir(parents=True);binary.write_bytes(b'project-local search fixture')
   with patch.object(executor,'ROOT',root),patch.object(executor.shutil,'which',return_value=None):
    self.assertTrue(executor.seed_search_tool(root/'isolated'))
   target=root/'isolated'/'XDG_CACHE_HOME'/'opencode'/'bin'/binary.name
   self.assertEqual(target.read_bytes(),binary.read_bytes())
