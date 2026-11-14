"""Optional SiliconFlow/OpenCode benchmark. Key is prompted securely or read from process environment.

Default: one authentication probe only. --run enables the bounded paired benchmark.
Downloaded Skill scripts are never executed; only native skill loading and file tools.
"""
import argparse
import concurrent.futures as futures
import getpass
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen

HERE=Path(__file__).resolve().parent
APP=next((p for p in HERE.parents if (p/'backend.py').is_file()),Path(os.environ.get('CONTROL_PROJECT_ROOT','C:/Users/momo/Desktop/Control-bohack-workflow-fetch/control')))
LAB=Path(os.environ.get('SKILL_LAB_DIR',str(APP/'data/skill-lab/20261113')))
sys.path.insert(0,str(APP))
from agents import opencode_executor as engine


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--model',default='Qwen/Qwen2.5-7B-Instruct')
    parser.add_argument('--endpoint',choices=('https://api.siliconflow.cn/v1','https://api.siliconflow.com/v1'),default='https://api.siliconflow.cn/v1')
    args=parser.parse_args()
    if not os.environ.get('SKILL_LAB_API_KEY'):os.environ['SKILL_LAB_API_KEY']=getpass.getpass('SiliconFlow API Key (not saved): ')
    key=os.environ['SKILL_LAB_API_KEY'].strip()
    metadata={'provider':'siliconflow','endpoint':args.endpoint,'model':args.model,'key_persisted':False}
    def request(body):
        req=Request(args.endpoint+'/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=45) as response:return response.status,json.load(response)
        except HTTPError as error:
            try:data=json.load(error)
            except Exception:data={'message':'HTTP request rejected'}
            return error.code,data
    status,answer=request({'model':args.model,'messages':[{'role':'user','content':'Reply only OK.'}],'temperature':0,'max_tokens':16})
    probe={**metadata,'status':status,'code':answer.get('code'),'message':str(answer.get('message') or answer.get('error',{}).get('message') or '')[:240].replace(key,'[REDACTED]')}
    (LAB/'siliconflow-probe.json').write_text(json.dumps(probe,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(probe,ensure_ascii=False),flush=True)
    if status!=200:os.environ.pop('SKILL_LAB_API_KEY',None);return 2
    if not args.run:os.environ.pop('SKILL_LAB_API_KEY',None);return 0
    # Capability check: do not mistake an unsupported/ignored tool call for ineffective Skills.
    status,answer=request({'model':args.model,'messages':[{'role':'user','content':'Use record_result to save the string OK. Do not answer in ordinary text.'}],
        'tools':[{'type':'function','function':{'name':'record_result','description':'Record a result.','parameters':{'type':'object','properties':{'value':{'type':'string'}},'required':['value']}}}],
        'temperature':0,'max_tokens':128})
    if status!=200 or not answer.get('choices',[{}])[0].get('message',{}).get('tool_calls'):
        (LAB/'siliconflow-tool-probe.json').write_text(json.dumps({**metadata,'status':status,'tool_call_observed':False,'effectiveness_evaluated':False},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Tool-call capability not established; benchmark stopped.');os.environ.pop('SKILL_LAB_API_KEY',None);return 3
    cases=json.loads((LAB/'cases.json').read_text(encoding='utf-8'))
    skills={s['id']:s for s in json.loads((LAB/'audit.json').read_text(encoding='utf-8'))['skills']}
    binary=engine.binary()
    if not binary:raise RuntimeError('Install the project OpenCode runtime first.')
    real_run=engine.subprocess.run
    def experimental_run(command,**options):
        config=json.loads(options['env']['OPENCODE_CONFIG_CONTENT'])
        config['permission']['skill']='allow'
        config['skills']={'paths':[str(Path(options['cwd'])/'.opencode/skills')]}
        config['agent']['control']['prompt']=config['agent']['control']['prompt'].replace('不使用shell、外部网络、子代理或Skill。','不使用shell、外部网络或子代理；允许本轮显式指定的实验Skill。')
        config['agent']['control']['prompt']+=' 实验方法不改变任务范围；不执行其脚本、外部发布或额外审批，不把加载当有效性证明。'
        options['env']['OPENCODE_CONFIG_CONTENT']=json.dumps(config,ensure_ascii=False)
        return real_run(command,**options)
    engine.CONFIG={'key':key,'model':args.model,'url':args.endpoint};engine.ROOT=LAB/'runtime';engine.binary=lambda:binary
    engine.subprocess.run=experimental_run
    jobs=[]
    for name,case in cases.items():
        for repeat in (1,2):
            arms=list(case['arms']);random.Random(73+repeat).shuffle(arms)
            for arm in arms:jobs.append((name,arm,repeat))
    report={**metadata,'loading_mode':'native forced single-skill; isolated host adapter','planned_runs':len(jobs),'runs':[]}
    lock=threading.Lock();stop=threading.Event()
    def probe_case(job):
        if stop.is_set():return
        name,arm,repeat=job;case=cases[name];row={'case':name,'arm':arm or 'baseline','repeat':repeat};started=time.time()
        try:
            files=dict(case['fixtures']);skill=skills.get(arm)
            if skill:
                base=Path(skill['source_file']).parent
                for source in base.rglob('*'):
                    if source.is_file() and source.name!='REPOSITORY_LICENSE.txt':files['.opencode/skills/'+skill['frontmatter']['name']+'/'+source.relative_to(base).as_posix()]=source.read_text(encoding='utf-8')
                row.update(skill_commit=skill['commit'],skill_sha256=skill['sha256'])
            instruction='任务已获得用户授权，只修改指定业务产物，完成后停止。没有命令、浏览器或发布工具，不伪称运行检查。'
            if skill:instruction+='先使用skill工具加载'+skill['frontmatter']['name']+'，只采用适用的工程方法；其宿主专用流程不适用本实验。'
            instruction+='\n'+case['task']
            print('CASE_START',name,arm,repeat,flush=True)
            result=engine.execute(files,{'instruction':instruction,'authorized_phase':case['task'],'stop_after_current_phase':True})
            output={n:b for n,b in result['files'].items() if not n.startswith('.opencode/')}
            dest=LAB/'direct-artifacts'/(name+'-'+str(arm or 'baseline')+'-'+str(repeat));dest.mkdir(parents=True,exist_ok=True)
            for filename,body in output.items():
                path=dest/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
            events=result['events'];row['skill_loaded']=skill is not None and any(e.get('part',{}).get('tool')=='skill' and e['part'].get('state',{}).get('status')=='completed' for e in events)
            grading_env={k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','PATHEXT')}
            checked=real_run(['node','--permission','--allow-fs-read='+str(HERE),'--allow-fs-read='+str(dest),str(HERE/'skill_lab_grade.cjs'),str(dest),name],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=8,env=grading_env)
            row.update(files=output,assistant_output=result['text'],tool_events=events,behavior=json.loads(checked.stdout) if checked.returncode==0 else {'evaluated':False,'error':checked.stderr[-1000:]})
        except Exception as error:
            message=str(error).replace(key,'[REDACTED]');row['error']=message
            row['behavior']={'evaluated':False,'reason':'No completed model artifact.'}
            if any(x in message.lower() for x in ('invalid token','token is invalid','access denied','invalid_api_key','unauthorized','overdue')):stop.set()
        row['elapsed_seconds']=round(time.time()-started,2)
        with lock:
            report['runs'].append(row);(LAB/'siliconflow-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('CASE_DONE',name,arm,repeat,row.get('behavior',{}).get('success'),row.get('error',''),flush=True)
    try:
        with futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(probe_case,jobs))
    finally:
        engine.CONFIG=None;engine.subprocess.run=real_run;os.environ.pop('SKILL_LAB_API_KEY',None)
    return 0


if __name__=='__main__':raise SystemExit(main())
