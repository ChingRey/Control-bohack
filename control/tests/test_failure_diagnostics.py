import copy,io,os,time,unittest
from unittest.mock import patch
from urllib.error import HTTPError,URLError
from agents import teaching,opencode_executor as executor,coding_workflow

class FailureDiagnosticsTests(unittest.TestCase):
 def test_noop_edit_is_not_denied_write_but_real_failure_still_fails(self):
  event={'part':{'tool':'edit','state':{'status':'error','input':{'oldString':'a','newString':'a'},'error':'No changes to apply: oldString and newString are identical.'}}}
  self.assertEqual(executor.failed_file_tools([event]),[])
  real=copy.deepcopy(event);real['part']['state']['error']='Permission denied'
  self.assertEqual(executor.failed_file_tools([real]),[real])
 def test_direct_file_execution_has_no_plan_index_crash(self):
  t={'step':0};coding_workflow.mark_executed(t);self.assertEqual(t['coding_workflow']['checkpoints'],[])
 def test_teacher_timeout_configuration_and_error_categories(self):
  class Agent:
   mode='model';config={};request_budget={'attempts':0,'deadline':0};history=[];project_source={}
  for error,expected in [(TimeoutError(),'超时'),(HTTPError('https://invalid',401,'denied',{},io.BytesIO()),'HTTP 401'),(HTTPError('https://invalid',429,'limit',{},io.BytesIO()),'HTTP 429'),(URLError('no connection'),'网络连接失败')]:
   with self.subTest(expected=expected),patch.object(teaching.providers,'request',return_value=None),patch.object(teaching,'request_model',side_effect=error):
    with self.assertRaisesRegex(ValueError,expected):teaching.project_chat(Agent(),{},lambda *a:None)
  with patch.dict(os.environ,{'CONTROL_TEACHING_REQUEST_TIMEOUT_SECONDS':'90'}):self.assertEqual(teaching.network_timeout(),90)
  with patch.dict(os.environ,{'CONTROL_TEACHING_REQUEST_TIMEOUT_SECONDS':'0'}):
   with self.assertRaises(ValueError):teaching.network_timeout()
 def test_url_error_trace_records_only_sanitized_transport_classification(self):
  budget={'attempts':0,'deadline':time.monotonic()+10,'request_timeout':5};events=[];budget['on_attempt']=events.append
  error=URLError(OSError(10061,'connection refused'))
  with patch.object(teaching,'urlopen',side_effect=error):
   with self.assertRaises(URLError):teaching.request_model(None,budget,lambda *args:None)
  event=events[-1]
  self.assertEqual(event['network_stage'],'proxy_connect')
  self.assertEqual(event['network_error_type'],'ConnectionRefusedError')
  self.assertEqual(event['network_error_code'],10061)
  self.assertNotIn('error',event)
  self.assertNotIn('key',event)
