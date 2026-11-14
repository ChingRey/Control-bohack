import unittest

from agents import linked_list_benchmark as linked, rubric


class LinkedListBenchmarkTests(unittest.TestCase):
    def test_delete_first_and_last_are_different_on_separated_duplicates(self):
        self.assertEqual(linked.execute([4,5,4,6],4),[5,4,6])
        self.assertEqual(linked.execute([4,5,4,6],4,last=True),[4,5,6])
        data={'test_cases':[{'values':[4,5,4,6],'target':4,'expected':[5,4,6]}]}
        self.assertFalse(linked.observe('s','transfer',data,0)['checks'][0]['passed'])

    def test_adjacent_duplicates_do_not_cover_order(self):
        data={'test_cases':[{'values':[4,4,6],'target':4,'expected':[4,6]}]}
        evidence=linked.observe('s','post',data,0)
        self.assertIn('重复值',evidence['case_gaps'])
        feedback=rubric.evaluate(evidence)
        self.assertFalse(feedback['test_passed'])
        self.assertEqual(feedback['scores']['verification']['evidence_ids'],[evidence['id']])

    def test_false_expected_output_is_recorded_without_mutant_credit(self):
        data={'test_cases':[{'values':[2,3],'target':2,'expected':[]}]}
        evidence=linked.observe('s','practice',data,0)
        self.assertEqual(evidence['checks'][0]['actual'],[3])
        self.assertFalse(evidence['checks'][0]['passed'])
        self.assertEqual(evidence['checks'][0]['caught'],[])
        self.assertIn('删头',rubric.evaluate(evidence)['case_gaps'])
