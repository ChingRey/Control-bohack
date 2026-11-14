import copy,json,time,unittest
from unittest.mock import patch
from agents import model_limits,teaching
import backend as b
import test_checkpoints as fixture


class TimeoutSettingsTests(unittest.TestCase):
 def setUp(self):
  before=model_limits.settings();self.addCleanup(model_limits.configure,before)

 def test_invalid_values_do_not_partially_apply(self):
  before=model_limits.settings()
  for bad in ({**before,'teacher_request_seconds':0},{**before,'teacher_request_seconds':True},
              {**before,'teacher_total_seconds':5},{'other':60}):
   with self.assertRaises(ValueError):model_limits.configure(bad)
   self.assertEqual(model_limits.settings(),before)

 def test_budget_honors_separate_request_and_total_limits(self):
  model_limits.configure({'teacher_request_seconds':15,'teacher_total_seconds':30,'background_request_seconds':45,'background_total_seconds':90})
  front=model_limits.budget('teacher');back=model_limits.budget('background')
  self.assertEqual(front['request_timeout'],15);self.assertEqual(back['request_timeout'],45)
  self.assertLessEqual(front['deadline']-time.monotonic(),30);self.assertLessEqual(back['deadline']-time.monotonic(),90)

 def test_transport_timeout_is_forwarded_and_traced_without_secrets(self):
  budget={'attempts':0,'deadline':time.monotonic()+20,'request_timeout':7};events=[];budget['on_attempt']=events.append
  with patch.object(teaching,'urlopen',side_effect=TimeoutError()) as network:
   with self.assertRaises(TimeoutError):teaching.request_model(None,budget,lambda *args:None)
  self.assertEqual(network.call_args.kwargs['timeout'],7);self.assertEqual(events[-1]['error_type'],'TimeoutError')
  self.assertEqual(events[-1]['status'],'failed');self.assertEqual(len(events),2)

 def test_settings_api_persists_nonsecret_values(self):
  h=fixture.CheckpointIntegrationTests();h.setUp();self.addCleanup(h.doCleanups)
  settings={'teacher_request_seconds':20,'teacher_total_seconds':40,'background_request_seconds':30,'background_total_seconds':90}
  code,value=h.call('/api/settings/timeouts',settings);self.assertEqual(code,200);self.assertEqual(value,settings)
  self.assertEqual(json.loads((b.DATA/'model-timeouts.json').read_text()),settings)
  health=h.call('/api/health')[1];self.assertEqual(health['model_timeouts'],settings)
  self.assertEqual(health['background_revision'],'snapshot-v2')
