"""Propose and validate teaching strategies using completed benchmark trials."""
import os

def propose(trial, history=()):
    """One concrete hypothesis, justified by independent outcomes and actual steps."""
    from .teach import materials
    from .benchmark import VERSION
    _,adapt=materials(trial['benchmark_version'])
    result = trial['result']
    strategy = trial['strategy']
    if (strategy['status'] not in ('baseline','validated') or result['mastered']
            or result['evidence_sufficiency'] != 'sufficient'
            or not any(e['phase']=='lesson' and e['actual_strategy_used']['step_id']=='practice' for e in trial['events'])):
        return None
    focus = next((k for k in adapt if k in result['weaknesses'] and k!=strategy.get('focus')),None)
    if not focus and result['test_passed'] and not result['transfer_passed'] and strategy.get('focus')!='transfer':
        focus = 'transfer'
    if not focus:
        return None
    scope={k:trial[k] for k in ('skill_id','topic','task_type','difficulty','student_level','benchmark_version','mastery_threshold')}
    repeated=[row for row in history if row['eligible'] and all(row.get(k)==v for k,v in scope.items())
              and (focus in row['weaknesses'] if focus!='transfer' else row['test_passed'] and not row['transfer_passed'])]
    if trial['benchmark_version']!=VERSION and len({row['participant'] for row in repeated})<2:
        return None
    title, prompt = adapt[focus] if focus in adapt else ('预演独立迁移','练习结束后先合上提示，换一个未见过的表单，预测结果，再说出如何核实。')
    change = {'id':'practice','stage':'引导实践 · '+title,'prompt':prompt,'hint':1}
    sequence = [change if step['id']=='practice' else step for step in strategy['sequence']]
    return {
        'parent_version':strategy['version'],'focus':focus,'sequence':sequence,
        'observation':'后测仍出现薄弱项，或标准任务通过后未能独立迁移。',
        'reflection':'把对应活动移到引导练习阶段，有机会让学生更早发现判断与运行结果的差异。',
        'possible_causes':['练习没有先让学生显式记录自己的判断','初始差异或练习熟悉度也可能解释结果'],
        'proposed_adjustment':prompt,'previous_step':strategy['sequence'][2]['prompt'],
        'applicable_conditions':scope,
        'validation_plan':{'design':'相同 Benchmark 与难度，匹配起点，不同学生；比较四维独立分数增益及迁移和提示依赖',
                           'min_pairs': int(os.getenv('CONTROL_SIMULATION_MIN_PAIRS', '1')) if trial['cohort']=='simulation' else 2, 'max_pre_gap': 10, 'min_gain_delta': 5},
        'evidence_ids':result['evidence_ids'],'source_trial_id':trial['id'],
        'source_evaluation_id':result['evaluation_id'],
        'supporting_trials':[{'trial_id':row['trial_id'],'evaluation_id':row['evaluation_id']} for row in repeated],
        'confidence':'hypothesis','validation_status':'candidate',
    }


def compare(baseline, candidate, plan):
    """Compare independent first post-tests; keep a record of failed validation."""
    used, pairs = set(), []
    for new in candidate:
        choices = [old for old in baseline if old['trial_id'] not in used
                   and old['participant']!=new['participant']
                   and abs(old['pre_score']-new['pre_score'])<=plan['max_pre_gap']]
        if not choices:
            continue
        old = min(choices,key=lambda x:abs(x['pre_score']-new['pre_score']))
        used.add(old['trial_id'])
        pairs.append({'baseline_trial_id':old['trial_id'],'candidate_trial_id':new['trial_id'],
                      'gain_delta':round(new['gain']-old['gain'],2),
                      'post_delta':round(new['post_score']-old['post_score'],2),
                      'transfer_delta':int(new['transfer_passed'])-int(old['transfer_passed']),
                      'transfer_level_delta':new['transfer_level']-old['transfer_level'],
                      'test_delta':int(new['test_passed'])-int(old['test_passed']),
                      'hint_burden_delta':new['hint_burden']-old['hint_burden']})
    summary={'pairs':pairs,'status':'testing','required_pairs':plan['min_pairs']}
    if len(pairs)<plan['min_pairs']:
        return summary
    n=len(pairs)
    good=(sum(p['gain_delta'] for p in pairs)/n >= plan['min_gain_delta']
          and sum(p['post_delta'] for p in pairs)>0
          and sum(p['transfer_delta'] for p in pairs)>=0
          and sum(p['transfer_level_delta'] for p in pairs)>0
          and sum(p['test_delta'] for p in pairs)>=0
          and sum(p['hint_burden_delta'] for p in pairs)<=0)
    return {**summary,'status':'validated' if good else 'rejected'}
