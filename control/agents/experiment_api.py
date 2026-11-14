"""HTTP-facing storage and orchestration for the teaching benchmark."""
import json
import os
from . import benchmark, student_library, strategy_library as library, teaching_trial


def begin(c, task, body, current_code_hash):
    profile=body.get('profile_id')
    cohort=body.get('cohort','human')
    arm=body.get('arm','default')
    if cohort not in ('human','simulation') or arm not in ('default','baseline','candidate'):
        raise ValueError('请选择有效的试验模式')
    if cohort=='simulation' and os.getenv('CONTROL_ALLOW_SIMULATION')!='1':
        raise ValueError('默认数据库不接受模拟试验')
    if not isinstance(profile,str):
        raise ValueError('请从本机学生档案中选择参与者')
    student_library.read(c,profile)
    checkpoint_id=task.get('benchmark_checkpoint_id')
    checkpoint=next((item for item in task.get('coding_checkpoints',[])
                     if item['checkpoint_id']==checkpoint_id),None)
    if checkpoint is None:
        raise ValueError('请从进化面板新建待办输入教学示例')
    if checkpoint['project_evidence']['code_hash']!=current_code_hash:
        raise ValueError('待办示例代码已修改，请重新新建教学试验')
    if load(c,task['id']):
        raise ValueError('当前项目已有教学试验，请继续当前试验或另建项目')
    session=teaching_trial.create(task,profile,cohort,arm)
    c.execute("INSERT INTO teaching_experiments VALUES (?,?,?,?)",
              (session['id'],task['id'],profile,library.encode(session)))
    return teaching_trial.view(session)


def load(c, task_id):
    row=c.execute("SELECT body FROM teaching_experiments WHERE task_id=?",(task_id,)).fetchone()
    return json.loads(row[0]) if row else None


def personal(c, learner_id, cohort):
    rows=c.execute("SELECT body FROM teaching_experiments WHERE learner_id=? ORDER BY rowid DESC",(learner_id,))
    records={}
    for raw, in rows:
        s=json.loads(raw)
        if s['stage']=='complete' and s['cohort']==cohort and s['skill_id'] not in records:
            records[s['skill_id']]={'evaluation_id':s['result']['evaluation_id'],'mastered':s['result']['mastered'],
                                    'weaknesses':s['result']['weaknesses'],'benchmark_version':s['benchmark_version'],
                                    'evidence_sufficiency':s['result']['evidence_sufficiency']}
    return records


def submit(c, task, body):
    s=load(c,task['id'])
    if not s:
        raise ValueError('请先开始教学试验')
    packet=personal(c,s['learner_id'],s['cohort']).get(benchmark.SKILL,{})
    teaching_trial.apply(s,body,lambda trial:library.select(c,trial),packet)
    if s['stage']=='complete':
        library.finish(c,s)
    c.execute("UPDATE teaching_experiments SET body=? WHERE id=?",(library.encode(s),s['id']))
    return teaching_trial.view(s)
