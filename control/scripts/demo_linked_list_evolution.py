"""Run the linked-list A → B → C acceptance through the workbench HTTP API."""
import argparse
import json
import os
from pathlib import Path

from demo_teaching_evolution import backend, http_server
from agents import linked_list_benchmark as linked

PRE = dict(head=1,duplicate=2,missing=0,tail=1,request=1,evidence=2,review=0)
WEAK = [{'values':[3,6,9],'target':6,'expected':[3,9]}]
STRONG = [
    {'values':[],'target':9,'expected':[]},
    {'values':[8],'target':8,'expected':[]},
    {'values':[1,2,3],'target':1,'expected':[2,3]},
    {'values':[4,5,6],'target':6,'expected':[4,5]},
    {'values':[7,8],'target':9,'expected':[7,8]},
    {'values':[2,3,2,4],'target':2,'expected':[3,2,4]},
    *WEAK,
]
TRANSFER = [*STRONG[:5], {'values':[4,5,4,6],'target':4,'expected':[4,5,6]},
            {'values':[9,5,7],'target':5,'expected':[9,7]}]


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    backend.DATA,backend.DB=output,output/'records.sqlite3'
    if backend.DB.exists():
        raise ValueError('演示要求一个新数据库目录')
    os.environ['CONTROL_ALLOW_SIMULATION']='1'
    os.environ['CONTROL_SIMULATION_MIN_PAIRS']='2'
    endpoint='/api/teaching/strategy-trials/simulation?benchmark='+linked.VERSION
    with http_server() as request:
        def trial(name,arm,improved):
            profile=request('/api/students',{'name':name})
            task=request('/api/tasks',{'scenario':'strategy-trial','benchmark_version':linked.VERSION})
            path='/api/tasks/'+task['id']+'/teaching/experiment'
            progress=request(path,{'profile_id':profile['id'],'cohort':'simulation','arm':arm})
            def submit(stage,cases):
                nonlocal progress
                assert progress['stage']==stage,progress['stage']
                answers={key:PRE[key] for key in ('missing','duplicate')} if stage=='transfer' else PRE
                progress=request(path+'/submit',{'stage':stage,'revision':progress['revision'],
                                                 'answers':answers,'test_cases':cases})
                return progress
            submit('pre',WEAK)
            practice=submit('practice',STRONG if improved else WEAK)
            if practice['stage']=='practice':
                assert practice['events'][-1]['phase']=='remediation'
                assert practice['events'][-1]['feedback_evaluation_id']==practice['feedback'][-1]['evaluation_id']
                submit('practice',STRONG if improved else WEAK)
            submit('post',STRONG if improved else WEAK)
            return submit('transfer',TRANSFER if improved else WEAK)
        first=trial('模拟基线 A','default',False)
        assert len(request(endpoint)['versions'])==1
        trial('模拟基线 A2','baseline',False)
        candidate=request(endpoint)['versions'][-1]
        assert candidate['status']=='candidate' and len(candidate['supporting_trials'])>=2
        trial('模拟试用 B','candidate',True)
        assert request(endpoint)['versions'][-1]['status']=='testing'
        trial('模拟试用 B2','candidate',True)
        assert request(endpoint)['versions'][-1]['status']=='validated'
        final=trial('模拟复用 C','default',True)
        assert final['decision']['experience_ref']=='linked-list-delete:v2'
        assert next(e for e in final['events'] if e['actual_strategy_used']['step_id']=='practice')['strategy_version']==2
        assert final['result']['mastered']
        assert request('/api/teaching/strategy-trials/simulation')['trial_count']==0
    with http_server() as request:
        report=request(endpoint)
    report.update({'baseline_evidence':first,'reuse_evidence':final,'validation_mode':'synthetic submissions, actual linked-list assertions'})
    (output/'linked-list-evidence.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Linked-list v1 → v2: 2 baseline trials, 2 matched trials, 1 reuse trial')
    print(output/'linked-list-evidence.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out.resolve())
