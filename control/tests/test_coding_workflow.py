import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents import coding_workflow as w

class WorkflowTests(unittest.TestCase):
    def task(self):return {'id':'isolated','step':0,'plan':[]}
    def test_plan_and_pause_contract(self):
        t=self.task();w.set_plan(t,['界面，停下审查','交互，停下审查'])
        t['plan']=t['plan_draft'];w.confirm(t)
        self.assertEqual(w.state(t)['status'],'paused')
        self.assertTrue(w.prepare(t,'做界面')['stop_after_current_phase'])
        with self.assertRaises(ValueError):w.set_plan(t,['覆盖'])
    def test_experience_switch_and_unverified_skills(self):
        t=self.task();rules={'rules':[{'id':'r','revision':2}],'skills':[{'id':'unverified'}]}
        self.assertEqual(w.prepare(t,'x',rules)['learning_context']['rules'],rules['rules'])
        w.state(t)['experience_enabled']=False
        p=w.prepare(t,'x',rules)
        self.assertEqual(p['learning_context']['rules'],[])
        self.assertEqual(p['learning_context']['skills'],[])
        self.assertEqual(len(rules['rules']),1)
    def test_unconnected_never_advances(self):
        t=self.task()
        with self.assertRaises(ValueError):w.OpenCodeCodingAgent().step(t,'x')
        self.assertEqual(t['step'],0)
        w.inspect_phase(t,w.prepare(t,'x'))
        self.assertFalse(w.state(t)['loads'][0]['submitted'])
        self.assertFalse(w.state(t)['loads'][0]['applied'])
