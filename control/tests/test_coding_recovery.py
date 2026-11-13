import unittest
import backend
class RecoveryTests(unittest.TestCase):
 def test_coding_only(self):
  t={'coding_run':{'status':'running'}}
  self.assertTrue(backend.recover_interrupted(t));self.assertEqual(t['coding_run']['status'],'failed')
  self.assertFalse(backend.recover_interrupted(t))
 def test_completed_unchanged(self):
  t={'coding_run':{'status':'completed'}};self.assertFalse(backend.recover_interrupted(t))
if __name__=='__main__':unittest.main()
