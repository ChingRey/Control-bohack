import json, subprocess, unittest
from unittest.mock import patch
from agents import opencode_executor as e

class ExecutorTests(unittest.TestCase):
 def tearDown(self):e.CONFIG=None
 def test_config_secret_not_in_metadata(self):
  e.configure('test-secret','model','cn')
  self.assertNotIn('test-secret',json.dumps(e.metadata()))
 def test_isolated_execution(self):
  e.configure('test-secret','model','cn')
  def run(cmd,**kw):
   self.assertNotIn('test-secret',' '.join(cmd))
   self.assertEqual(kw['env']['CONTROL_CODING_KEY'],'test-secret')
   self.assertNotIn('OPENAI_API_KEY',kw['env'])
   self.assertEqual(json.loads(kw['env']['OPENCODE_CONFIG_CONTENT'])['permission']['*'],'deny')
   from pathlib import Path
   (Path(kw['cwd'])/'app.js').write_text('changed',encoding='utf-8')
   return subprocess.CompletedProcess(cmd,0,json.dumps({'type':'text','part':{'text':'done'}}),'')
  with patch.object(e,'binary',return_value='opencode'),patch.object(e.subprocess,'run',side_effect=run):
   result=e.execute({'app.js':'before'},{})
  self.assertEqual(result['files']['app.js'],'changed')
 def test_failed_process_rejected(self):
  e.configure('test-secret','model','cn')
  with patch.object(e,'binary',return_value='opencode'),patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','')):
   with self.assertRaises(ValueError):e.execute({'app.js':'before'}, {})
