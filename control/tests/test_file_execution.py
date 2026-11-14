import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import backend as b
from agents import coding_workflow, opencode_executor as executor, project_files
import test_checkpoints as fixture


class ProjectFileExecutionTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        task=b.load(self.h.task['id']);task['checkpoint_delivery']='manual';b.save(task)

    def run_coding(self, files, packet, planning=False, chatting=False):
        self.assertFalse(planning);self.assertFalse(chatting)
        content='console.log("revised");' if 'src/main.js' in files else 'console.log("ready");'
        return {'text':'已保存 src/main.js','files':{**files,'src/main.js':content},'events':[]}

    def test_create_js_request_and_followup_revision_are_writable(self):
        with patch.object(executor,'execute',side_effect=self.run_coding):
            self.assertEqual(self.h.call(self.h.path+'/coding/messages',{'message':'按计划创建 src/main.js 并写入代码'})[0],202)
            task=self.h.wait();root=task['coding_checkpoints'][-1]['checkpoint_id']
            self.assertIn('src/main.js',b.read_project_files(task['id']))
            self.assertEqual(self.h.call(self.h.path+'/coding/messages',{'message':'修改 src/main.js 的初始化代码'})[0],202)
            task=self.h.wait()
        self.assertEqual(task['coding_checkpoints'][-1]['root_checkpoint_id'],root)
        self.assertEqual(sum(m['content']=='修改 src/main.js 的初始化代码' for m in task['messages']),1)

    def test_new_project_plans_before_writing_and_pauses_each_stage(self):
        task=b.load(self.h.task['id']);task['plan']=[];task['plan_draft']=[];b.save(task)
        for requirement in ('我们做打地鼠小游戏','请创建一个 src/main.js 文件'):
            current=b.load(self.h.task['id']);current['plan_draft']=[];b.save(current)
            def plan(files,packet,planning=False,chatting=False):
                self.assertTrue(planning);self.assertFalse(chatting)
                self.assertIsNone(packet['authorized_phase'])
                return {'text':'开发计划：\n1. 创建基础页面\n2. 实现游戏交互','files':files,'events':[]}
            with patch.object(executor,'execute',side_effect=plan):
                self.assertEqual(self.h.call(self.h.path+'/coding/messages',{'message':requirement})[0],202)
                task=self.h.wait()
            self.assertEqual(task['plan'],[]);self.assertEqual(len(task['plan_draft']),2)
            self.assertEqual(b.read_project_files(task['id']),{})
        with patch.object(executor,'execute',side_effect=self.run_coding) as execute:
            self.assertEqual(self.h.call(self.h.path+'/coding/plan-decision',{'choice':'approve','request_id':'approve','expected_plan':task['plan_draft']})[0],202)
            task=self.h.wait()
            self.assertEqual(task['step'],0)
            self.assertEqual(task['coding_workflow']['checkpoints'][0]['status'],'executed_pending_review')
            self.assertEqual(task['coding_workflow']['checkpoints'][1]['status'],'pending')
            self.assertEqual(len(task['plan']),2);self.assertIn('src/main.js',b.read_project_files(task['id']))
            self.assertEqual(self.h.call(self.h.path+'/coding/messages',{'message':'继续'})[0],400)
            self.assertEqual(execute.call_count,1)

    def test_failed_write_cannot_be_reported_as_completed(self):
        def failed(files,packet,*args):
            return {'text':'所有文件已经完成','files':files,'events':[{'type':'tool_use','part':{'tool':'write','state':{'status':'error','error':'unavailable'}}}]}
        with patch.object(executor,'execute',side_effect=failed):
            self.h.call(self.h.path+'/coding/messages',{'message':'按计划创建 src/main.js'})
            task=self.h.wait()
        self.assertEqual(task['coding_run']['status'],'failed');self.assertEqual(task['step'],0)
        self.assertFalse(any(m.get('content')=='所有文件已经完成' for m in task['messages']))

    def test_actual_changes_with_failed_edit_are_saved_for_student_review(self):
        def partial(files,packet,*args):
            return {'text':'已写入，仍需检查。','files':{**files,'src/main.js':'const value = 1;'},
                    'events':[{'part':{'tool':'edit','state':{'status':'error','error':'No changes to apply: oldString and newString are identical.'}}}]}
        with patch.object(executor,'execute',side_effect=partial):
            self.h.call(self.h.path+'/coding/messages',{'message':'按计划创建 src/main.js'})
            task=self.h.wait()
        self.assertEqual(task['coding_run']['status'],'completed')
        self.assertEqual(task['step'],0)
        self.assertEqual(task['coding_workflow']['checkpoints'][0]['status'],'executed_pending_review')
        self.assertIn('src/main.js',b.read_project_files(task['id']))
        self.assertEqual(task['messages'][-1]['execution_warnings'][0]['tool'],'edit')

    def test_explicit_discussion_stays_read_only(self):
        for instruction in ('先讨论如何创建 src/main.js，不要写代码','修改开发计划','如何创建JS文件？','请给出开发计划'):
            self.assertEqual(coding_workflow.message_intent(instruction),'discuss')
        self.assertEqual(coding_workflow.message_intent('按计划创建 main.js'),'execute')

    def test_rename_delete_and_write_failure_rollback(self):
        task=b.load(self.h.task['id'])
        root=b.project(task['id'])
        b.write_project_file(root/'old.js','old')
        b.apply_coding_files(task,{'old.js':'old'},{'src/new.mjs':'new'},'重命名')
        self.assertFalse((root/'old.js').exists());self.assertEqual((root/'src/new.mjs').read_text(),'new')
        self.assertTrue(next(c for c in task['changes'] if c['file']=='old.js')['deleted'])
        before=b.read_project_files(task['id']);writer=b.write_project_file
        def fail(path,content):
            if path.name=='z.js':raise OSError('simulated write failure')
            writer(path,content)
        with patch.object(b,'write_project_file',side_effect=fail):
            with self.assertRaises(OSError):
                b.apply_coding_files(task,before,{'src/new.mjs':'changed','z.js':'fail'},'修改')
        self.assertEqual(b.read_project_files(task['id']),before)

    def test_project_config_types_allowed_and_external_paths_stay_blocked(self):
        for name in ('src/main.js','src/main.mjs','src/types.d.ts','db/schema.sql','.gitignore','package.json','Dockerfile','.env.example','.env','node_modules/pkg/main.js','.git/config','.settings/custom.xyz'):
            self.assertTrue(project_files.allowed(name),name)
        for name in ('../outside.js','C:/outside.js','C:outside.js','/outside.js'):
            self.assertFalse(project_files.allowed(name),name)


class ExecutorFilePermissionTests(unittest.TestCase):
    def test_confirmed_execution_can_create_nested_js_without_command_permissions(self):
        def run(command,**options):
            config=json.loads(options['env']['OPENCODE_CONFIG_CONTENT'])
            permission=config['permission']
            for tool in ('edit','write','patch','apply_patch'):
                self.assertEqual(permission[tool],'allow')
            self.assertEqual(permission['*'],'deny')
            self.assertEqual(permission['external_directory'],'deny')
            self.assertNotIn('--auto',command)
            path=Path(options['cwd'])/'src/main.js';path.parent.mkdir();path.write_text('console.log(1)',encoding='utf-8')
            return subprocess.CompletedProcess(command,0,json.dumps({'type':'text','part':{'text':'已创建'}}),'')
        with patch.object(executor,'CONFIG',{'key':'test-secret','model':'test','url':'https://example.invalid'}),patch.object(executor,'binary',return_value='fake'),patch.object(executor.subprocess,'run',side_effect=run):
            self.assertIn('src/main.js',executor.execute({}, {})['files'])

    def test_planning_write_candidate_is_rejected_even_if_tool_ignores_permission(self):
        def run(command,**options):
            self.assertEqual(json.loads(options['env']['OPENCODE_CONFIG_CONTENT'])['permission']['write'],'deny')
            (Path(options['cwd'])/'main.js').write_text('unexpected',encoding='utf-8')
            return subprocess.CompletedProcess(command,0,json.dumps({'type':'text','part':{'text':'done'}}),'')
        with patch.object(executor,'CONFIG',{'key':'test-secret','model':'test','url':'https://example.invalid'}),patch.object(executor,'binary',return_value='fake'),patch.object(executor.subprocess,'run',side_effect=run):
            with self.assertRaisesRegex(ValueError,'不能修改'):
                executor.execute({}, {}, planning=True)


if __name__=='__main__':unittest.main()
