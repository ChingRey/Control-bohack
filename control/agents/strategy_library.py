"""SQLite strategy versions and anonymized experiment results."""
import hashlib
import json
from . import benchmark as b, evolve, teach

FAMILY = 'input-boundary'


def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def initialize(c):
    c.execute("""CREATE TABLE IF NOT EXISTS teaching_experiments (
        id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE, learner_id TEXT NOT NULL, body TEXT NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS teaching_experiments_learner ON teaching_experiments(learner_id)")
    c.execute("""CREATE TABLE IF NOT EXISTS strategy_library (
        cohort TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL,
        PRIMARY KEY(cohort,version))""")
    c.execute("""CREATE TABLE IF NOT EXISTS strategy_status_history (
        id INTEGER PRIMARY KEY, cohort TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS strategy_experiment_results (
        cohort TEXT NOT NULL, trial_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
        PRIMARY KEY(cohort,trial_id))""")
    c.execute("CREATE INDEX IF NOT EXISTS strategy_results_version ON strategy_experiment_results(cohort,version)")


def _insert(c, cohort, version, status, definition):
    raw=encode(definition)
    c.execute("INSERT INTO strategy_library VALUES (?,?,?,?,?)",
              (cohort,version,status,raw,hashlib.sha256(raw.encode()).hexdigest()))
    _record(c,cohort,version,status,{'reason':'登记初始策略' if version==1 else '由后测证据提出，等待试用'})


def _record(c, cohort, version, status, detail):
    c.execute("INSERT INTO strategy_status_history(cohort,version,status,detail) VALUES (?,?,?,?)",
              (cohort,version,status,encode(detail)))


def _status(c, cohort, version, status, detail):
    c.execute("UPDATE strategy_library SET status=? WHERE cohort=? AND version=?",(status,cohort,version))
    _record(c,cohort,version,status,detail)


def load(c, cohort, version):
    row=c.execute("SELECT status,body,digest FROM strategy_library WHERE cohort=? AND version=?",(cohort,version)).fetchone()
    if not row:
        return None
    status,raw,digest=row
    if hashlib.sha256(raw.encode()).hexdigest()!=digest:
        raise ValueError('策略正文与版本哈希不符')
    return {'id':FAMILY,'version':version,'status':status,'definition_hash':digest,**json.loads(raw)}


def _matches(item, session):
    return all(session.get(k)==v for k,v in item.get('applicable_conditions',{}).items())


def select(c, session):
    cohort=session['cohort']
    base=load(c,cohort,1)
    conditions={k:session[k] for k in ('skill_id','topic','task_type','difficulty','benchmark_version')}
    if base is None:
        _insert(c,cohort,1,'baseline',{**teach.BASE,'applicable_conditions':conditions})
        base=load(c,cohort,1)
    rows=c.execute("SELECT version FROM strategy_library WHERE cohort=? ORDER BY version DESC",(cohort,)).fetchall()
    strategies=[load(c,cohort,v) for v, in rows]
    active=next((x for x in strategies if x['status']=='validated' and _matches(x,session)),base)
    # A participant can contribute only one comparable result per cohort and scope.
    participant=_participant(session)
    previously_measured=any(x['participant']==participant and all(x.get(k)==session.get(k) for k in conditions)
                            for x in _results(c,cohort))
    candidate=next((x for x in strategies if x['status'] in ('candidate','testing') and _matches(x,session)
                    and x['parent_version']==active['version']),None)
    if session['arm']=='candidate' and candidate and not previously_measured:
        if candidate['status']=='candidate':
            _status(c,cohort,candidate['version'],'testing',{'trial_id':session['id'],'reason':'明确选择参加候选试用'})
            candidate['status']='testing'
        selected, reason=candidate,'试用已登记的候选版本'
    elif session['arm']=='baseline' and candidate and not previously_measured:
        selected, reason=active,'继续收集当前策略的可比基线'
    else:
        selected, reason=active,'使用已验证的匹配策略' if active['version']!=1 else '使用初始策略'
    history={'focus':active['focus'],'ref':f"{FAMILY}:v{active['version']}"} if active['status']=='validated' else {}
    if session['arm']=='candidate' and selected['status']!='testing':
        reason+='；当前没有适用且可比较的候选，本次仍使用现行策略'
    return selected,reason,history


def _participant(s):
    return hashlib.sha256((s['cohort']+':'+s['learner_id']).encode()).hexdigest()


def _results(c,cohort,version=None):
    if version is None:
        rows=c.execute("SELECT body FROM strategy_experiment_results WHERE cohort=? ORDER BY rowid",(cohort,))
    else:
        rows=c.execute("SELECT body FROM strategy_experiment_results WHERE cohort=? AND version=? ORDER BY rowid",(cohort,version))
    return [json.loads(row[0]) for row in rows]


def _measurement(s):
    pre, post, strategy = s['evaluations']['pre'][0], s['result'], s['strategy']
    count={str(i):sum(e['hint_level']==i for e in s['events']) for i in range(4)}
    observed = {stage:{'evidence_id': s['evidence'][stage][0]['id'],
                        'prediction_count': sum(v is not None for v in s['evidence'][stage][0]['predictions']),
                        'failed_cases': [i for i,row in enumerate(s['evidence'][stage][0]['checks']) if not row['passed']]}
                for stage in ('pre','post','transfer')}
    return {'observed':observed,'scores':post['scores'],**{k:s[k] for k in ('skill_id','topic','task_type','difficulty','student_level','benchmark_version','mastery_threshold','arm')},
            'trial_id':s['id'],'checkpoint_id':s['project'].get('checkpoint_id'),'participant':_participant(s),'version':strategy['version'],
            'strategy_status_at_teach':strategy['status'],'strategy_hash':strategy['definition_hash'],
            'decision_id':s['decision']['decision_id'],'experience_ref':s['decision']['experience_ref'],
            'proposal_evaluation_ref':strategy.get('source_evaluation_id'),
            'pre_score':pre['core_score'],'post_score':post['core_score'],'total_score':post['total_score'],
            'gain':round(post['core_score']-pre['core_score'],2) if post['core_score'] is not None else None,
            'transfer_passed':post['transfer_passed'],'transfer_level':post['scores']['transfer']['level'],
            'test_passed':post['test_passed'],'mastered':post['mastered'],'weaknesses':post['weaknesses'],
            'evaluation_id':post['evaluation_id'],'evidence_ids':post['evidence_ids'],
            'hint_distribution':count,'hint_burden':sum(int(k)*n for k,n in count.items()),
            'executed_steps':[{'id':e['id'],'step':e['actual_strategy_used']['step_id'],'phase':e['phase'],
                               'prompt':e['prompt'],'feedback_id':e['feedback_evaluation_id']} for e in s['events']]}


def finish(c,s):
    cohort, version=s['cohort'], s['strategy']['version']
    measurement=_measurement(s)
    previous=_results(c,cohort)
    comparable = not any(
        prior['participant']==measurement['participant'] and prior['benchmark_version']==measurement['benchmark_version']
        and prior['gain'] is not None and prior['transfer_level'] is not None
        for prior in previous)
    measurement['eligible']=comparable and measurement['gain'] is not None and measurement['transfer_level'] is not None
    c.execute("INSERT INTO strategy_experiment_results VALUES (?,?,?,?)",(cohort,s['id'],version,encode(measurement)))
    status=load(c,cohort,version)['status']
    if status in ('baseline','validated') and measurement['eligible']:
        proposed=evolve.propose(s)
        if proposed:
            existing=[load(c,cohort,v) for v, in c.execute("SELECT version FROM strategy_library WHERE cohort=?",(cohort,))]
            duplicate=any(x.get('parent_version')==version and x.get('focus')==proposed['focus']
                          and x.get('applicable_conditions')==proposed['applicable_conditions'] for x in existing)
            if not duplicate:
                new_version=1+max(x['version'] for x in existing)
                _insert(c,cohort,new_version,'candidate',proposed)
                s['created_candidate']=new_version
    # A baseline may arrive after a candidate. Recheck matching open comparisons in either case.
    for v, in c.execute("SELECT version FROM strategy_library WHERE cohort=? AND status='testing'",(cohort,)).fetchall():
        item=load(c,cohort,v)
        scope=item['applicable_conditions']
        def accepted(row):
            return row['eligible'] and all(row.get(k)==value for k,value in scope.items())
        base=[x for x in _results(c,cohort,item['parent_version']) if accepted(x)]
        tested=[x for x in _results(c,cohort,v) if accepted(x) and x['strategy_status_at_teach']=='testing'
                and any(step['phase']=='lesson' and step['prompt']==item['proposed_adjustment']
                        for step in x['executed_steps'])]
        outcome=evolve.compare(base,tested,item['validation_plan'])
        if outcome['status'] in ('validated','rejected'):
            _status(c,cohort,v,outcome['status'],outcome)
            if outcome['status']=='validated' and item['parent_version']!=1:
                parent=load(c,cohort,item['parent_version'])
                if parent['applicable_conditions']==scope:
                    _status(c,cohort,parent['version'],'retired',{'replacement':v})
    return measurement


def dashboard(c,cohort):
    results=_results(c,cohort)
    versions=[]
    for version, in c.execute("SELECT version FROM strategy_library WHERE cohort=? ORDER BY version",(cohort,)):
        row=load(c,cohort,version)
        row['history']=[{'status':status,**json.loads(detail)} for status,detail in c.execute(
            "SELECT status,detail FROM strategy_status_history WHERE cohort=? AND version=? ORDER BY id",(cohort,version))]
        row['results']=[{k:v for k,v in x.items() if k!='participant'} for x in results if x['version']==version]
        row['sample_count']=len(row['results'])
        versions.append(row)
    sessions=[s for raw, in c.execute("SELECT body FROM teaching_experiments")
              if (s:=json.loads(raw))['cohort']==cohort and s.get('events')]
    for row in versions:
        row['execution_count']=sum(s['strategy']['version']==row['version'] for s in sessions)
    completed=len(results)
    started=len(sessions)
    return {'cohort':cohort,'versions':versions,'trial_count':completed,'started_count':started,
            'validated_count':sum(x.get('parent_version') is not None and x['status'] in ('validated','retired') for x in versions)}
