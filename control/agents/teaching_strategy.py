"""Versioned pedagogy seam. Evolution proposes; this module never auto-promotes."""
import json
from pathlib import Path

DEFAULT='initial-v1'
ROOT=Path(__file__).resolve().parent/'teaching_assets/strategies'

def definition(version=DEFAULT):
    # Registry prevents runtime model text from becoming a file path or executable strategy.
    registry={DEFAULT:ROOT/'initial-v1.json'}
    if version not in registry:raise ValueError('未登记的教学策略版本')
    value=json.loads(registry[version].read_text(encoding='utf8'))
    if value.get('version')!=version or not value.get('steps'):raise ValueError('教学策略格式无效')
    return value

def packet(task):
    value=definition(task.get('teaching',{}).get('strategy_version',DEFAULT))
    return {k:value[k] for k in ('id','version','name','steps','guidance')}

def trace(value):
    return {'id':value['id'],'version':value['version'],'expected_steps':[s['id'] for s in value['steps']],
            'adherence_verified':False,'learning_effect_verified':False,'evaluation_status':'reserved_not_scored'}
