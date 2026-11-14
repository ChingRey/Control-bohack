import io,json,os,unittest
from unittest.mock import patch
from agents import teaching,teaching_evolution

class TeachingStreamProgressTests(unittest.TestCase):
 def test_one_request_streams_visible_reply_and_reports_loaded_experience_versions(self):
  task={'id':'fixture','mode':'opencode','title':'Example','plan':['Explain state'],'plan_draft':[],'step':0,
        'files':{'app.js':'const score = 42;'},'changes':[],'checks':[],
        'messages':[{'channel':'coding','role':'user','content':'Build a game'},
                    {'channel':'teaching','role':'user','content':'解释 app.js:1 的状态'}]}
  expected=teaching_evolution.packet(task)
  frames=[]
  for delta,finish in [({'reasoning_content':'private reasoning never publish'},None),({'content':'score 保存当前分数。'},None),({'content':'<continuity_memory>{"notes":[]}</continuity_memory>'},None),({},'stop')]:
   frames.append('data: '+json.dumps({'choices':[{'index':0,'delta':delta,'finish_reason':finish}]})+'\n\n')
  frames.append('data: [DONE]\n\n')
  response=io.BytesIO(''.join(frames).encode());response.headers={'Content-Type':'text/event-stream'}
  updates=[]
  config={'TEACHING_MODE':'model','TEACHING_PROVIDER':'siliconflow','SILICONFLOW_API_KEY':'fixture-key','TEACHING_MODEL':'zai-org/GLM-5.3-Flash'}
  with patch.dict(os.environ,config),patch.object(teaching,'urlopen',return_value=response) as send:
   reply=teaching.run(task,progress=lambda stage,value:updates.append((stage,value)))
  self.assertEqual(send.call_count,1)
  payload=json.loads(send.call_args.args[0].data)
  self.assertTrue(payload['stream']);self.assertNotIn('tools',payload)
  self.assertEqual(reply,'score 保存当前分数。')
  visible=[value for stage,value in updates if stage=='streaming']
  self.assertTrue(visible);self.assertNotIn('private reasoning',str(visible));self.assertNotIn('continuity_memory',str(visible))
  experience=next(value for stage,value in updates if stage=='experience_loaded')
  self.assertEqual(experience['revision'],expected['revision'])
  self.assertEqual([(e['id'],e['revision']) for e in experience['entries']],[(e['id'],e['revision']) for e in expected['entries']])
  self.assertIn('materials_ready',[stage for stage,value in updates])
  timings=task['teaching']['turns'][-1]['request_timings'][0]
  self.assertIn('first_content_seconds',timings)
  self.assertIn('first_reasoning_seconds',timings)
