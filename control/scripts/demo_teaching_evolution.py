"""Run the workbench HTTP flow against an isolated SQLite database (simulated students)."""
import argparse
import json
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend

GOOD = dict(concept=1,reason=0,order=2,failure=1,instruction=1,review=2,regression=1)
GAP = {**GOOD,'order':1,'review':0,'regression':0}
TRANSFER_GOOD = {k:GOOD[k] for k in ('order','failure','regression')}
TRANSFER_GAP = {**TRANSFER_GOOD,'order':1,'regression':0}


class QuietHandler(backend.Handler):
    def log_message(self, *_):
        pass


@contextmanager
def http_server():
    server=backend.LocalHTTPServer(('127.0.0.1',0),QuietHandler)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    def request(path, payload=None):
        kwargs={} if payload is None else {'data':json.dumps(payload).encode(),
                                           'headers':{'Content-Type':'application/json'}}
        try:
            with urlopen(Request(f'http://127.0.0.1:{server.server_port}'+path,**kwargs),timeout=8) as response:
                return json.load(response)
        except HTTPError as error:
            with error:
                raise ValueError(f'{path} ({error.code}): {json.load(error)["error"]}') from None
    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def pilot(request, arm='default', succeeds=False, profile=None, cohort='simulation'):
    profile=profile or request('/api/students',{'name':'Simulation fixture' if cohort=='simulation' else 'Test fixture'})['id']
    task=request('/api/tasks',{'scenario':'strategy-trial'})
    path='/api/tasks/'+task['id']+'/teaching/experiment'
    started=request(path,{'profile_id':profile,'cohort':cohort,'arm':arm})
    current=started
    def send(stage,answers,predictions):
        nonlocal current
        current=request(path+'/submit',{'stage':stage,'revision':current['revision'],'answers':answers,'predictions':predictions})
        return current
    weak=[True,False,True,True]
    strong=[True,False,False,False]
    first=send('pre',GAP,weak)
    next_lesson=send('practice',GOOD if succeeds else GAP,strong if succeeds else weak)
    if next_lesson['stage']=='practice':
        next_lesson=send('practice',GAP,weak)
    independent=send('post',GOOD if succeeds else GAP,strong if succeeds else weak)
    assert 'events' not in independent and independent['stage']=='transfer'
    complete=send('transfer',TRANSFER_GOOD if succeeds else TRANSFER_GAP,strong if succeeds else weak)
    assert complete['id']==started['id']==first['id']
    return complete, profile, path


def summary(request):
    return request('/api/teaching/strategy-trials/simulation')


def replay(directory):
    directory.mkdir(parents=True,exist_ok=True)
    db=directory/'records.sqlite3'
    if db.exists():
        raise ValueError('请指定没有 records.sqlite3 的新演示目录')
    backend.DATA,backend.DB=directory,db
    os.environ['CONTROL_ALLOW_SIMULATION']='1'
    with http_server() as request:
        baseline, _, _=pilot(request)
        candidate=summary(request)['versions'][-1]
        assert candidate['status']=='candidate'
        comparison, _, _=pilot(request,'candidate',succeeds=True)
        assert summary(request)['versions'][-1]['status']=='validated'
        recalled, _, _=pilot(request,succeeds=True)
        assert recalled['decision']['experience_ref'] and recalled['events'][0]['strategy_version']==2
        assert request('/api/teaching/strategy-trials')['trial_count']==0
    with http_server() as request:  # new HTTP server, same DB on disk
        view=summary(request)
    return {'mode':'simulation','scope':'controlled benchmark and application wiring, not a model or human efficacy test',
            'baseline':baseline['result'],'validation_trial':comparison['result'],
            'later_decision':recalled['decision'],'persisted_dashboard':view}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New directory for the simulation database and evidence JSON')
    output=parser.parse_args().out.resolve()
    result=replay(output)
    (output/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(output/'evidence.json')
