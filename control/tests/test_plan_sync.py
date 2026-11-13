import unittest
from agents import coding_workflow as w, opencode_executor as e
class PlanSyncTests(unittest.TestCase):
 def test_numbered_plan_order(self):
  t={};self.assertTrue(w.sync_plan(t,'开发计划：\n1. 页面布局\n2. 游戏交互'));self.assertEqual(t['plan_draft'],['页面布局','游戏交互'])
 def test_ordinary_list_not_plan(self):
  t={};self.assertFalse(w.sync_plan(t,'你好：\n1. 可以做网页\n2. 可以做游戏'))
 def test_native_todos(self):
  t={};w.sync_plan(t,events=[{'part':{'tool':'todowrite','state':{'input':{'todos':[{'content':'第一阶段'},{'content':'第二阶段'}]}}}}]);self.assertEqual(t['plan_draft'],['第一阶段','第二阶段'])
 def test_new_workflow_keeps_api(self):
  try:
   e.configure('test-key','test-model','cn');w.state({});w.state({});self.assertTrue(e.metadata()['configured'])
  finally:e.CONFIG=None
