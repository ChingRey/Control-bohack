import copy
import json
import os
import threading
import time
import unittest
from unittest.mock import patch
from agents import teaching_evolution as e, teaching
import backend as b
import test_checkpoints as fixture


def task():
    t={'id':'experience-test','mode':'opencode','plan':['实现计分'],'step':0,'files':{},
       'messages':[{'role':'user','channel':'teaching','content':'我不懂状态是什么意思'},
                   {'role':'assistant','channel':'teaching','content':'先看例子，分数原来是3，点击后加1变成4。'},
                   {'role':'user','channel':'teaching','content':'状态保存分数，点击会改变分数。'}]}
    s=e.state(t)
    s['loads'].append({'reply_message_id':1,'code_hash':'hash','playbook_revision':0,
                       'entries':[{'id':'seed-example','revision':1}], 'adoption_verified':False})
    return t


def evaluation():
    return {'observations':[{'dimension':'understanding','value':1,'reason':'学生解释了数据变化',
                            'quotes':[{'message_id':2,'quote':'状态保存分数，点击会改变分数。'}]}],
            'feedback':[{'entry_id':'seed-example','entry_revision':1,'outcome':'helpful','reason':'采用了具体例子且后续有解释',
                         'quotes':[{'message_id':1,'quote':'先看例子，分数原来是3，点击后加1变成4。'},
                                   {'message_id':2,'quote':'状态保存分数，点击会改变分数。'}]}]}


def reflection(kind='add'):
    return {'summary':'学生在例子后能解释，原因仍待验证。','operations':[{
        'type':kind,'target_id':'seed-example' if kind!='add' else None,'title':'比较计分前后',
        'when':'理解计分状态时','action':'用同一次点击对比分数前后，暂不引入其他概念。',
        'verify':'学生独立预测下一次分数。','limits':'已理解变量基础时使用，不认证掌握。','tags':['状态','计分'],
        'reason':'学生通过具体变化作了解释，保留为待验证策略。',
        'quotes':[{'message_id':2,'quote':'状态保存分数，点击会改变分数。'}]}]}


def result():
    return {'evaluation':evaluation(),'reflection':reflection(),'provider':{'mode':'model','provider':'fixture'}}


class ExperienceTests(unittest.TestCase):
    def test_seed_selection_modes_and_project_isolation(self):
        t=task();self.assertTrue(e.packet(t)['entries'])
        self.assertTrue(all(not r['verified'] for r in e.state(t)['entries']))
        s=e.state(t);e.manage(t,{'action':'options','mode':'off','auto':False,'expected_revision':0})
        self.assertEqual(e.packet(t)['entries'],[])
        self.assertEqual(e.state(task())['mode'],'adaptive')

    def test_validation_rejects_invented_and_teacher_only_evidence(self):
        p=e.build_review(task());v=evaluation();v['observations'][0]['quotes'][0]['quote']='invented'
        with self.assertRaises(ValueError):e.validate_evaluation(v,p)
        v=evaluation();v['observations'][0]['quotes']=[{'message_id':1,'quote':'先看例子'}]
        with self.assertRaises(ValueError):e.validate_evaluation(v,p)

    def test_feedback_requires_actual_load_and_later_student(self):
        t=task();p=e.build_review(t);v=evaluation();v['feedback'][0]['entry_revision']=99
        with self.assertRaises(ValueError):e.validate_evaluation(v,p)
        t['teaching_evolution']['loads']=[];p=e.build_review(t)
        with self.assertRaises(ValueError):e.validate_evaluation(evaluation(),p)

    def test_score_missing_is_null_and_no_duplicate_dimensions(self):
        p=e.build_review(task());value=e.validate_evaluation(evaluation(),p);scores=e.scores(value)
        self.assertEqual(scores[0]['score'],100)
        self.assertTrue(all(r['score'] is None for r in scores[1:]))
        value['observations']*=2
        with self.assertRaises(ValueError):e.validate_evaluation(value,p)

    def test_delta_forks_seed_keeps_evidence_and_versions_and_is_idempotent(self):
        t=task();p=e.build_review(t);out=result();out['reflection']=reflection('revise')
        before=copy.deepcopy(t);e.apply(t,p,out);s=e.state(t)
        self.assertEqual(s['entries'][0]['action'],before['teaching_evolution']['entries'][0]['action'])
        candidate=s['entries'][-1];self.assertEqual(candidate['status'],'trial')
        self.assertEqual(candidate['parent_id'],'seed-example');self.assertFalse(candidate['verified'])
        self.assertEqual(s['entries'][0]['helpful'],1);self.assertEqual(s['revision'],1)
        frozen=copy.deepcopy(t)
        with self.assertRaises(ValueError):e.apply(t,p,out)
        self.assertEqual(t,frozen)
        self.assertEqual(t['messages'],before['messages']);self.assertEqual(t['files'],before['files'])

    def test_bad_delta_has_no_partial_commit(self):
        t=task();p=e.build_review(t);out=result();out['reflection']['operations'][0]['quotes'][0]['message_id']=999
        before=copy.deepcopy(t)
        with self.assertRaises(ValueError):e.apply(t,p,out)
        self.assertEqual(t,before)

    def test_restore_preserves_audit_cursor_and_disables_updates(self):
        t=task();p=e.build_review(t);e.apply(t,p,result());s=e.state(t)
        e.manage(t,{'action':'restore','target_revision':0,'expected_revision':1})
        s=e.state(t);self.assertEqual(len(s['entries']),5)
        self.assertEqual(len(s['reviews']),1);self.assertEqual(s['cursor'],2)
        self.assertEqual(s['mode'],'observe');self.assertFalse(s['auto']);self.assertEqual(s['revision'],2)
        with self.assertRaises(ValueError):e.manage(t,{'action':'options','mode':'off','auto':False,'expected_revision':1})

    def test_selection_has_at_most_one_trial_and_stopped_never_loads(self):
        t=task();p=e.build_review(t);e.apply(t,p,result());selected=e.packet(t)['entries']
        self.assertEqual(len([r for r in selected if r['status']=='trial']),1)
        sid=e.state(t)['entries'][-1]['id']
        e.manage(t,{'action':'status','entry_id':sid,'status':'inactive','expected_revision':1})
        self.assertNotIn(sid,[r['id'] for r in e.packet(t)['entries']])

    def test_observe_retains_candidates_without_trialing(self):
        t=task();e.state(t)['mode']='observe';p=e.build_review(t);e.apply(t,p,result())
        sid=e.state(t)['entries'][-1]['id'];self.assertEqual(e.state(t)['entries'][-1]['status'],'candidate')
        self.assertNotIn(sid,[r['id'] for r in e.packet(t)['entries']])

    def test_two_negative_trials_stop_without_promoting_other_entries(self):
        t=task();p=e.build_review(t);e.apply(t,p,result());trial=e.state(t)['entries'][-1]
        for n in range(2):
            reply=len(t['messages']);t['messages'].extend([
                {'role':'assistant','channel':'teaching','content':'比较一下状态前后。'},
                {'role':'user','channel':'teaching','content':'还是把文字当状态，我无法区分。'}])
            e.state(t)['loads'].append({'reply_message_id':reply,'entries':[{'id':trial['id'],'revision':1}]})
            packet=e.build_review(t)
            negative={'observations':[],'feedback':[{'entry_id':trial['id'],'entry_revision':1,'outcome':'harmful',
                'reason':'夹具：已尝试但仍混淆，记录负面观察。','quotes':[
                    {'message_id':reply,'quote':'比较一下状态前后。'},
                    {'message_id':reply+1,'quote':'还是把文字当状态，我无法区分。'}]}]}
            e.apply(t,packet,{'evaluation':negative,'reflection':{'summary':'仍有混淆，暂不新增。','operations':[]}})
        current=e.state(t)['entries'][-1]
        self.assertEqual(current['status'],'inactive');self.assertEqual(current['harmful'],2)
        self.assertFalse(current['verified']);self.assertNotIn(current['id'],[r['id'] for r in e.packet(t)['entries']])

    def test_retry_gaps_are_deferred_without_blocking_later_messages(self):
        t=task();t['messages'][1]['queue_status']='needs_retry';p=e.build_review(t)
        self.assertEqual(p['through_id'],2);self.assertIn(2,[r['id'] for r in p['messages']]);self.assertEqual(p['deferred_ids'],[1])
        e.apply(t,p,{'evaluation':{'observations':[],'feedback':[]},'reflection':{'summary':'本批仅记录已送达原话。','operations':[]}})
        t['messages'][1]['queue_status']='delivered'
        retry=e.build_review(t);self.assertEqual(retry['new_message_ids'],[1])
        e.apply(t,retry,{'evaluation':{'observations':[],'feedback':[]},'reflection':{'summary':'补回重试记录。','operations':[]}})
        self.assertEqual(e.state(t)['deferred_ids'],[])
        t=task();e.state(t)['cursor']=0;t['messages'][1]['content']='x'*36001
        with self.assertRaises(ValueError):e.build_review(t)

    def test_model_calls_are_two_distinct_roles_with_validated_evaluation(self):
        t=task();p=e.build_review(t)
        with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(e,'call_model',side_effect=[evaluation(),reflection()]) as call:
            out=e.analyze(t,p)
        self.assertEqual(call.call_count,2)
        self.assertIn('evaluation',call.call_args_list[1].args[2]);e.apply(t,p,out)
        self.assertEqual(len(e.state(t)['reviews']),1)


class ExperienceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        t=b.load(self.h.task['id']);source=task();t['messages']=source['messages'];t['teaching_evolution']=source['teaching_evolution'];b.save(t)

    def wait_review(self):
        for _ in range(300):
            with b.task_lock(self.h.task['id']):t=b.load(self.h.task['id'])
            if e.state(t)['run']['status']!='running':return t
            time.sleep(.01)
        self.fail('reflection did not finish')

    def test_api_persists_review_and_restore_without_touching_code(self):
        with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(e,'analyze',return_value=result()):
            code,_=self.h.call(self.h.path+'/teaching/experience-review',{})
            self.assertEqual(code,202);t=self.wait_review()
        self.assertEqual(e.state(t)['run']['status'],'completed');self.assertEqual(len(e.state(t)['reviews']),1)
        self.assertEqual(self.h.call(self.h.path+'/teaching/experience-manage',{'action':'restore','target_revision':0,'expected_revision':1})[0],200)
        reopened=b.load(t['id']);self.assertEqual(e.state(reopened)['revision'],2)
        self.assertEqual(reopened['messages'],task()['messages']);self.assertEqual(b.read_project_files(t['id']),{})

    def test_background_accepts_append_without_overwriting_new_chat(self):
        entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def analyze(*args):entered.set();release.wait(3);return result()
        with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(e,'analyze',side_effect=analyze):
            self.h.call(self.h.path+'/teaching/experience-review',{});self.assertTrue(entered.wait(2))
            with b.task_lock(self.h.task['id']):
                t=b.load(self.h.task['id']);t['messages'].append({'role':'user','channel':'teaching','content':'new conversation'});b.save(t)
            release.set();t=self.wait_review()
        self.assertEqual(e.state(t)['run']['status'],'completed');self.assertEqual(e.state(t)['revision'],1)
        self.assertEqual(t['messages'][-1]['content'],'new conversation')

    def test_failure_preserves_state_and_sample_never_mocks_success(self):
        self.assertEqual(self.h.call(self.h.path+'/teaching/experience-review',{})[0],400)
        with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(e,'analyze',side_effect=RuntimeError('private internal error')):
            self.h.call(self.h.path+'/teaching/experience-review',{});t=self.wait_review()
        self.assertEqual(e.state(t)['run']['status'],'failed');self.assertEqual(e.state(t)['revision'],0)
        self.assertNotIn('private internal error',json.dumps(t))

    def test_restart_marks_reflection_failed_without_replaying(self):
        t=b.load(self.h.task['id']);e.state(t)['run']={'status':'running'}
        self.assertTrue(b.recover_interrupted(t));self.assertEqual(e.state(t)['run']['status'],'failed')

    def test_successful_chat_automatically_schedules_reflection_after_organizer(self):
        entered=threading.Event()
        def analyze(*args):entered.set();return result()
        with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(teaching,'project_chat',return_value='本轮讲解。'),patch.object(b.workflow_records,'organize',return_value=[]),patch.object(e,'analyze',side_effect=analyze):
            code,_=self.h.call(self.h.path+'/chat/send',{'channel':'teaching','message':'继续解释状态','request_id':'auto-reflection'})
            self.assertEqual(code,202);self.assertTrue(entered.wait(3));t=self.wait_review()
        self.assertEqual(e.state(t)['run']['status'],'completed')
        self.assertEqual(len(e.state(t)['reviews']),1)
        self.assertTrue(e.state(t)['loads'])

    def test_real_teacher_request_receives_experience_and_load_is_traced(self):
        captured=[]
        def request(config,messages,*args,**kwargs):captured.append(json.loads(messages[1]['content']));return object()
        t=b.load(self.h.task['id'])
        with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(teaching.providers,'request',side_effect=request),patch.object(teaching,'request_model',return_value={'choices':[{'message':{'content':'先看一个具体例子。'}}]}):
            self.assertEqual(teaching.run(t),'先看一个具体例子。')
        self.assertTrue(captured[0]['experience_context']['entries'])
        turn=t['teaching']['turns'][-1];self.assertTrue(turn['experience_context']['entries'])
        e.record_load(t,turn,len(t['messages']));self.assertFalse(e.state(t)['loads'][-1]['adoption_verified'])


if __name__=='__main__':unittest.main()
