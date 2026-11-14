import unittest
from unittest.mock import patch
import test_checkpoints as fixture
import backend as b


class PhaseScopeTests(unittest.TestCase):
    def setUp(self):
        self.h = fixture.CheckpointIntegrationTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        task = b.load(self.h.task['id'])
        task['checkpoint_delivery'] = 'manual'
        task['plan'] = ['需求分析：确定点击和计分规则', '实现游戏界面', '实现倒计时']
        b.coding_workflow.confirm(task)
        b.save(task)

    def test_write_plan_without_changes_cannot_reach_acceptance(self):
        task = b.load(self.h.task['id'])
        task['plan'] = ['添加计数器']
        b.coding_workflow.confirm(task); b.save(task)
        def no_change(files, payload, *args):
            return {'text': '已经完成，测试全部通过。', 'files': files, 'events': []}
        with patch.object(b.opencode_executor, 'execute', side_effect=no_change):
            self.h.call(self.h.path+'/steps/run', {'confirmed': True, 'expected_step': 0, 'instruction': '执行本阶段'})
            task = self.h.wait()
        self.assertEqual(task['coding_run']['status'], 'failed')
        with self.assertRaises(ValueError): b.coding_workflow.accept_phase(task)

    def test_nonwriting_step_needs_no_file_changes_and_no_auto_acceptance(self):
        task = b.load(self.h.task['id'])
        task['plan'] = ['检查运行结果并记录观察']
        b.coding_workflow.confirm(task); b.save(task)
        def no_change(files, payload, *args):
            return {'text': '静态检查结束，实际运行未验证。', 'files': files, 'events': []}
        with patch.object(b.opencode_executor, 'execute', side_effect=no_change):
            self.h.call(self.h.path+'/steps/run', {'confirmed': True, 'expected_step': 0, 'instruction': '执行本阶段'})
            task = self.h.wait()
        scope = b.coding_workflow.phase_contract(task)
        self.assertFalse(scope['requires_file_change'])
        self.assertEqual(scope['execution_status'], 'executed')
        self.assertEqual(scope['acceptance_status'], 'not_accepted')
        self.assertEqual(task['step'], 0)
        b.coding_workflow.accept_phase(task)
        self.assertEqual(task['step'], 1)

    def test_requirement_stage_cannot_commit_premature_game_files(self):
        with patch.object(b.opencode_executor, 'execute', side_effect=self.h.execute) as transport:
            self.assertEqual(self.h.step()[0], 202)
            task = self.h.wait()
        self.assertTrue(transport.call_args.args[2])
        self.assertEqual(task['coding_run']['status'], 'failed')
        self.assertFalse((b.project(task['id']) / 'src/products.js').exists())
        self.assertEqual(task['step'], 0)
        self.assertFalse(task.get('coding_checkpoints'))

    def test_readonly_stage_reports_exact_plan_and_waits(self):
        captured = []
        def execute(files, payload, *args):
            captured.append(payload)
            return {'text': '玩家点击地鼠获得一分。', 'files': files, 'events': []}
        with patch.object(b.opencode_executor, 'execute', side_effect=execute):
            self.h.step()
            task = self.h.wait()
        report = task['messages'][-1]['phase_report']
        self.assertEqual(report['title'], task['plan'][0])
        self.assertEqual(report['status'], 'executed_pending_review')
        self.assertEqual(task['step'], 0)
        self.assertEqual(captured[0]['phase_contract']['future'][0]['title'], task['plan'][1])
        self.assertEqual(task['coding_checkpoints'][-1]['stage'], task['plan'][0])

    def test_file_stage_keeps_write_tools_and_original_title(self):
        task = b.load(self.h.task['id'])
        task['plan'][0] = '实现商品列表'
        b.coding_workflow.confirm(task)
        b.save(task)
        with patch.object(b.opencode_executor, 'execute', side_effect=self.h.execute) as transport:
            self.h.step()
            task = self.h.wait()
        self.assertFalse(transport.call_args.args[2])
        self.assertEqual(task['messages'][-1]['phase_report']['title'], '实现商品列表')
        self.assertTrue((b.project(task['id']) / 'src/products.js').exists())
        self.assertEqual(task['step'], 0)
