"""Deterministic rubric over benchmark evidence; ordinary chat remains provisional."""
from uuid import NAMESPACE_URL, uuid5
from . import benchmark as b


def _score(keys, obs, standards, advanced=None):
    evidence = obs['answers']
    if not all(key in evidence for key in keys):
        return None
    successes = sum(bool(v) for v in standards)
    if not successes:
        level = 0
    elif successes < len(standards):
        level = min(2, successes)
    else:
        level = 4 if advanced else 3
    return min(level, b.HINT_CAP[obs['hint_level']])


def marks(obs):
    picks = obs['answers']
    right = {k: picks.get(k) == answer for k,answer in b.EXPECTED.items()}
    predictions = obs['predictions']
    predicted = [i < len(predictions) and predictions[i] is expect for i,expect in enumerate((True,False,False,False))]
    has_predictions = len(predictions) >= 3 and all(v is not None for v in predictions[:3])
    checks = obs['checks']
    standard = bool(checks) and all(x['passed'] for x in checks[:3])
    behavior = bool(checks) and all(x['passed'] for x in checks)
    verification = (_score(('order',),obs,[predicted[0],all(predicted[1:3]),standard],
                            predicted[3] and behavior)
                    if has_predictions else None)
    if obs['stage']=='transfer':
        level = (_score(('order','failure'),obs,[predicted[0],all(predicted[1:3]),standard,right['failure']],
                        right['regression'] and predicted[3] and behavior)
                 if has_predictions else None)
        return {'transfer': level}
    return {'knowledge': _score(('concept',),obs,[right['concept']],right['reason']),
            'judgment': _score(('order','failure'),obs,[right['order'],right['failure']],right['regression']),
            'ai_collaboration': _score(('instruction','review'),obs,[right['instruction'],right['review']],right['regression']),
            'verification': verification}


def evaluate(obs, transfer=None, minimum=None, linked_turn=None):
    levels = marks(obs)
    if transfer is not None:
        if obs['stage'] != 'post' or transfer['stage'] != 'transfer':
            raise ValueError('迁移证据必须关联独立后测')
        levels.update(marks(transfer))
    scores = {}
    for key, level in levels.items():
        row = transfer if key == 'transfer' and transfer is not None else obs
        scores[key] = {'level': level, 'weighted': None if level is None else b.DIMENSIONS[key][1]*level/4,
                       'evidence_ids': [] if level is None else [row['id']],
                       'anchor': ('未观察到' if level is None else
                                  f'有 H{row["hint_level"]} 提示；按提示上限记分' if level>0 and row['hint_level'] else b.ANCHORS[level])}
    total = sum(item['weighted'] for item in scores.values() if item['weighted'] is not None)
    full = set(scores)==set(b.DIMENSIONS) and all(x['level'] is not None for x in scores.values())
    core_values = [scores.get(k,{}).get('level') for k in ('knowledge','judgment','ai_collaboration','verification')]
    core = round(sum(scores[k]['weighted'] for k in ('knowledge','judgment','ai_collaboration','verification')) * 100/85, 2) if all(v is not None for v in core_values) else None
    transfer_ok = transfer is not None and (levels.get('transfer') or 0) >= 3 and transfer['hint_level'] == 0
    test_ok = bool(obs['checks']) and all(x['passed'] for x in obs['checks'])
    mastery_line = b.threshold() if minimum is None else minimum
    mastered = full and total >= mastery_line and test_ok and transfer_ok and (levels.get('verification') or 0)>=3 and obs['hint_level']==0
    return {
        'evaluation_id': 'ev-'+uuid5(NAMESPACE_URL, obs['id']+(':'+transfer['id'] if transfer else '')).hex,
        'turn_id': linked_turn, 'skill_id': b.SKILL, 'benchmark_version': b.VERSION,
        'scores': scores, 'total_score': round(total,2) if full else None, 'core_score': core,
        'mastery_level': 'mastered' if mastered else 'developing' if full else 'insufficient_evidence',
        'mastered': mastered, 'weaknesses': [k for k,v in levels.items() if v is not None and v<3],
        'missing': [k for k in b.DIMENSIONS if levels.get(k) is None],
        'evidence_ids': [obs['id']]+([transfer['id']] if transfer else []),
        'assistance_summary': {'hint_level': obs['hint_level'], 'transfer_hint_level': transfer['hint_level'] if transfer else None},
        'evidence_sufficiency': 'sufficient' if full else 'insufficient_evidence',
        'confidence': 'fixed_benchmark_only', 'test_passed':test_ok,'transfer_passed': transfer_ok,
        'mastery_threshold': mastery_line,
    }
