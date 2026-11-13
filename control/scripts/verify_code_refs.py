"""Offline paired citation checks; no model API or student data."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.code_refs import collect,digest
original="// header\nconst n=1;\nfunction jump(){\n return n;\n}"
refs=collect('game.js:3-5',{'game.js':original})
cases=[('unchanged',original,True),('inserted_line','// new\n'+original,False),('changed_body',original.replace('return n','return n+1'),False),('deleted_line','const n=1;',False)]
rows=[]
for name,source,expected in cases:
 old=1<=3<=len(source.split('\n'))
 new=refs[0]['valid'] and refs[0]['hash']==digest(source)
 assert new==expected
 rows.append({'case':name,'expected_precise_jump':expected,'old_accepts':old,'new_accepts':new})
assert not collect('game.js:4-99',{'game.js':original})[0]['valid']
assert not collect('missing.js:1',{'game.js':original})[0]['valid']
report={'kind':'offline deterministic mechanism comparison, not model quality','cases':rows,'old_wrong_accepts':sum(r['old_accepts']!=r['expected_precise_jump'] for r in rows),'new_wrong_accepts':sum(r['new_accepts']!=r['expected_precise_jump'] for r in rows),'extra_checks':['range end rejected','missing file rejected']}
p=Path(__file__).resolve().parents[1]/'docs/experiments/code-reference-check.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
