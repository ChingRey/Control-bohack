"""Run the existing batch simulation in a separate process and database."""
import json
import os
import sqlite3
import subprocess
import sys
import threading
from uuid import UUID, uuid4

from . import benchmark_registry, strategy_library

_LOCK = threading.Lock()
_ACTIVE = {}


def status(data_root, *, include_board=False):
    root = data_root / 'strategy-simulations'
    marker = root / 'latest.json'
    if not marker.is_file():
        return {'state': 'idle'}
    run_id = json.loads(marker.read_text(encoding='utf-8'))['id']
    folder = root / UUID(hex=run_id).hex
    info = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
    progress = folder / 'progress.json'
    summary = json.loads(progress.read_text(encoding='utf-8')) if progress.is_file() else {}
    process = _ACTIVE.get(folder)
    if (folder / 'report.json').is_file():
        info['state'] = 'completed'
    elif process is not None and process.poll() is None:
        info['state'] = 'running'
    else:
        info.update(state='failed', error='模拟未完成。请重新运行，或由负责人检查本机运行日志。')
    users, returns = info.get('users',50), info.get('return_visits',5)
    info.update(users=users,return_visits=returns,target=users+returns,
                completed=summary.get('completed',0),active=summary.get('active'),
                recent=summary.get('recent',[]),phase=summary.get('phase','starting'))
    info.setdefault('benchmark_version',benchmark_registry.get().VERSION)
    if include_board and info['state'] == 'completed':
        db = folder / 'records.sqlite3'
        c = sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)
        try:
            info['board'] = strategy_library.dashboard(c,'simulation',info['benchmark_version'])
        finally:
            c.close()
    return info


def start(data_root, repository, scenario, users=50, return_visits=None, benchmark_version=None):
    if scenario not in ('responsive', 'neutral'):
        raise ValueError('请选择模拟条件')
    suite=benchmark_registry.get(benchmark_version)
    if type(users) is not int or not 1<=users<=200:
        raise ValueError('模拟人数须为 1～200 的整数')
    if return_visits is None:
        return_visits=min(5,users)
    if type(return_visits) is not int or not 0<=return_visits<=users:
        raise ValueError('回访轮数须在 0 到模拟人数之间')
    with _LOCK:
        previous = status(data_root)
        if previous['state'] == 'running':
            return previous
        for folder, child in list(_ACTIVE.items()):
            if child.poll() is not None:
                del _ACTIVE[folder]
        root = data_root / 'strategy-simulations'
        run_id = uuid4().hex
        folder = root / run_id
        folder.mkdir(parents=True)
        info={'id':run_id,'scenario':scenario,'state':'running','users':users,
              'return_visits':return_visits,'benchmark_version':suite.VERSION}
        (folder / 'run.json').write_text(json.dumps(info), encoding='utf-8')
        env = {**os.environ, 'CONTROL_WORKBENCH_DATA': str(folder), 'TEACHING_MODE': 'sample'}
        for key in tuple(env):
            if 'API_KEY' in key or key == 'CONTROL_V021_ACCESS_TOKEN':
                env.pop(key)
        with (folder / 'run.log').open('wb') as log:
            child = subprocess.Popen(
                [sys.executable, '-X', 'utf8', str(repository/'scripts/simulate_teaching_evolution.py'),
                 '--out',str(folder),'--scenario',scenario,'--users',str(users),
                 '--return-visits',str(return_visits),'--benchmark',suite.VERSION],
                cwd=repository, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        _ACTIVE[folder] = child
        temporary = root / 'latest.tmp'
        temporary.write_text(json.dumps({'id': run_id}), encoding='utf-8')
        temporary.replace(root / 'latest.json')
        return {**info, 'completed':0,'target':users+return_visits,'recent':[],'phase':'starting'}
