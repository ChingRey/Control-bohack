"""Withdraw shared strategies while preserving all trial evidence."""
from . import strategy_library as library


def withdraw(c, cohort, version, reason):
    if cohort not in ('simulation', 'human') or type(version) is not int or version < 2:
        raise ValueError('请选择有效的用户类型和非基线版本')
    if not isinstance(reason,str) or not 1<=len(reason.strip())<=500:
        raise ValueError('请输入回退原因（1–500 字）')
    rows = [library.load(c,cohort,v) for v, in c.execute(
        'SELECT version FROM strategy_library WHERE cohort=? ORDER BY version',(cohort,))]
    by_version = {row['version']:row for row in rows}
    target = by_version.get(version)
    if target is None or target['status'] != 'validated':
        raise ValueError('只能撤回当前已通过门槛的版本；未通过的候选会自动停止试用')
    removed = {version}
    for row in rows:
        if row.get('parent_version') in removed:
            removed.add(row['version'])
    parent = target['parent_version']
    while parent != 1 and by_version[parent]['status'] not in ('validated','retired'):
        parent = by_version[parent]['parent_version']
    for v in sorted(removed):
        if by_version[v]['status'] in ('candidate','testing','retired','validated'):
            library._status(c,cohort,v,'withdrawn',{'reason':reason.strip(),'fallback_version':parent})
    if parent != 1 and by_version[parent]['status']=='retired':
        library._status(c,cohort,parent,'validated',{'restored_from':version,'reason':reason.strip()})
    c.execute('INSERT OR REPLACE INTO strategy_fallbacks VALUES (?,?,?)',
              (cohort,library.encode(target['applicable_conditions']),parent))
    return {'withdrawn':sorted(removed),'fallback_version':parent}
