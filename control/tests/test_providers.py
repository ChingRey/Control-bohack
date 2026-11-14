import copy
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents import providers, teaching

class Response:
 def __init__(self,value):self.value=value
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self):return json.dumps(self.value).encode()

def response(text):
 return {'status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}],'usage':{'input_tokens':30,'output_tokens':10}}

class ProviderTests(unittest.TestCase):
 def fixture(self):
  from test_teaching import TeachingTests
  value=TeachingTests();value.setUp();return value
 def test_openai_payload_uses_responses_and_correct_key_only(self):
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'openai','TEACHING_MODEL':'gpt-5-test','OPENAI_API_KEY':'openai-test-key','DEEPSEEK_API_KEY':'wrong-provider-key'},clear=True):
   config=providers.settings();req=providers.request(config,[{'role':'system','content':'Return JSON'},{'role':'user','content':'test'}],2600,teaching.tools())
   data=json.loads(req.data)
   self.assertEqual(req.full_url,'https://api.openai.com/v1/responses')
   self.assertEqual(req.get_header('Authorization'),'Bearer openai-test-key')
   self.assertFalse(data['store']);self.assertIn('input',data);self.assertNotIn('messages',data)
   self.assertIn('max_output_tokens',data);self.assertNotIn('max_tokens',data)
   self.assertIn('name',data['tools'][0]);self.assertNotIn('function',data['tools'][0])
   self.assertNotIn('openai-test-key',json.dumps(providers.metadata(config,'model')))
 def test_openai_tool_loop_preserves_call_id_and_reasoning_items(self):
  f=self.fixture()
  output=[{'type':'reasoning','id':'rs_1','summary':[],'encrypted_content':'test-encrypted-reasoning'},
          {'type':'function_call','id':'fc_1','call_id':'call_1','name':'read_teaching_skill','arguments':'{"name":"diagnose"}'}]
  raw=[Response({'status':'completed','output':output}),Response(response(json.dumps(f.good)))]
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'openai','TEACHING_MODEL':'gpt-5-test','OPENAI_API_KEY':'test-openai-key'},clear=True),patch('agents.teaching.urlopen',side_effect=raw) as send:
   teaching.run(f.t)
   data=json.loads(send.call_args_list[1].args[0].data)
  self.assertIn(output[0],data['input']);self.assertIn(output[1],data['input'])
  result=next(x for x in data['input'] if x.get('type')=='function_call_output')
  self.assertEqual(result['call_id'],'call_1')
  self.assertIn('diagnose',result['output'])
  self.assertEqual(f.t['teaching']['turns'][-1]['provider']['provider'],'openai')
  self.assertNotIn('test-openai-key',json.dumps(f.t));self.assertNotIn('test-encrypted-reasoning',json.dumps(f.t))
 def test_openai_memory_summary_uses_same_provider(self):
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'openai','TEACHING_MODEL':'gpt-test','OPENAI_API_KEY':'test-key'},clear=True),patch('agents.teaching.urlopen',return_value=Response(response('{"summary":"保留原始依据，不认证掌握。"}'))) as send:
   agent=teaching.TeachingAgent();agent.request_budget={'attempts':0,'deadline':time.monotonic()+20};agent.progress=lambda *a:None
   self.assertEqual(agent.summarize_memory([{'id':0,'content':'test'}]),'保留原始依据，不认证掌握。')
   self.assertEqual(send.call_args.args[0].full_url,'https://api.openai.com/v1/responses')
 def test_provider_is_pinned_for_the_whole_agent_run(self):
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'openai','TEACHING_MODEL':'gpt-test','OPENAI_API_KEY':'test-key'},clear=True):
   agent=teaching.TeachingAgent()
   providers.configure('deepseek','different-key','deepseek-flash')
   self.assertEqual(agent.config['provider'],'openai');self.assertEqual(agent.config['key'],'test-key')
 def test_refusal_and_incomplete_are_errors_not_fake_success(self):
  config={'protocol':'responses'}
  with self.assertRaises(ValueError):providers.normalize(config,{'status':'incomplete','output':[]})
  with self.assertRaises(ValueError):providers.normalize(config,{'status':'completed','output':[{'type':'message','content':[{'type':'refusal','refusal':'test'}]}]})
 def test_missing_selected_provider_key_never_uses_the_other_key(self):
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'openai','TEACHING_MODEL':'gpt-test','DEEPSEEK_API_KEY':'wrong','TEACHING_API_KEY':'also-wrong'},clear=True):
   config=providers.settings();self.assertEqual(config['key'],'')
   with self.assertRaises(ValueError):providers.request(config,[],200)
 def test_invalid_configuration_does_not_partially_change_environment(self):
  with patch.dict(os.environ,{},clear=True):
   for args in [('other','key','model'),('openai','bad\nkey','model'),('openai','key',''),('openai','key',[])]:
    with self.assertRaises(ValueError):providers.configure(*args)
    self.assertNotIn('TEACHING_PROVIDER',os.environ)
 def test_openai_environment_key_activates_model_mode(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key','TEACHING_MODEL':'gpt-test'},clear=True):
   agent=teaching.TeachingAgent();self.assertEqual(agent.mode,'model');self.assertEqual(agent.metadata()['provider'],'openai')

 def test_configured_provider_cannot_route_key_to_other_service(self):
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'openai','TEACHING_MODEL':'gpt-test','OPENAI_API_KEY':'test-key','TEACHING_ENDPOINT':'https://api.deepseek.com/chat/completions'},clear=True):
   self.assertEqual(providers.settings()['endpoint'],'https://api.openai.com/v1/responses')

 def test_siliconflow_uses_own_key_fixed_endpoint_and_tools(self):
  with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'wrong-key'},clear=True):
   providers.configure('siliconflow','fixture-silicon-key','zai-org/GLM-5.3')
   os.environ['TEACHING_ENDPOINT']='https://api.deepseek.com/chat/completions'
   config=providers.settings()
   self.assertEqual(config['key'],'fixture-silicon-key')
   self.assertEqual(config['endpoint'],'https://api.siliconflow.cn/v1/chat/completions')
   req=providers.request(config,[{'role':'user','content':'read project'}],2600,teaching.tools(),json_mode=False)
   data=json.loads(req.data)
   self.assertEqual(data['model'],'zai-org/GLM-5.3');self.assertIn('tools',data)
   self.assertNotIn('thinking',data);self.assertNotIn('response_format',data)
   self.assertNotIn('fixture-silicon-key',json.dumps(providers.metadata(config,'model')))

 def test_siliconflow_does_not_fall_back_to_another_provider_key(self):
  with patch.dict(os.environ,{'TEACHING_PROVIDER':'siliconflow','DEEPSEEK_API_KEY':'wrong','TEACHING_API_KEY':'also-wrong'},clear=True):
   config=providers.settings();self.assertEqual(config['key'],'')
   with self.assertRaises(ValueError):providers.request(config,[],2600)

if __name__=='__main__':unittest.main()
