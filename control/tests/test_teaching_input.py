import copy
import json
import unittest
import os
from unittest.mock import patch
from agents import teaching, teaching_input as ti, checkpoints


class CompactTeachingInputTests(unittest.TestCase):
    def task(self):
        before = {'src/game.js':'\n'.join('const v'+str(i)+' = '+str(i)+';' for i in range(300)),
                  'unrelated.js':'// do not preload this'}
        after = dict(before)
        after['src/game.js'] = after['src/game.js'].replace('const v249 = 249;', 'const v249 = 999;')
        task = {'id':'compact','mode':'opencode','plan':['修改计分','添加音效'],'step':0,
                'files':after,'changes':[],'checks':[],
                'messages':[{'channel':'coding','role':'user','content':'做一个游戏'},
                            {'channel':'coding','role':'user','content':'修改计分'},
                            {'channel':'coding','role':'assistant','content':'已修改文件'}]}
        teaching.state(task)
        checkpoints.record(task,'cp','修改计分','已修改文件',before,after,0)
        return task

    def test_review_preloads_actual_hunk_not_first_lines_and_never_full_diff_twice(self):
        task=self.task(); ctx=teaching.context(task,'checkpoint')
        self.assertIn(250,[x['line'] for x in ctx['files']['src/game.js']])
        self.assertNotIn(1,[x['line'] for x in ctx['files']['src/game.js']])
        self.assertNotIn('unrelated.js',ctx['files'])
        self.assertNotIn('diff',ctx['checkpoint_event']['project_evidence']['changes'][0])
        self.assertNotIn('agent_output',ctx['checkpoint_event'])
        self.assertNotIn('plan_draft',ctx)

    def test_chat_has_no_automatic_source_or_checkpoint_and_keeps_current_question(self):
        task=self.task(); question='请解释这个功能。'*300
        task['messages'].append({'channel':'teaching','role':'user','content':question})
        ctx=teaching.context(task,'message')
        self.assertEqual(ctx['files'],{})
        self.assertIsNone(ctx['checkpoint_event'])
        self.assertEqual(ctx['messages'][-1]['content'],question)
        # Unloaded code remains accessible through the same read-only tool.
        result=teaching.dispatch_tool('read_project_file',{'path':'unrelated.js'},ctx,
                                     task['messages'],task['files'])
        self.assertEqual(result['lines'][0]['text'],'// do not preload this')

    def test_large_changed_file_does_not_starve_other_changed_files(self):
        task=self.task()
        after={'big.js':'\n'.join('const v'+str(i)+' = '+str(i)+';' for i in range(1000)),
               'new-test.js':'// important test\nassert(true);'}
        task['files']=after
        checkpoints.record(task,'multiple','写测试','已写',{},after,0)
        ctx=teaching.context(task,'checkpoint')
        self.assertIn('big.js',ctx['files'])
        self.assertIn('new-test.js',ctx['files'])

    def test_memory_is_hidden_and_reused_without_changing_authoritative_phase(self):
        task=self.task();ctx=teaching.context(task,'checkpoint')
        notes=[{'kind':'next_step','text':'询问学生如何验证计分','evidence_ids':[1]}]
        reply,candidate=ti.split_reply('先检查计分。<continuity_memory>'+json.dumps({'notes':notes})+'</continuity_memory>',ctx)
        self.assertEqual(reply,'先检查计分。')
        ti.remember(task,ctx,reply,candidate)
        rebuilt=teaching.context(task,'message')
        self.assertEqual(rebuilt['continuity_memory']['notes'],notes)
        self.assertEqual(rebuilt['development_scope']['acceptance_status'],'not_accepted')
        self.assertEqual(task['step'],0)

    def test_bad_memory_does_not_erase_good_memory_and_old_code_marked_stale(self):
        task=self.task();ctx=teaching.context(task,'checkpoint')
        good=[{'kind':'open_question','text':'还需确认计分','evidence_ids':[1]}]
        ti.remember(task,ctx,'先验证',good)
        old=copy.deepcopy(task['teaching']['continuity']['notes'])
        text='自然回复<continuity_memory>'+json.dumps({'notes':[{'kind':'next_step','text':'伪造来源','evidence_ids':[999]}]})+'</continuity_memory>'
        reply,notes=ti.split_reply(text,ctx)
        self.assertIsNone(notes)
        ti.remember(task,ctx,reply,notes)
        self.assertEqual(task['teaching']['continuity']['notes'],old)
        task['files']['src/game.js']+='\n// next version'
        ctx=teaching.context(task,'message')
        self.assertTrue(ctx['continuity_memory']['stale_for_code'])

    def test_plain_reply_and_broken_marker_are_not_shown_as_internal_memory(self):
        ctx=teaching.context(self.task(),'message')
        self.assertEqual(ti.split_reply('你好',ctx),('你好',None))
        self.assertEqual(ti.split_reply('你好<continuity_memory>{',ctx),('你好',None))

    def test_deleted_file_is_explicit_and_full_history_is_preserved(self):
        task=self.task(); original=copy.deepcopy(task['messages'])
        checkpoints.record(task,'delete','删除旧文件','已删除',task['files'],{},0)
        task['files']={}
        ctx=teaching.context(task,'checkpoint')
        self.assertTrue(all(x['deleted'] for x in ctx['checkpoint_event']['project_evidence']['changes']))
        self.assertEqual(task['messages'],original)
        self.assertEqual(len(task['coding_checkpoints']),2)

    def test_queued_messages_do_not_leak_into_compact_input(self):
        task=self.task()
        task['messages'].append({'channel':'teaching','role':'user','content':'future-secret-topic','queue_status':'queued'})
        ctx=teaching.context(task,'message')
        self.assertNotIn('future-secret-topic',json.dumps(ctx))
        self.assertNotIn(3,ctx['context_usage']['loaded_message_ids'])

    def test_library_methods_and_continuity_share_one_model_request(self):
        task=self.task();seen=[]
        def request(config,messages,*args,**kwargs):
            seen.append(json.loads(messages[1]['content']));return object()
        reply='请检查计分。<continuity_memory>'+json.dumps({'notes':[{'kind':'next_step','text':'询问学生怎样验证计分','evidence_ids':[1]}]})+'</continuity_memory>'
        with patch.dict(os.environ,{'TEACHING_MODE':'model','TEACHING_PROVIDER':'siliconflow','SILICONFLOW_API_KEY':'fixture'}),patch.object(teaching.providers,'request',side_effect=request),patch.object(teaching,'request_model',return_value={'choices':[{'message':{'content':reply}}]}):
            self.assertEqual(teaching.run(task,'checkpoint'),'请检查计分。')
        self.assertEqual(len(seen),1)
        self.assertTrue(seen[0]['teaching_library']['lessons'])
        self.assertTrue(seen[0]['stage_methods'])
        self.assertIn('src/game.js',seen[0]['files'])
        self.assertEqual(task['teaching']['continuity']['revision'],1)
        self.assertTrue(task['teaching']['turns'][-1]['teaching_library']['submitted_to_model'])
