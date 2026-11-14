import copy
import json
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import backend as b
from agents import providers,teaching,opencode_executor as coding
from test_providers import Response
from test_teaching_library import task
import test_checkpoints as fixture

class SiliconFlowTests(unittest.TestCase):
 def test_own_endpoint_key_tools_and_json_with_no_cross_provider_options(self):
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'not-this-provider'},clear=True):
   providers.configure('siliconflow','fixture-silicon-key','zai-org/GLM-5.3')
   os.environ['TEACHING_ENDPOINT']='https://api.deepseek.com/chat/completions'
   config=providers.settings();self.assertEqual(config['key'],'fixture-silicon-key')
   self.assertEqual(config['endpoint'],'https://api.siliconflow.cn/v1/chat/completions')
   plain=providers.request(config,[{'role':'user','content':'Read project'}],2600,teaching.tools())
   body=json.loads(plain.data);self.assertIn('tools',body);self.assertNotIn('thinking',body);self.assertNotIn('response_format',body)
   structured=json.loads(providers.request(config,[],2600,json_mode=True).data)
   self.assertEqual(structured['response_format'],{'type':'json_object'})
   self.assertNotIn('fixture-silicon-key',json.dumps(providers.metadata(config,'model')))
 def test_missing_silicon_key_does_not_use_another_service_key(self):
  for environment in ({'TEACHING_PROVIDER':'siliconflow','DEEPSEEK_API_KEY':'wrong','OPENAI_API_KEY':'also-wrong','TEACHING_API_KEY':'generic-wrong'}, {'TEACHING_ENDPOINT':'https://api.siliconflow.cn/v1/chat/completions','TEACHING_API_KEY':'generic-wrong'}):
   with patch.dict(os.environ,environment,clear=True):
    config=providers.settings();self.assertEqual(config['provider'],'siliconflow');self.assertEqual(config['key'],'')
    with self.assertRaises(ValueError):providers.request(config,[],2600)
 def test_environment_only_siliconflow_configuration(self):
  with patch.dict(os.environ,{'SILICONFLOW_API_KEY':'fixture-silicon-key'},clear=True):
   agent=teaching.TeachingAgent();self.assertEqual(agent.mode,'model');self.assertEqual(agent.config['provider'],'siliconflow');self.assertEqual(agent.config['model'],'zai-org/GLM-5.3')
 def test_teaching_tool_loop_and_library_survive_siliconflow_wire_adapter(self):
  t=task('请解释刷新与localStorage是什么');before=copy.deepcopy(t['files'])
  replies=[Response({'choices':[{'message':{'role':'assistant','tool_calls':[{'id':'read-1','type':'function','function':{'name':'read_project_file','arguments':'{"path":"index.html","start_line":1,"limit":1}'}}]}}]}),Response({'choices':[{'message':{'role':'assistant','content':'需要区分页面内存和同一来源的localStorage。'}}]})]
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'siliconflow','SILICONFLOW_API_KEY':'fixture-silicon-key','TEACHING_MODEL':'zai-org/GLM-5.3'},clear=True),patch.object(teaching,'urlopen',side_effect=replies) as send:
   reply=teaching.run(t)
  self.assertIn('localStorage',reply);self.assertEqual(send.call_count,2)
  for call in send.call_args_list:self.assertEqual(call.args[0].full_url,'https://api.siliconflow.cn/v1/chat/completions')
  first=json.loads(send.call_args_list[0].args[0].data);ctx=json.loads(first['messages'][1]['content'])
  self.assertIn('L09',[c['id'] for c in ctx['teaching_library']['lessons']])
  last=json.loads(send.call_args_list[1].args[0].data);self.assertTrue(any(m.get('tool_call_id')=='read-1' for m in last['messages']))
  turn=t['teaching']['turns'][-1];self.assertEqual(turn['provider']['provider'],'siliconflow');self.assertEqual(turn['tools'][0]['name'],'read_project_file')
  self.assertTrue(turn['teaching_library']['submitted_to_model']);self.assertEqual(before,t['files']);self.assertNotIn('fixture-silicon-key',json.dumps(t))
 def test_summarizer_keeps_the_selected_provider_snapshot(self):
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'siliconflow','SILICONFLOW_API_KEY':'fixture-silicon-key','TEACHING_MODEL':'zai-org/GLM-5.3'},clear=True):
   agent=teaching.TeachingAgent();providers.configure('deepseek','fixture-different-key','deepseek-flash')
   agent.request_budget={'attempts':0,'deadline':time.monotonic()+20};agent.progress=lambda *args:None
   with patch.object(teaching,'urlopen',return_value=Response({'choices':[{'message':{'content':'{"summary":"保留原话，未认证掌握。"}'}}]})) as send:
    self.assertIn('保留原话',agent.summarize_memory([{'id':0,'content':'test'}]))
   self.assertEqual(send.call_args.args[0].full_url,'https://api.siliconflow.cn/v1/chat/completions')
 def test_coding_transport_has_independent_key_and_arbitrary_file_tools(self):
  with patch.object(coding,'CONFIG',None),patch.dict(os.environ,{'SILICONFLOW_API_KEY':'teaching-only-key'},clear=False),patch.object(coding,'binary',return_value='fixture-cli'):
   coding.configure('coding-only-key','Qwen/Qwen3-Coder-30B-A3B-Instruct',provider='siliconflow')
   def run(command,cwd,env,**kwargs):
    self.assertEqual(env['CONTROL_CODING_KEY'],'coding-only-key');self.assertNotIn('SILICONFLOW_API_KEY',env)
    config=json.loads(env['OPENCODE_CONFIG_CONTENT']);self.assertEqual(config['provider']['control']['options']['baseURL'],'https://api.siliconflow.cn/v1')
    self.assertEqual(config['permission']['write'],'allow');self.assertEqual(kwargs['timeout'],900)
    path=Path(cwd)/'src/new.custom';path.parent.mkdir();path.write_text('created',encoding='utf-8')
    return SimpleNamespace(returncode=0,stdout=json.dumps({'type':'text','part':{'text':'written'}}),stderr='')
   with patch.object(coding.subprocess,'run',side_effect=run):result=coding.execute({}, {})
   self.assertEqual(result['files']['src/new.custom'],'created')

class SiliconFlowAPITests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
 def test_role_specific_configuration_and_no_key_in_snapshot_or_database(self):
  with patch.dict(os.environ,{},clear=True):
   status,provider=self.h.call('/api/settings/teaching',{'provider':'siliconflow','api_key':'teaching-fixture-key'})
   self.assertEqual(status,200);self.assertEqual(provider['provider']['model'],'zai-org/GLM-5.3')
   status,meta=self.h.call('/api/settings/coding',{'provider':'siliconflow','api_key':'coding-fixture-key','model':'Qwen/Qwen3-Coder-30B-A3B-Instruct'})
   self.assertEqual(status,200);self.assertEqual(meta['provider'],'siliconflow')
   self.assertEqual(providers.settings()['key'],'teaching-fixture-key');self.assertEqual(coding.CONFIG['key'],'coding-fixture-key')
   status,snapshot=self.h.call(self.h.path);self.assertEqual(status,200);self.assertEqual(len(snapshot['teaching_library']['topics']),21)
   for key in ('teaching-fixture-key','coding-fixture-key'):
    self.assertNotIn(key,json.dumps(snapshot));self.assertNotIn(key.encode(),Path(b.DB).read_bytes())
 def test_configuration_rejects_invalid_values_without_partial_changes(self):
  with patch.dict(os.environ,{},clear=True):
   self.assertEqual(self.h.call('/api/settings/teaching',{'provider':'siliconflow','api_key':'invalid\nkey','model':'zai-org/GLM-5.3'})[0],400)
   self.assertNotIn('SILICONFLOW_API_KEY',os.environ);self.assertNotIn('TEACHING_PROVIDER',os.environ)
