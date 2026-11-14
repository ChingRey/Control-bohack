"""Structured application experiment. Backend owns stages and evidence."""
from . import benchmark as b, rubric, experiment_decide, teach
from uuid import uuid4


def create(task, learner_id, cohort, arm):
    return {
        'id':uuid4().hex, 'task_id':task['id'],
        'project':{'title':task['title'],'plan':list(task['plan']),
                   'checkpoint_id':task['benchmark_checkpoint_id']},
        'learner_id':learner_id, 'cohort':cohort, 'arm':arm,
        'stage':'pre','revision':0,'evidence':{},'evaluations':{},'events':[],
        'skill_id':b.SKILL,'topic':b.TOPIC,'task_type':b.TASK_TYPE,'difficulty':b.DIFFICULTY,
        'benchmark_version':b.VERSION,'mastery_threshold':b.threshold(),
    }


def apply(s, submitted, choose, personal):
    stage=s['stage']
    if stage == 'complete':
        raise ValueError('本次考核已完成')
    if submitted.get('stage') != stage or submitted.get('revision') != s.get('revision',0):
        raise ValueError('考核阶段已变化，请刷新后重新提交')
    hints=max((event['hint_level'] for event in s['events'] if event['phase']!='independent'),default=0)
    obs=b.observe(s['id'],stage,submitted,hints if stage=='practice' else 0)
    if not obs['answers'] and not any(v is not None for v in obs['predictions']):
        raise ValueError('请至少提交一项可观察的作答')
    result=rubric.evaluate(obs, minimum=s['mastery_threshold'],
                                         linked_turn=s['events'][-1]['id'] if s['events'] else None)
    s['evidence'].setdefault(stage,[]).append(obs)
    s['evaluations'].setdefault(stage,[]).append(result)
    if stage=='pre':
        if result['core_score'] is None:
            raise ValueError('前测需填写全部标准问题与前三项预期')
        s['student_level']='novice' if result['core_score']<75 else 'ready'
        strategy, reason, validated=choose(s)
        s['decision']=experiment_decide.choose(s,result,personal,validated)
        s['strategy'],s['selection_reason']=strategy,reason
        s['events']=teach.start(s)
        s['stage']='practice'
    elif stage=='practice':
        step=teach.after_feedback(s,result,remediate=len(s['evidence']['practice'])<2)
        s['events'].append(step)
        if step['phase']=='independent':
            s['stage']='post'
    elif stage=='post':
        s['stage']='transfer'
    elif stage=='transfer':
        s['result']=rubric.evaluate(s['evidence']['post'][0],obs,s['mastery_threshold'],
                                                   linked_turn=s['events'][-1]['id'])
        s['stage']='complete'
    s['revision']=s.get('revision',0)+1
    return s


def view(s):
    data={k:s[k] for k in ('id','stage','cohort','arm','benchmark_version')}
    data['revision']=s.get('revision',0)
    if s['stage'] in ('practice','complete'):
        data['events']=s['events']
    if s['stage']!='complete':
        data['form']=b.form(s['stage'])
    if 'decision' in s:
        data['decision']=s['decision']
        data['checkpoint_id']=s['project'].get('checkpoint_id')
    if s['stage']=='practice':
        data['feedback']=[{'weaknesses':e['weaknesses'],'missing':e['missing'],'evaluation_id':e['evaluation_id']}
                          for e in s['evaluations'].get('practice',[])]
        data['practice_checks']=[obs['checks'] for obs in s['evidence'].get('practice',[])]
    if s['stage']=='complete':
        data['result']=s['result']
        data['evidence']=s['evidence']
        data['pre']=s['evaluations']['pre'][0]
    return data
