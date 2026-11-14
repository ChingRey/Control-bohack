import base64
import unittest
from agents import workflow, teaching, opencode_executor
import backend as b
import test_checkpoints as fixture

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
 def test_material_revision_and_private_context(self):
  task={}
  workflow.update(task,{'kind':'requirements','content':'计数器','expected_revision':0,'confirmed':True})
  workflow.update(task,{'kind':'learner','content':'待核实','expected_revision':1})
  self.assertNotIn('learner',workflow.shared(task)['materials'])
  with self.assertRaises(ValueError):workflow.update(task,{'kind':'design','content':'旧版本','expected_revision':0})
  self.assertEqual(len(workflow.state(task)['materials']['requirements']),1)
 def test_binary_restore_preserves_chat_and_snapshot(self):
  task=b.load(self.h.task['id']);root=b.project(task['id'])
  b.write_project_bytes(root/'asset.custom',b'\x00\xff')
  self.assertEqual(self.h.call(self.h.path+'/versions/save',{'label':'原始'})[0],200)
  stored=b.load(task['id']);version=stored['project_versions'][0]
  b.write_project_bytes(root/'asset.custom',b'\x00changed');b.write_project_file(root/'new.js','new')
  before=b.load(task['id'])['messages']
  current=self.h.call(self.h.path+'/versions/current',{})[1]
  self.assertEqual(self.h.call(self.h.path+'/versions/restore',{'version_id':version['id'],'expected_hash':'stale'})[0],400)
  status,snap=self.h.call(self.h.path+'/versions/restore',{'version_id':version['id'],'expected_hash':current['hash']})
  self.assertEqual(status,200);self.assertEqual((root/'asset.custom').read_bytes(),b'\x00\xff');self.assertFalse((root/'new.js').exists())
  self.assertEqual(b.load(task['id'])['messages'],before)
  self.assertNotIn('project_versions',snap);self.assertEqual(len(snap['version_history']),2)
 def test_permissions_unchanged(self):
  self.assertEqual(opencode_executor.permissions()['write'],'allow')
  self.assertEqual(opencode_executor.execution_timeout(False),900)
  self.assertNotIn('write_project_file',[t['function']['name'] for t in teaching.tools()])

 def test_behavior_report_bound_to_code(self):
  current=self.h.call(self.h.path+'/versions/current',{})[1]
  body={'expected_hash':current['hash'],'operation':'点击添加','expected':'新增一条','actual':'新增一条','result':'passed'}
  self.assertEqual(self.h.call(self.h.path+'/behavior/record',body)[0],200)
  b.write_project_file(b.project(self.h.task['id'])/'new.js','changed')
  self.assertEqual(self.h.call(self.h.path+'/behavior/record',body)[0],400)
  self.assertEqual(b.load(self.h.task['id'])['behavior_records'][0]['source'],'student_report_not_independent_test')
 def test_page_resource_served_and_no_teacher_write_tool(self):
  status,raw=self.h.call('/workflow.js')
  self.assertEqual(status,200);self.assertIn(b'workflowNames',raw)
  from agents import workflow_methods
  self.assertEqual(len(workflow_methods.METHODS),6)
  self.assertIn('safety-guard',workflow_methods.packet(4))

 def test_prototype_executes_without_full_plan(self):
  from unittest.mock import patch
  t=b.load(self.h.task['id']);t['plan']=[];t['plan_draft']=[];b.save(t)
  revision=workflow.state(t)['revision']
  self.assertEqual(self.h.call(self.h.path+'/workflow/material',{'kind':'requirements','content':'计数按钮','confirmed':True,'expected_revision':revision})[0],200)
  def execute(files,packet,planning=False,chatting=False):
   self.assertFalse(planning);self.assertFalse(chatting)
   self.assertTrue(packet['shared_materials']['confirmed_materials']['requirements'])
   return {'text':'原型已创建','files':{'index.html':'<button>计数</button>'},'events':[]}
  with patch.object(opencode_executor,'execute',side_effect=execute):
   self.assertEqual(self.h.call(self.h.path+'/coding/prototype',{'expected_revision':revision+1})[0],202)
   t=self.h.wait()
  self.assertEqual(t['coding_run']['status'],'completed');self.assertIn('index.html',b.read_project_files(t['id']))
