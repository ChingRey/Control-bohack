import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import checkpoints, teaching, memory


class CheckpointIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = patch.object(b, 'DATA', Path(self.temp.name))
        self.db = patch.object(b, 'DB', Path(self.temp.name) / 'records.sqlite3')
        self.data.start(); self.db.start()
        self.addCleanup(self.data.stop); self.addCleanup(self.db.stop)
        self.env = patch.dict(os.environ, {'TEACHING_MODE': 'sample'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.config = patch.object(b.opencode_executor, 'CONFIG', {'key': 'fake', 'model': 'fake', 'url': 'https://example.invalid'})
        self.config.start(); self.addCleanup(self.config.stop)
        self.binary = patch.object(b.opencode_executor, 'binary', return_value='fake')
        self.binary.start(); self.addCleanup(self.binary.stop)
        self.task = self.call('/api/tasks', {'coding_mode': 'opencode'})[1]
        self.path = '/api/tasks/' + self.task['id']
        task = b.load(self.task['id'])
        task.update(plan=['实现商品列表'], plan_draft=['实现商品列表'])
        task['messages'].append({'role': 'user', 'channel': 'coding', 'content': '我需要商品列表和购物车'})
        b.coding_workflow.confirm(task); b.save(task)

    def call(self, path, body=None):
        handler = b.Handler.__new__(b.Handler)
        handler.path = path; handler.server = SimpleNamespace(server_port=8772)
        raw = json.dumps(body, ensure_ascii=False).encode() if body is not None else b''
        handler.headers = {'Host': '127.0.0.1:8772', 'Content-Length': str(len(raw))}
        handler.rfile = io.BytesIO(raw)
        result = []
        handler.reply = lambda code, obj, *args: result.extend((code, copy.deepcopy(obj)))
        handler.do_GET() if body is None else handler.do_POST()
        return result

    def wait(self):
        for _ in range(500):
            with b.task_lock(self.task['id']):
                task = b.load(self.task['id'])
            coding_busy = task.get('coding_run', {}).get('status') in ('queued', 'running')
            teacher_busy = task.get('teaching_run', {}).get('status') in ('queued', 'running')
            if not coding_busy and not teacher_busy:
                return task
            time.sleep(.01)
        self.fail('Background task did not finish')

    def execute(self, files, payload, *args):
        return {'text': '商品列表已写入 src/products.js；尚未运行测试。',
                'files': {**files, 'src/products.js': 'export const products = [];\n'}, 'events': []}

    def step(self):
        return self.call(self.path + '/steps/run', {'confirmed': True, 'expected_step': 0, 'instruction': '实现本阶段商品列表'})

    def test_success_dispatches_one_versioned_checkpoint_and_selects_goal(self):
        captured = []
        respond = teaching.TeachingAgent.respond
        def inspect(agent, ctx, progress=None):
            captured.append(copy.deepcopy(ctx))
            return respond(agent, ctx, progress)
        with patch.object(b.opencode_executor, 'execute', side_effect=self.execute), patch.object(teaching.TeachingAgent, 'respond', new=inspect):
            self.assertEqual(self.step()[0], 202)
            task = self.wait()
        self.assertEqual(task['coding_run']['status'], 'completed')
        self.assertEqual(task['step'], 0)  # Student acceptance still advances the stage.
        self.assertEqual(len(task['coding_checkpoints']), 1)
        event = task['coding_checkpoints'][0]
        self.assertEqual(event['checkpoint_id'], task['coding_run']['id'])
        self.assertEqual(event['session_id'], task['id'])
        self.assertEqual(event['stage'], '实现商品列表')
        self.assertEqual(event['task_description'], '实现本阶段商品列表')
        self.assertEqual(event['user_requirement'], '我需要商品列表和购物车')
        self.assertIn('+export const products', event['project_evidence']['changes'][0]['diff'])
        self.assertEqual(event['project_evidence']['test_status'], 'not_run')
        self.assertEqual(event['delivery']['status'], 'completed')
        self.assertEqual(task['teaching_run']['checkpoint_id'], event['checkpoint_id'])
        self.assertEqual(task['teaching']['turns'][-1]['checkpoint_id'], event['checkpoint_id'])
        self.assertEqual(captured[0]['action'], 'checkpoint')
        self.assertEqual(captured[0]['checkpoint_event']['checkpoint_id'], event['checkpoint_id'])
        self.assertTrue(task['teaching']['plan']['goal'])
        self.assertEqual(self.call(self.path)[1]['coding_checkpoints'], task['coding_checkpoints'])

    def test_teacher_failure_preserves_code_and_review_retries_same_event(self):
        with patch.object(b.opencode_executor, 'execute', side_effect=self.execute), patch.object(teaching, 'run', side_effect=ValueError('模拟教师失败')):
            self.step(); task = self.wait()
        self.assertEqual(task['coding_run']['status'], 'completed')
        self.assertIn('src/products.js', b.read_project_files(task['id']))
        self.assertEqual(task['coding_checkpoints'][0]['delivery']['status'], 'failed')
        checkpoint_id = task['coding_checkpoints'][0]['checkpoint_id']
        self.assertEqual(self.call(self.path + '/teaching/review', {})[0], 202)
        task = self.wait()
        self.assertEqual(task['teaching_run']['status'], 'completed')
        self.assertEqual(len(task['coding_checkpoints']), 1)
        self.assertEqual(task['teaching_run']['checkpoint_id'], checkpoint_id)

    def test_teacher_start_failure_does_not_mark_coding_failed(self):
        with patch.object(b.opencode_executor, 'execute', side_effect=self.execute), patch.object(b, 'start_teaching', side_effect=ValueError('模拟启动失败')):
            self.step(); task = self.wait()
        self.assertEqual(task['coding_run']['status'], 'completed')
        self.assertEqual(task['teaching_run']['status'], 'failed')
        self.assertEqual(task['coding_checkpoints'][0]['delivery']['status'], 'failed')

    def test_timeout_and_stale_results_do_not_dispatch(self):
        with patch.object(b.opencode_executor, 'execute', side_effect=ValueError('OpenCode超时')), patch.object(b, 'start_teaching') as send:
            self.step(); task = self.wait()
            self.assertEqual(task['coding_run']['status'], 'failed')
            self.assertFalse(task.get('coding_checkpoints')); send.assert_not_called()
        def stale(files, payload, *args):
            b.write_project_file(b.project(task['id']) / 'app.js', '// external edit')
            return self.execute(files, payload)
        with patch.object(b.opencode_executor, 'execute', side_effect=stale), patch.object(b, 'start_teaching') as send:
            self.step(); task = self.wait()
            self.assertEqual(task['coding_run']['status'], 'failed')
            self.assertFalse(task.get('coding_checkpoints')); send.assert_not_called()

    def test_chat_does_not_emit_but_plan_completion_does(self):
        task = b.load(self.task['id']); task['plan'] = []; task['plan_draft'] = []; b.save(task)
        def planned(files, payload, *args):
            return {'text': '开发计划\n1. 展示商品\n2. 添加购物车', 'files': files, 'events': []}
        with patch.object(b.opencode_executor, 'execute', side_effect=planned):
            self.call(self.path + '/coding/messages', {'message': '先讨论需求'})
            self.assertFalse(self.wait().get('coding_checkpoints'))
            self.call(self.path + '/coding/generate-plan', {'message': '请生成阶段计划'})
            task = self.wait()
        self.assertEqual(len(task['coding_checkpoints']), 1)
        self.assertEqual(task['coding_checkpoints'][0]['kind'], 'planning')
        self.assertEqual(task['coding_checkpoints'][0]['stage'], 'planning')

    def test_sample_step_uses_same_event_contract(self):
        task = b.load(self.task['id']); task['mode'] = 'sample'; b.save(task)
        for name, source in b.FILES.items():
            b.write_project_file(b.project(task['id']) / name, source)
        self.assertEqual(self.step()[0], 202)
        task = self.wait()
        self.assertEqual(task['step'], 1)
        self.assertEqual(len(task['coding_checkpoints']), 1)
        self.assertEqual(task['coding_checkpoints'][0]['delivery']['status'], 'completed')

    def test_restart_marks_interrupted_delivery_failed(self):
        task = b.load(self.task['id'])
        checkpoints.record(task, 'checkpoint', '执行任务', '完成', {}, {}, 0)
        task['coding_checkpoints'][0]['delivery'] = {'status': 'queued'}
        task['teaching_run'] = {'id': 'teacher', 'status': 'queued', 'checkpoint_id': 'checkpoint'}
        self.assertTrue(b.recover_interrupted(task))
        self.assertEqual(task['coding_checkpoints'][0]['delivery']['status'], 'failed')


class CheckpointContextTests(unittest.TestCase):
    def task(self):
        return {'id': 'session', 'plan': ['实现接口'], 'step': 0, 'files': {}, 'changes': [], 'checks': [],
                'messages': [{'role': 'user', 'channel': 'coding', 'content': '实现商品API'}]}

    def test_large_project_is_bounded_and_subdirectory_lines_are_readable(self):
        task = self.task()
        files = {f'src/file{i}.py': '\n'.join(f'value_{n} = {n}' for n in range(400)) for i in range(180)}
        files['src/api.py'] = '\n'.join(f'item_{n} = {n}' for n in range(400))
        task['files'] = files
        event = checkpoints.record(task, 'run', '实现API', '已完成', {}, files, 0)
        ctx = teaching.context(task, 'checkpoint')
        self.assertLessEqual(memory.size(ctx['files']), checkpoints.SOURCE_CHARS)
        self.assertLess(memory.size(ctx), memory.MAX_CONTEXT_CHARS)
        self.assertEqual(ctx['project_files']['total_file_count'], 181)
        self.assertGreater(ctx['project_files']['omitted_file_count'], 0)
        self.assertGreater(ctx['checkpoint_event']['project_evidence']['omitted_change_count'], 0)
        self.assertTrue(any(c['diff_truncated'] for c in event['project_evidence']['changes']))
        result = teaching.dispatch_tool('read_project_file', {'path': 'src/api.py', 'start_line': 150, 'limit': 2}, ctx, project_source=files)
        self.assertEqual(result['lines'], [{'line': 150, 'text': 'item_149 = 149'}, {'line': 151, 'text': 'item_150 = 150'}])
        output = {'reply': '请检查这个接口的依据', 'next_phase': 'observe', 'teaching_action': 'ask',
                  'plan': {'goal': '检查API', 'reason': '当前任务', 'next_step': '检查输出', 'open_questions': []},
                  'hint_level': 0, 'assessment': 'insufficient', 'student_evidence_ids': [],
                  'citations': [{'file': 'src/api.py', 'line': 150, 'quote': 'item_149 = 149'}],
                  'source_ids': [], 'issue_kind': 'hypothesis', 'upgrade_suggestion': ''}
        self.assertEqual(teaching.validate(output, ctx)['citations'][0]['line'], 150)
        for path in ('../secret', 'C:/Users/momo/auth.json', 'other/project.py'):
            with self.assertRaises(ValueError):
                teaching.dispatch_tool('read_project_file', {'path': path}, ctx, project_source=files)

    def test_event_is_deduplicated_and_old_source_is_explicitly_stale(self):
        task = self.task(); task['files'] = {'app.js': 'const value = 1;'}
        event = checkpoints.record(task, 'run', '实现API', '已完成', {}, task['files'], 0)
        self.assertIs(checkpoints.record(task, 'run', '重复', '重复', {}, {}, 0), event)
        task['files']['app.js'] = 'const value = 2;'
        self.assertTrue(teaching.context(task, 'review')['checkpoint_event']['project_evidence']['stale_for_code'])
        self.assertEqual(event['agent_output'], '已完成')

    def test_tool_read_budget_is_enforced_without_losing_complete_lines(self):
        task = self.task(); files = {'src/api.py': '\n'.join('x' * 200 for _ in range(400))}; task['files'] = files
        ctx = teaching.context(task, 'review')
        for _ in range(3):
            try:
                result = teaching.dispatch_tool('read_project_file', {'path': 'src/api.py', 'limit': 120}, ctx, project_source=files)
                self.assertTrue(all(len(row['text']) == 200 for row in result['lines']))
            except ValueError:
                break
        self.assertLessEqual(ctx['source_read_characters'], 24000)
        with self.assertRaises(ValueError):
            teaching.dispatch_tool('read_project_file', {'path': 'src/api.py'}, ctx, project_source=files)

    def test_model_tool_loop_can_cite_source_omitted_from_initial_context(self):
        task = self.task()
        task['files'] = {'src/api.py': '\n'.join(f'item_{n} = {n}' for n in range(200))}
        checkpoints.record(task, 'checkpoint', '实现API', '已保存API', {}, task['files'], 0)
        call = {'id': 'read-1', 'type': 'function', 'function': {'name': 'read_project_file',
                'arguments': json.dumps({'path': 'src/api.py', 'start_line': 150, 'limit': 1})}}
        output = {'reply': '请检查商品接口的结果', 'next_phase': 'observe', 'teaching_action': 'ask',
                  'plan': {'goal': '检查商品API的返回值', 'reason': '检查点中的接口变更', 'next_step': '预测输出', 'open_questions': []},
                  'hint_level': 0, 'assessment': 'insufficient', 'student_evidence_ids': [],
                  'citations': [{'file': 'src/api.py', 'line': 150, 'quote': 'item_149 = 149'}],
                  'source_ids': [], 'issue_kind': 'hypothesis', 'upgrade_suggestion': ''}
        responses = [{'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [call]}}]},
                     {'choices': [{'message': {'content': json.dumps(output)}}]}]
        with patch.dict(os.environ, {'TEACHING_MODE': 'model', 'TEACHING_PROVIDER': 'deepseek',
                                     'DEEPSEEK_API_KEY': 'fake', 'TEACHING_API_KEY': 'fake', 'TEACHING_MODEL': 'fake'}), \
             patch('agents.teaching.request_model', side_effect=responses) as request:
            teaching.run(task, 'checkpoint')
        first = json.loads(request.call_args_list[0].args[0].data)
        initial = json.loads(first['messages'][1]['content'])
        self.assertNotIn(150, [r['line'] for r in initial['files']['src/api.py']])
        self.assertEqual(task['teaching']['plan']['goal'], '检查商品API的返回值')
        self.assertEqual(task['teaching']['turns'][-1]['checkpoint_id'], 'checkpoint')
        self.assertTrue(task['teaching']['turns'][-1]['tools'][0]['success'])


if __name__ == '__main__':
    unittest.main()
