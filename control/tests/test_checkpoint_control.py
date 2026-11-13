"""Protocol acceptance with a simulated Coding transport, no Teaching Agent required."""
import copy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest
from unittest.mock import patch

import test_checkpoints as fixture
import backend as b
from agents import checkpoint_control


class CheckpointControlTests(unittest.TestCase):
    def setUp(self):
        self.h = fixture.CheckpointIntegrationTests()
        self.h.setUp(); self.addCleanup(self.h.doCleanups)
        task = b.load(self.h.task['id'])
        task['checkpoint_delivery'] = 'manual'
        task['plan'] = ['实现商品列表', '实现购物车']
        b.coding_workflow.confirm(task); b.save(task)
        self.calls = []
        def execute(files, payload, *args):
            self.calls.append(copy.deepcopy(payload))
            return {'text': '本轮文件已保存；测试未运行。',
                    'files': {**files, 'src/products.js': 'export const revision = '+str(len(self.calls))+';\n'}, 'events': []}
        self.transport = patch.object(b.opencode_executor, 'execute', side_effect=execute)
        self.transport.start(); self.addCleanup(self.transport.stop)
        self.teacher = patch.object(b.teaching, 'run', side_effect=AssertionError('Manual delivery must not invoke Teaching'))
        self.send = self.teacher.start(); self.addCleanup(self.teacher.stop)

    def initial_pause(self):
        self.assertEqual(self.h.step()[0], 202)
        task = self.h.wait()
        event = task['coding_checkpoints'][-1]
        self.assertEqual(event['delivery']['status'], 'available')
        return task, event

    def body(self, task, event, request_id='resume-1', **changes):
        result = {'session_id': task['id'], 'request_id': request_id, 'confirmed': True,
                  'teaching_completed': True, 'expected_code_hash': task['coding_checkpoints'][-1]['project_evidence']['code_hash']}
        result.update(changes)
        return result

    def command(self, event, action, body):
        return self.h.call(self.h.path+'/checkpoints/'+event['checkpoint_id']+'/'+action, body)

    def test_http_pause_receive_resume_continue_without_teaching(self):
        server = b.LocalHTTPServer(('127.0.0.1', 0), b.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def cleanup():
            server.shutdown(); server.server_close(); thread.join(2)
        self.addCleanup(cleanup)
        def remote(path, body=None):
            req = Request('http://127.0.0.1:'+str(server.server_port)+path,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json'})
            try:
                with urlopen(req, timeout=3) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)
        self.h.call = remote
        task, event = self.initial_pause()
        status, received = remote(self.h.path+'/checkpoints')
        self.assertEqual(status, 200)
        self.assertEqual(received['items'][0]['checkpoint_id'], event['checkpoint_id'])
        body = self.body(task, event)
        self.assertEqual(self.command(event, 'resume', body)[0], 202)
        task = self.h.wait()
        self.assertEqual(task['step'], 1)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(task['coding_checkpoints'][-1]['stage'], '实现购物车')
        status, replay = self.command(event, 'resume', body)
        self.assertEqual(status, 200)
        self.assertEqual(replay['operation']['status'], 'completed')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.command(event, 'resume', self.body(task,event,'resume-other'))[0], 400)
        status, source = remote(self.h.path+'/project-file?path=src/products.js&checkpoint_id='+task['coding_checkpoints'][-1]['checkpoint_id'])
        self.assertEqual(status, 200)
        self.assertFalse(source['stale_for_checkpoint'])
        self.assertIn('revision = 2', source['lines'][0]['text'])
        self.send.assert_not_called()

    def test_multiple_revisions_return_new_results_before_one_final_resume(self):
        task, event = self.initial_pause()
        for i in (1, 2):
            body = self.body(task,event,'revise-'+str(i),instruction='学生确认：修改商品显示 '+str(i))
            self.assertEqual(self.command(event,'revise',body)[0],202)
            task = self.h.wait()
            latest = task['coding_checkpoints'][-1]
            self.assertEqual(task['step'],0)
            self.assertEqual(latest['root_checkpoint_id'],event['checkpoint_id'])
            self.assertEqual(latest['delivery']['status'],'available')
            operation = task['coding_checkpoints'][0]['operations'][-1]
            self.assertEqual(operation['result_checkpoint_id'],latest['checkpoint_id'])
        self.assertEqual(self.command(event,'resume',self.body(task,event))[0],202)
        task = self.h.wait()
        self.assertEqual(task['step'],1)
        self.assertEqual(len(self.calls),4)
        self.assertEqual(len(task['coding_checkpoints'][0]['operations']),3)

    def test_confirmation_version_and_request_conflicts_are_rejected(self):
        task,event = self.initial_pause()
        for changes in ({'confirmed':False},{'session_id':'other'},{'expected_code_hash':'old'},{'teaching_completed':False}):
            self.assertEqual(self.command(event,'resume',self.body(task,event,**changes))[0],400)
        self.assertEqual(self.command(event,'revise',self.body(task,event,instruction=''))[0],400)
        body=self.body(task,event,'revise-1',instruction='学生确认：调整显示')
        self.assertEqual(self.command(event,'revise',body)[0],202); self.h.wait()
        body['instruction']='替换为不同操作'
        self.assertEqual(self.command(event,'revise',body)[0],400)
        self.assertEqual(len(self.calls),2)

    def test_skill_notification_returns_actual_disabled_status_and_records_usage(self):
        task,event = self.initial_pause()
        unlock={'skill_id':'systematic-debugging','assessment_id':'assessment-1','unlocked':True}
        body=self.body(task,event,skill_unlocks=[unlock])
        self.assertEqual(self.command(event,'resume',body)[0],202)
        task=self.h.wait()
        acknowledgement=task['coding_checkpoints'][0]['operations'][0]['skill_results'][0]
        self.assertEqual(acknowledgement['notification_status'],'received')
        self.assertFalse(acknowledgement['enabled']);self.assertFalse(acknowledgement['used'])
        self.assertEqual(acknowledgement['activation_status'],'unsupported')
        self.assertEqual(self.calls[-1]['skill_unlock_notifications'][0]['assessment_id'],'assessment-1')
        self.assertEqual(self.calls[-1]['learning_context']['skills'],[])
        self.assertEqual(task['coding_run']['skill_results'][0],acknowledgement)
        self.assertFalse(task['teaching']['learning']['unlock_requests'])

    def test_failed_resume_retries_same_target_without_accepting_twice(self):
        task,event=self.initial_pause();body=self.body(task,event)
        with patch.object(b.opencode_executor,'execute',side_effect=ValueError('模拟Coding超时')):
            self.assertEqual(self.command(event,'resume',body)[0],202)
            task=self.h.wait()
        self.assertEqual(task['step'],1)
        operation=task['coding_checkpoints'][0]['operations'][0]
        self.assertEqual(operation['status'],'failed')
        self.assertEqual(self.command(event,'resume',body)[0],200)
        body['retry']=True
        self.assertEqual(self.command(event,'resume',body)[0],202)
        task=self.h.wait()
        self.assertEqual(task['step'],1)
        self.assertEqual(task['coding_checkpoints'][0]['operations'][0]['attempt'],2)
        self.assertEqual(task['coding_checkpoints'][0]['operations'][0]['status'],'completed')

    def test_failed_request_cannot_retry_after_another_checkpoint_with_same_code(self):
        task,event=self.initial_pause();body=self.body(task,event)
        with patch.object(b.opencode_executor,'execute',side_effect=ValueError('模拟超时')):
            self.command(event,'resume',body);task=self.h.wait()
        files=b.read_project_files(task['id'])
        b.checkpoint_events.record(task,'another-checkpoint','重新检查','完成',files,files,task['step'])
        b.save(task)
        body['retry']=True
        self.assertEqual(self.command(event,'resume',body)[0],400)

    def test_duplicate_resume_while_running_is_a_receipt_not_another_job(self):
        task,event=self.initial_pause();body=self.body(task,event)
        entered=threading.Event();release=threading.Event()
        def slow(files,payload,*args):
            entered.set();release.wait(3)
            return {'text':'完成','files':files,'events':[]}
        with patch.object(b.opencode_executor,'execute',side_effect=slow) as execute:
            try:
                self.assertEqual(self.command(event,'resume',body)[0],202)
                self.assertTrue(entered.wait(1))
                self.assertEqual(self.command(event,'resume',body)[0],200)
                different={**body,'request_id':'another-resume'}
                self.assertEqual(self.command(event,'resume',different)[0],400)
                self.assertEqual(execute.call_count,1)
            finally:
                release.set();self.h.wait()

    def test_last_phase_resume_finishes_without_launching_more_coding(self):
        task=b.load(self.h.task['id']);task['plan']=task['plan'][:1];b.coding_workflow.confirm(task);b.save(task)
        task,event=self.initial_pause()
        status,result=self.command(event,'resume',self.body(task,event))
        self.assertEqual(status,200)
        self.assertEqual(result['operation']['outcome'],'development_finished')
        self.assertEqual(result['task']['step'],1)
        self.assertEqual(len(self.calls),1)

    def test_cross_session_and_stale_commands_cannot_change_project(self):
        task,event=self.initial_pause()
        other=self.h.call('/api/tasks',{'coding_mode':'opencode','checkpoint_delivery':'manual'})[1]
        body=self.body(task,event);body['session_id']=other['id']
        result=self.h.call('/api/tasks/'+other['id']+'/checkpoints/'+event['checkpoint_id']+'/resume',body)
        self.assertEqual(result[0],400)
        b.write_project_file(b.project(task['id'])/'src/products.js','// external change')
        self.assertEqual(self.command(event,'resume',self.body(task,event))[0],400)
        self.assertEqual(b.load(task['id'])['step'],0)


if __name__=='__main__':unittest.main()
