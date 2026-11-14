"""Simulated learners with repeatable pre-test profiles and an explicit response model."""
import random

from agents import benchmark, linked_list_benchmark as linked


def simulated_answer(session, learner, scenario):
    stage = session['stage']
    events = session.get('events', [])
    if session.get('benchmark_version')==linked.VERSION:
        return linked_answer(session,learner,scenario)
    learned = dict(learner['knows'])
    compared_examples = any(event['phase']=='lesson'
                            and event['actual_strategy_used']['step_id']=='practice'
                            and '输入 → 预期 → 实际' in event['prompt'] for event in events)
    # Each learner's general learning and response to the verification exercise
    # are fixed before assignment by a seeded draw.
    if stage != 'pre':
        for key, draw in learner['practice_gain'].items():
            if draw < 0.16:
                learned[key] = True
        if scenario == 'responsive' and compared_examples and learner['responds']:
            for key in ('order','review','boundary','extra','regression'):
                learned[key] = True
    wrong = {'concept':0,'reason':1,'order':1,'failure':0,'instruction':0,'review':0,'regression':0}
    selected = {'order','failure','regression'} if stage=='transfer' else set(wrong)
    answers = {key:benchmark.EXPECTED[key] if learned[key] else wrong[key]
               for key in wrong if key in selected}
    predictions = [True, not learned['empty'], not learned['boundary'], not learned['extra']]
    return {'stage':stage,'revision':session['revision'],'answers':answers,'predictions':predictions}


def make_learner(seed, index):
    rng = random.Random(f'{seed}:{index}')
    aptitude = rng.uniform(0.35,0.83)
    knows = {
        'concept': rng.random()<aptitude+0.18,
        'reason': rng.random()<aptitude,
        'order': rng.random()<aptitude-0.35,
        'failure': rng.random()<aptitude+0.18,
        'instruction': rng.random()<aptitude,
        'review': rng.random()<aptitude-0.25,
        'regression': rng.random()<aptitude,
        'empty': True,
        'boundary': rng.random()<aptitude-0.35,
        'extra': rng.random()<aptitude-0.25,
    }
    # Keep a common novice band for comparison alongside varied learners.
    if index % 5 in (1, 2, 3):
        knows.update(concept=True, reason=index%2==0, order=False, failure=True, instruction=True,
                     review=False, boundary=False, extra=False)
    return {'knows':knows,
            'practice_gain':{key:rng.random() for key in knows},
            'responds':rng.random()<0.9}

# Fixed, independently specified assertions. The transfer task deletes the last
# match, so the separated-duplicate case has a different expected result.
LINKED_CASES = (
    ('middle',[3,6,9],6,[3,9]),
    ('empty',[],3,[]),
    ('singleton',[3],3,[]),
    ('head',[3,6,9],3,[6,9]),
    ('tail',[3,6,9],9,[3,6]),
    ('missing',[3,6,9],2,[3,6,9]),
    ('duplicate',[3,6,3,9],3,[6,3,9]),
)


def linked_answer(session, learner, scenario):
    stage=session['stage']
    knows=learner['knows']
    response=scenario=='responsive' and learner['responds'] and any(
        event['phase']=='lesson' and event['actual_strategy_used']['step_id']=='practice'
        and event['prompt']==linked.ADAPT['verification'][1] for event in session.get('events',[]))
    stronger=stage!='pre' and response
    flags={'head':knows['concept'],'duplicate':knows['order'],'missing':knows['failure'],
           'tail':knows['reason'],'request':knows['instruction'],'evidence':knows['review'],
           'review':knows['regression']}
    if stronger:
        flags.update({key:True for key in flags})
    names=('missing','duplicate') if stage=='transfer' else linked.QUESTIONS
    answers={key:linked.QUESTIONS[key][2] if flags[key] else (linked.QUESTIONS[key][2]+1)%3 for key in names}
    coverage={'middle','head'}
    if stronger:
        coverage.update(linked.CORE)
    else:
        coverage.update(key for key,known in (
            ('missing',knows['boundary']),('singleton',knows['order']),('tail',knows['extra'])) if known)
    tests=[{'values':values,'target':target,'expected':[3,6,9] if stage=='transfer' and key=='duplicate' else expected}
           for key,values,target,expected in LINKED_CASES if key in coverage]
    return {'stage':stage,'revision':session['revision'],'answers':answers,'test_cases':tests}
