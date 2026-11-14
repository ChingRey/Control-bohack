import copy,io,json,os,time,unittest
from types import SimpleNamespace
from unittest.mock import patch
import backend as b
from agents import teaching_v021 as v, opencode_executor as executor
from agents.teaching_contract_v021 import mock_service, validator
import test_checkpoints as fixture

class V021IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
  self.env=patch.dict(os.environ,{'CONTROL_V021_ACCESS_TOKEN':'test-operator-token'});self.env.start();self.addCleanup(self.env.stop)
  task=b.load(self.h.task['id']);task['checkpoint_delivery']='manual';task['plan'].append('添加购物车');task['coding_workflow']['checkpoints'].append({'index':1,'title':'添加购物车','status':'pending'});b.save(task)
  with patch.object(executor,'execute',side_effect=self.h.execute):
   code,_=self.h.call(self.h.path+'/steps/run',{'confirmed':True,'expected_step':0,'instruction':'创建商品列表'})
   self.assertEqual(code,202);self.h.wait()
  # Finish background queue teardown before fixture cleanup.
  time.sleep(.03)
 def call(self,op,body=None,auth=True):
  handler=b.Handler.__new__(b.Handler);handler.path=self.h.path+'/teaching-v021'+('/'+op if op else '')
  handler.server=SimpleNamespace(server_port=8772)
  raw=json.dumps(body).encode() if body is not None else b''
  handler.headers={'Host':'127.0.0.1:8772','Content-Length':str(len(raw))}
  if auth:handler.headers['Authorization']='Bearer test-operator-token'
  handler.rfile=io.BytesIO(raw);result=[]
  handler.reply=lambda code,obj,*args:result.extend((code,copy.deepcopy(obj)))
  handler.do_GET() if body is None else handler.do_POST()
  return result
 def command(self,op,rid,**kw):
  code,receipt=self.call(op,{'request_id':rid,**kw});self.assertEqual(code,200,receipt);return receipt['response']
 def begin(self):
  self.command('configure','config')
  decision=self.command('decide','decision')
  self.assertEqual(decision['decision_id'],'decide-decision')
  self.assertEqual(decision['knowledge_point_ids'],['acceptance-criteria'])
  view=self.call('')[1]
  self.assertEqual(view['decision'],decision)
  frozen=view['contexts'][decision['context_id']]
  self.assertEqual(frozen['sources'][decision['evidence_refs'][0]]['plan'],b.load(self.h.task['id'])['plan'])
  return self.command('teach','turn0')
 def test_all_four_history_and_authorized_strategy_switch(self):
  initial=self.begin();self.assertEqual(initial['strategy_selection_mode'],'initial')
  self.command('respond','reply0',message='我会检查商品列表是否显示并验证空列表边界。')
  self.command('evaluate','eval0',assessment_mode='formative')
  follow=self.command('teach','turn1');self.assertEqual(follow['strategy_selection_mode'],'continued')
  req=self.call('')[1]['requests']['turn1']['contract_request']
  self.assertIn('空列表',req['teaching_history']['recent_turns'][0]['student_reply']['content'])
  self.assertEqual(len(req['teaching_history']['recent_evaluations']),1)
  self.command('allow-switch','grant',reason='本机管理员授权 Mock 策略切换联调')
  switched=self.command('teach','turn2');self.assertEqual(switched['strategy_selection_mode'],'switched')
  self.command('respond','reply2',message='我会增加独立操作并记录实际结果。')
  self.command('evaluate','eval2',assessment_mode='independent_transfer')
  proposal=self.command('evolve','evolve')
  state=self.call('')[1];self.assertEqual(state['experiments'][0]['status'],'pending')
  self.assertFalse(state['applied_mastery']);self.assertEqual(state['skill_unlocks'],[])
  self.assertEqual(len(state['assignments']),3)
 def test_http_auth_client_owned_fields_and_version_isolation(self):
  self.assertEqual(self.call('',auth=False)[0],403)
  self.begin()
  self.assertEqual(self.call('teach',{'request_id':'bad','allow_strategy_switch':True})[0],400)
  task=b.load(self.h.task['id']);self.assertEqual(task['coding_checkpoints'][-1]['schema_version'],1)
  self.assertEqual(task['teaching']['memory']['schema_version'],1)
  self.assertEqual(task['teaching_v021']['schema_version'],'0.2.1')
 def test_idempotency_collision_and_frozen_evidence(self):
  self.begin();before=self.call('')[1]
  self.command('teach','turn0');after=self.call('')[1]
  self.assertEqual(len(after['turns']),len(before['turns']))
  self.assertEqual(self.call('teach',{'request_id':'turn0','phase':'summary'})[0],400)
  context=next(iter(after['contexts'].values()))
  self.assertTrue(all(e['artifact_ref'] in context['sources'] for e in context['context']['evidence']))
  b.write_project_file(b.project(self.h.task['id'])/'src/products.js','changed')
  self.assertEqual(self.call('teach',{'request_id':'changed'})[0],400)
  self.assertEqual(self.call('')[1]['contexts'],after['contexts'])
 def test_unauthorized_service_switch_rejected_without_assignment(self):
  self.begin();before=self.call('')[1]['assignments']
  class Bad(mock_service.MockTeachingService):
   async def teach(self,request):
    result=await super().teach(request)
    alt=next(c for c in request.strategy_candidates if c.id!=request.active_strategy.id)
    return result.model_copy(update={'strategy_id':alt.id,'strategy_version':alt.version,'strategy_selection_mode':'switched'})
  with patch.object(v,'SERVICE_FACTORY',Bad):self.assertEqual(self.call('teach',{'request_id':'bad-switch'})[0],400)
  self.assertEqual(self.call('')[1]['assignments'],before)
  self.command('teach','bad-switch',retry=True)
  self.assertEqual(len(self.call('')[1]['assignments']),len(before)+1)
 def test_mock_never_unlocks_and_resume_once(self):
  self.begin();self.command('respond','reply',message='测试正常和边界操作。')
  result=self.command('evaluate','eval',assessment_mode='independent_transfer');self.assertTrue(result['suggested_pass'])
  with patch.object(executor,'execute',side_effect=self.h.execute):
   code,res=self.call('resume',{'request_id':'resume','confirmed':True,'teaching_completed':True})
   self.assertEqual(code,202,res);self.h.wait();time.sleep(.03)
   code,res=self.call('resume',{'request_id':'resume','confirmed':True,'teaching_completed':True})
   self.assertEqual(code,200,res)
  task=b.load(self.h.task['id']);self.assertEqual(task['step'],1)
  self.assertFalse(task['coding_run'].get('skill_results'))
  self.assertEqual(self.call('resume',{'request_id':'resume-again','confirmed':True,'teaching_completed':True})[0],400)
 def test_public_contract_bytes_unchanged(self):
  import hashlib
  root=v.Path(v.__file__).parent/'teaching_contract_v021/public'
  for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
   digest,name=line.split(None,1);name=name.strip()
   path=root/name
   self.assertEqual(hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),digest,name)

 def test_failed_coding_resume_can_retry_without_advancing_twice(self):
  self.begin()
  with patch.object(executor,'execute',side_effect=ValueError('synthetic temporary failure')):
   code,result=self.call('resume',{'request_id':'retry-resume','confirmed':True,'teaching_completed':True})
   self.assertEqual(code,202,result);self.h.wait();time.sleep(.03)
  self.assertEqual(b.load(self.h.task['id'])['step'],1)
  def resumed(files,*args,**kwargs):return {'text':'已写入购物车','files':{**files,'src/cart.js':'export const cart=[];'},'events':[]}
  with patch.object(executor,'execute',side_effect=resumed):
   code,result=self.call('resume',{'request_id':'retry-resume','confirmed':True,'teaching_completed':True,'retry':True})
   self.assertEqual(code,202,result);self.h.wait();time.sleep(.03)
  task=b.load(self.h.task['id']);self.assertEqual(task['step'],1);self.assertIn('src/cart.js',b.read_project_files(task['id']))
 def test_invented_evidence_and_capability_rejected(self):
  self.command('configure','config')
  for field,value in [('evidence_refs',['invented']),('capability_id','nonexistent-course')]:
   class Bad(mock_service.MockTeachingService):
    async def decide(self,request):
     result=await super().decide(request)
     return result.model_copy(update={field:value})
   with patch.object(v,'SERVICE_FACTORY',Bad):self.assertEqual(self.call('decide',{'request_id':'bad-'+field})[0],400)
  self.assertFalse(self.call('')[1].get('active_decision'))
 def test_project_scoped_session_and_admin_permission(self):
  token='synthetic-session';v.SESSIONS[token]={'role':'student','task_id':self.h.task['id'],'expires':time.time()+60}
  handler=SimpleNamespace(headers={'Cookie':v.COOKIE+'='+token})
  try:
   self.assertEqual(v.auth(handler,self.h.task['id'])['role'],'student')
   with self.assertRaises(v.AccessDenied):v.auth(handler,'different-project')
   with self.assertRaises(v.AccessDenied):v.auth(handler,self.h.task['id'],admin=True)
  finally:v.SESSIONS.pop(token,None)

 def test_enabled_checkpoint_automatically_hands_off_after_resume(self):
  self.begin();task=b.load(self.h.task['id']);task['checkpoint_delivery']='automatic';b.save(task)
  def resumed(files,*args,**kwargs):return {'text':'已写入购物车','files':{**files,'src/cart.js':'export const cart=[];'},'events':[]}
  with patch.object(executor,'execute',side_effect=resumed):
   code,result=self.call('resume',{'request_id':'auto-resume','confirmed':True,'teaching_completed':True});self.assertEqual(code,202,result)
   for _ in range(300):
    time.sleep(.01)
    with b.task_lock(self.h.task['id']):current=b.load(self.h.task['id'])
    if len(current['teaching_v021']['turns'])==2:break
   else:self.fail('automatic V0.2.1 checkpoint not delivered')
  self.assertEqual(current['coding_checkpoints'][-1]['delivery']['status'],'completed')
  self.assertEqual(current['coding_checkpoints'][-1]['schema_version'],1)

 def test_skip_runs_no_teaching_and_allows_confirmed_resume(self):
  self.command('configure','config')
  task=b.load(self.h.task['id'])
  task['workflow']['stage']=2
  task['checkpoint_delivery']='automatic'
  b.save(task)
  b.start_checkpoint_teaching(task)
  view=self.call('')[1]
  self.assertFalse(view['decision']['teach'])
  self.assertEqual(view['turns'],[])
  self.assertEqual(b.load(task['id'])['coding_checkpoints'][-1]['delivery']['status'],'skipped')
  self.assertEqual(self.call('teach',{'request_id':'skip-teach'})[0],400)
  self.assertEqual(self.call('resume',{'request_id':'no-confirm','confirmed':False,'teaching_completed':True})[0],400)

  body={'request_id':'skip-resume','confirmed':True,'teaching_completed':True}
  with patch.object(executor,'execute',side_effect=self.h.execute) as transport:
   self.assertEqual(self.call('resume',body)[0],202)
   self.h.wait()
   self.assertEqual(self.call('resume',body)[0],200)
   transport.assert_called_once()
  self.assertEqual(b.load(task['id'])['step'],1)

 def test_legacy_demo_library_can_teach_newly_selected_edge_cases(self):
  self.command('configure','config')
  task=b.load(self.h.task['id'])
  library=task['teaching_v021']['library']
  library['knowledge_packages']=[p for p in library['knowledge_packages'] if p['knowledge_point_id']=='acceptance-criteria']
  task['plan'][0]='检查边界情形'
  b.save(task)
  decision=self.command('decide','edge-cases')
  self.assertEqual(decision['knowledge_point_ids'],['edge-cases'])
  turn=self.command('teach','teach-edge-cases')
  self.assertEqual(turn['action']['knowledge_point_ids'],['edge-cases'])

if __name__=='__main__':unittest.main()
