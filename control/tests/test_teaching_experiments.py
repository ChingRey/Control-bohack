"""End-to-end tests for evidence, actual planning and strategy state."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agents import benchmark as b, rubric
from scripts.demo_teaching_evolution import GOOD, GAP, http_server, pilot, replay, summary
import backend


class EvolutionTests(unittest.TestCase):
    def test_real_http_replanning_trial_validation_recall_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with patch.multiple(backend,DATA=path,DB=path/'records.sqlite3'), patch.dict(os.environ,{}):
                proof=replay(path)
                board=proof['persisted_dashboard']
                old,new=board['versions']
                self.assertEqual((old['status'],new['status']),('baseline','validated'))
                self.assertEqual(board['trial_count'],3)
                source=old['results'][0]
                self.assertEqual(new['source_evaluation_id'],source['evaluation_id'])
                self.assertEqual(new['evidence_ids'],source['evidence_ids'])
                self.assertIn('预期 → 实际', next(x for x in source['executed_steps'] if x['phase']=='remediation')['prompt'])
                remediation=next(x for x in source['executed_steps'] if x['phase']=='remediation')
                self.assertTrue(remediation['feedback_id'])
                with backend.connection() as c:
                    for raw, in c.execute('SELECT body FROM teaching_experiments'):
                        session=json.loads(raw)
                        if session['id']==source['trial_id']:
                            break
                self.assertEqual(remediation['feedback_id'],session['evaluations']['practice'][0]['evaluation_id'])
                self.assertEqual(next(x for x in session['events'] if x['phase']=='remediation')['subplan_version'],2)
                self.assertEqual(proof['later_decision']['source'],'decide_service_v0.2.1')
                self.assertEqual(source['checkpoint_id'],session['decision']['checkpoint_id'])
                self.assertIn(source['checkpoint_id'],session['decision']['evidence_refs'][0])
                self.assertEqual(backend.load(session['task_id'])['coding_checkpoints'][0]['checkpoint_id'],
                                 source['checkpoint_id'])
                self.assertIn('先独立设计',proof['later_decision']['learning_goal'])
                tested=new['results'][0]
                self.assertEqual(tested['strategy_status_at_teach'],'testing')
                self.assertIn(new['proposed_adjustment'],[x['prompt'] for x in tested['executed_steps'] if x['phase']=='lesson'])
                self.assertGreater(tested['transfer_level'],source['transfer_level'])

    def test_rejected_candidate_leaves_default_and_keeps_failed_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with patch.multiple(backend,DATA=path,DB=path/'records.sqlite3'), patch.dict(os.environ,{'CONTROL_ALLOW_SIMULATION':'1'}):
                with http_server() as request:
                    _,profile,_=pilot(request)
                    second,_,_=pilot(request,'candidate',profile=profile)
                    self.assertEqual(second['events'][0]['strategy_version'],1)
                    self.assertEqual(summary(request)['versions'][1]['status'],'candidate')
                    pilot(request,'candidate')
                    view=summary(request)
                    self.assertEqual(view['versions'][1]['status'],'rejected')
                    self.assertFalse(view['versions'][0]['results'][1]['eligible'])
                    self.assertEqual(view['versions'][1]['sample_count'],1)

    def test_human_requires_two_different_comparable_pairs_and_keeps_local_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with patch.multiple(backend,DATA=path,DB=path/'records.sqlite3'):
                with http_server() as request:
                    a,profile,_=pilot(request,cohort='human')
                    pilot(request,'candidate',succeeds=True,cohort='human')
                    self.assertEqual(request('/api/teaching/strategy-trials')['versions'][1]['status'],'testing')
                    pilot(request,'baseline',cohort='human')
                    pilot(request,'candidate',succeeds=True,cohort='human')
                    self.assertEqual(request('/api/teaching/strategy-trials')['versions'][1]['status'],'validated')
                    repeated,_,_=pilot(request,succeeds=True,profile=profile,cohort='human')
                    self.assertEqual(repeated['decision']['personal_evaluation_ref'],a['result']['evaluation_id'])
                    self.assertNotIn(profile,json.dumps(request('/api/teaching/strategy-trials')))

    def test_withdraw_keeps_evidence_and_future_default_falls_back(self):
        from agents.strategy_rollback import withdraw
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with patch.multiple(backend,DATA=path,DB=path/'records.sqlite3'), patch.dict(os.environ,{}):
                replay(path)
                with backend.connection() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    self.assertEqual(withdraw(conn,'simulation',2,'复核后撤回')['fallback_version'],1)
                with http_server() as request:
                    old=summary(request)['versions'][1]
                    self.assertEqual(old['status'],'withdrawn')
                    self.assertEqual({row['strategy_status_at_teach'] for row in old['results']},{'testing','validated'})
                    self.assertEqual(old['sample_count'],2)
                    later,_,_=pilot(request,succeeds=True)
                    self.assertEqual(later['events'][0]['strategy_version'],1)
                    self.assertIsNone(later['decision']['experience_ref'])

    def test_missing_is_not_zero_and_help_caps_scores(self):
        obs=b.observe('s','practice',{'answers':{'concept':0}},2)
        a=rubric.evaluate(obs)
        self.assertIsNone(a['total_score'])
        self.assertEqual(a['scores']['knowledge']['level'],0)
        self.assertIsNone(a['scores']['verification']['level'])
        guided=b.observe('s','practice',{'answers':GOOD,'predictions':[True,False,False,False]},2)
        report=rubric.evaluate(guided)
        self.assertEqual(report,rubric.evaluate(guided))
        self.assertEqual(report['scores']['verification']['level'],2)
        self.assertFalse(report['mastered'])

    def test_post_alone_or_failed_transfer_cannot_pass(self):
        post=b.observe('s','post',{'answers':GOOD,'predictions':[True,False,False,False]})
        weak=b.observe('s','transfer',{'answers':{'order':1,'failure':1},'predictions':[True,False,False,False]})
        self.assertEqual(rubric.evaluate(post)['evidence_sufficiency'],'insufficient_evidence')
        final=rubric.evaluate(post,weak)
        self.assertGreaterEqual(final['total_score'],80)
        self.assertFalse(final['mastered'])

    def test_strategy_compare_rejects_transfer_regression_or_excess_hints(self):
        old={'trial_id':'old','participant':'a','gain':5,'pre_score':60,'post_score':65,
             'transfer_passed':True,'transfer_level':3,'test_passed':True,'hint_burden':2}
        new={**old,'trial_id':'new','participant':'b','gain':25,'post_score':85,'transfer_level':4}
        from agents.evolve import compare
        gate={'min_pairs':1,'max_pre_gap':10,'min_gain_delta':5}
        self.assertEqual(compare([old],[new],gate)['status'],'validated')
        self.assertEqual(compare([old],[{**new,'hint_burden':3}],gate)['status'],'rejected')
        self.assertEqual(compare([old],[{**new,'transfer_level':2,'transfer_passed':False}],gate)['status'],'rejected')
