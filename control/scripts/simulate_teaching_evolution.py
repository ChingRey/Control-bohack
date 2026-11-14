"""Exercise strategy evolution through real HTTP and isolated SQLite."""
import argparse
import csv
import json
import os
from pathlib import Path

from demo_teaching_evolution import backend, http_server
from agents import benchmark, benchmark_registry
from simulated_learners import make_learner, simulated_answer


def persist(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)


def statuses(board):
    return {v['version']:v['status'] for v in board['versions']}


def next_arm(board, index):
    if not any(x['status'] in ('candidate','testing') for x in board['versions']):
        return 'default'
    # Alternate enrollment once a candidate is available. The backend decides
    # whether the learner actually matches a candidate or the current strategy.
    return 'candidate' if index % 2 == 0 else 'baseline'


def run_student(request, learner, scenario, arm, profile, version, on_stage):
    task = request('/api/tasks',{'scenario':'strategy-trial','benchmark_version':version})
    path = f"/api/tasks/{task['id']}/teaching/experiment"
    stage = request(path,{'profile_id':profile,'cohort':'simulation','arm':arm})
    teaching = {}
    while stage['stage']!='complete':
        on_stage(stage)
        if stage['stage']=='practice':
            teaching = stage
        payload = simulated_answer({**stage,'events':teaching.get('events',[])},learner,scenario)
        stage = request(path+'/submit',payload)
    return stage


def row_from(board, outcome, index, arm, repeat=False):
    result = next(r for v in board['versions'] for r in v['results'] if r['trial_id']==outcome['id'])
    remediation = [step['feedback_id'] for step in result['executed_steps'] if step['phase']=='remediation']
    return {
        'student': index, 'repeat_visit':repeat, 'trial_id':result['trial_id'],
        'checkpoint_id':result['checkpoint_id'], 'requested_arm':arm,'strategy_version':result['version'],
        'strategy_status_during_teaching':result['strategy_status_at_teach'],'eligible':result['eligible'],
        'pre_score':result['pre_score'],'post_score':result['post_score'],'gain':result['gain'],
        'transfer_pass':result['transfer_passed'],'test_pass':result['test_passed'],
        'hints':result['hint_burden'],'evaluation_id':result['evaluation_id'],
        'personal_evaluation_ref':outcome['decision']['personal_evaluation_ref'],
        'shared_experience_ref':result['experience_ref'],
        'remediation_evaluation':remediation[0] if remediation else None,
    }


def run(output, users, return_visits, seed, scenario, min_pairs, benchmark_version=benchmark.VERSION):
    db=output/'records.sqlite3'
    if db.exists():
        raise ValueError('输出目录已包含数据库，请使用新目录')
    output.mkdir(parents=True,exist_ok=True)
    backend.DATA,backend.DB=output,db
    os.environ['CONTROL_ALLOW_SIMULATION']='1'
    os.environ['CONTROL_SIMULATION_MIN_PAIRS']=str(min_pairs)
    rows, changes, profiles = [], [], []
    target=users+return_visits
    suffix='?benchmark='+benchmark_version

    def summary(request):
        return request('/api/teaching/strategy-trials/simulation'+suffix)

    def progress(phase, active=None):
        persist(output/'progress.json',{'completed':len(rows),'target':target,'phase':phase,'active':active,
                'recent':rows[-6:][::-1],'transitions':changes})

    progress('starting')
    with http_server() as request:
        board=summary(request)
        for index in range(1,users+return_visits+1):
            repeat=index>users
            ordinal=index-users if repeat else index
            def on_stage(st):
                progress('trial',{'index':index,'student':ordinal,'repeat_visit':repeat,'stage':st['stage'],
                         'strategy_version':st.get('events',[{}])[0].get('strategy_version') if st.get('events') else None})
            progress('trial',{'index':index,'student':ordinal,'repeat_visit':repeat,'stage':'setup'})
            if repeat:
                profile=profiles[ordinal-1]
            else:
                profile=request('/api/students',{'name':f'模拟用户 {ordinal:02d}'})['id']
                profiles.append(profile)
            learner=make_learner(seed,ordinal)
            arm='default' if repeat else next_arm(board,index)
            before=statuses(board)
            result=run_student(request,learner,scenario,arm,profile,benchmark_version,on_stage)
            board=summary(request)
            row=row_from(board,result,ordinal,arm,repeat)
            rows.append(row)
            if repeat and (row['eligible'] or row['personal_evaluation_ref']!=rows[ordinal-1]['evaluation_id']):
                raise ValueError('重复档案应读取个人记忆，但不得成为第二个验证样本')
            for version,status in statuses(board).items():
                if status!=before.get(version):
                    changes.append({'visit':index,'trial_id':row['trial_id'],'version':version,'status':status})
            progress('between_trials')
            print(f"[{index}/{users+return_visits}] v{row['strategy_version']} {row['strategy_status_during_teaching']} "
                  f"gain={row['gain']} library={statuses(board)}",flush=True)
        if request('/api/teaching/strategy-trials'+suffix)['trial_count']!=0:
            raise ValueError('模拟结果进入了真人策略库')
    progress('checking')
    with http_server() as request:
        stored=summary(request)
        if stored!=board:
            raise ValueError('服务重开后的策略库与运行结束时不一致')
    recalls=[r for r in rows if r['shared_experience_ref'] and r['strategy_status_during_teaching']=='validated']
    validated=[v for v in stored['versions'] if any(h['status']=='validated' for h in v['history'])]
    if benchmark_version==benchmark.VERSION and scenario=='responsive' and users>=50 and min_pairs<=5 and seed==20261114:
        if not validated or not recalls:
            raise ValueError('默认响应实验没有完成候选晋升和后续回读，请检查报告')
    with (output/'trials.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    data={'mode':'simulation','response_model':scenario,'seed':seed,'unique_students':len(set(profiles)),
          'repeat_visits':return_visits,'benchmark_version':benchmark_version,'min_pairs':min_pairs,'human_trials':0,
          'shared_strategy_recalls':len(recalls),'personal_memory_hits':sum(bool(r['personal_evaluation_ref']) for r in rows),
          'remediation_count':sum(bool(r['remediation_evaluation']) for r in rows),
          'latest_statuses':statuses(stored),'transitions':changes,'dashboard':stored,
          'scope':'Synthetic student answers. Mechanism and evidence tracing only.'}
    progress('complete')
    persist(output/'report.json',data)
    text=['# 教学进化批量模拟', '',
          f'参与者 **{users}** · 回访 **{return_visits}** · 补练 **{data["remediation_count"]}**',
          f'个人记忆命中 **{data["personal_memory_hits"]}** · 已验证策略回读 **{len(recalls)}**',
          f'随机种子 {seed} · 响应模型 {scenario} · 模拟验证需要 {min_pairs} 组对照',
          '', '| 完成次序 | 策略 | 状态 |','|---:|---|---|']
    text.extend(f'| {t["visit"]} | v{t["version"]} | {t["status"]} |' for t in changes)
    text += ['', '个体结果见 trials.csv，候选来源、配对证据及评分见 report.json。脚本答卷用于验证策略机制。']
    (output/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(output/'report.json',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--users',type=int,default=50)
    parser.add_argument('--return-visits',type=int,default=5)
    parser.add_argument('--seed',type=int,default=20261114)
    parser.add_argument('--scenario',choices=('responsive','neutral'),default='responsive')
    parser.add_argument('--min-pairs',type=int,default=5)
    parser.add_argument('--benchmark',choices=tuple(benchmark_registry.REGISTRY),default=benchmark.VERSION)
    args=parser.parse_args()
    if not 1<=args.users<=1000 or not 0<=args.return_visits<=args.users or not 1<=args.min_pairs<=500:
        parser.error('人数须为 1～1000，回访数不能超过人数，配对数须为 1～500')
    run(args.out.resolve(),args.users,args.return_visits,args.seed,args.scenario,args.min_pairs,args.benchmark)
