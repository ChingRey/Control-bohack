import unittest

from agents import teaching_methods as methods


class TeachingMethodsTests(unittest.TestCase):
    def setUp(self):
        self.decision = {
            'decision_id': 'decision-1',
            'goal_id': 'goal-1',
            'objective': '解释当前目标并在新情境中应用',
            'success_criteria': [
                {'criterion_id': 'explain', 'description': '能解释目标'},
                {'criterion_id': 'transfer', 'description': '能独立迁移'},
            ],
        }
        self.strategy = {'id': 'strategy-1', 'version': 1, 'content': {
            'steps': [{'id': 'ask-1', 'action': 'ask', 'purpose': '先了解学生的判断'}],
        }}
        self.context = {'valid_evidence_refs': [1], 'coding_plan': ['只读项目计划']}
        self.state = {'subplans': {}, 'hint_level': 0}

    def test_create_and_record_matching_step_advances_once(self):
        method = methods.teach(self.decision, self.state, self.strategy, self.context)
        result = {
            'execution_id': 'execution-1', 'subplan_id': method['subplan']['id'],
            'subplan_version': 1, 'step_id': 'ask-1', 'action': 'ask',
            'success': True, 'result_ref': 'turn-1',
        }
        recorded = methods.record_step(self.state, method, result)
        self.assertTrue(recorded['advanced'])
        self.assertEqual(self.state['subplans']['decision-1']['current_step_index'], 1)
        self.assertTrue(methods.needs_evaluation(self.state))
        self.assertTrue(methods.record_step(self.state, method, result)['duplicate'])

    def test_knowledge_and_pause_do_not_claim_a_subplan_step(self):
        knowledge = methods.teach(self.decision, self.state, self.strategy, self.context, 'knowledge')
        self.assertEqual(knowledge['next_step']['action'], 'explain')
        self.assertEqual(knowledge['next_step']['action_source'], 'workflow')
        self.assertIsNone(knowledge['next_step']['step_id'])
        paused = methods.teach(self.decision, self.state, self.strategy, self.context, 'pause')
        self.assertEqual(paused['next_step']['action'], 'pause')
        self.assertEqual(paused['next_step']['action_source'], 'workflow')
        self.assertIsNone(paused['next_step']['step_id'])

    def test_matching_evaluation_completes_only_with_all_criteria_and_transfer(self):
        method = methods.teach(self.decision, self.state, self.strategy, self.context)
        methods.store_subplan(self.state, method)
        subplan = self.state['subplans']['decision-1']
        self.state['last_evaluation'] = {
            'evaluation_id': 'evaluation-1', 'decision_id': 'decision-1',
            'goal_id': 'goal-1', 'subplan_id': subplan['id'], 'subplan_version': 1,
            'goal_status': 'met', 'evidence_refs': [1], 'transfer_evidence_ref': 1,
            'criterion_results': [
                {'criterion_id': 'explain', 'passed': True},
                {'criterion_id': 'transfer', 'passed': True},
            ],
        }
        completed = methods.teach(self.decision, self.state, self.strategy, self.context)
        self.assertTrue(completed['subplan_updated'])
        self.assertEqual(completed['subplan']['status'], 'completed')

    def test_wrong_goal_evaluation_is_stale_and_does_not_complete(self):
        method = methods.teach(self.decision, self.state, self.strategy, self.context)
        methods.store_subplan(self.state, method)
        subplan = self.state['subplans']['decision-1']
        self.state['last_evaluation'] = {
            'evaluation_id': 'evaluation-wrong-goal', 'decision_id': 'decision-1',
            'goal_id': 'another-goal', 'subplan_id': subplan['id'], 'subplan_version': 1,
            'goal_status': 'insufficient_evidence', 'evidence_refs': [],
        }
        result = methods.teach(self.decision, self.state, self.strategy, self.context)
        self.assertTrue(result['evaluation_stale'])
        self.assertFalse(result['subplan_updated'])
        self.assertEqual(result['subplan']['status'], 'active')

    def test_failed_step_is_not_advanced_and_replan_preserves_history(self):
        method = methods.teach(self.decision, self.state, self.strategy, self.context)
        failed = {
            'execution_id': 'execution-failed', 'subplan_id': method['subplan']['id'],
            'subplan_version': 1, 'step_id': 'ask-1', 'action': 'ask',
            'success': False, 'failure_reason': '模型输出校验失败',
        }
        result = methods.record_step(self.state, method, failed)
        self.assertFalse(result['advanced'])
        self.state['last_evaluation'] = {
            'evaluation_id': 'evaluation-partial', 'decision_id': 'decision-1',
            'goal_id': 'goal-1', 'subplan_id': method['subplan']['id'], 'subplan_version': 1,
            'goal_status': 'partial', 'evidence_refs': [1],
            'teaching_diagnosis': {'error_type': 'conceptual_gap'},
        }
        revised = methods.teach(self.decision, self.state, self.strategy, self.context)
        self.assertTrue(revised['subplan_replanned'])
        self.assertEqual(revised['subplan']['version'], 2)
        index = revised['subplan']['current_step_index']
        self.assertEqual(revised['subplan']['steps'][0]['status'], 'skipped')
        self.assertEqual(revised['subplan']['steps'][index]['action'], 'explain')
        methods.store_subplan(self.state, revised)
        self.assertEqual(self.state['subplans']['decision-1']['replan_history'][0]['from_version'], 1)


if __name__ == '__main__':
    unittest.main()
