"""Linked list benchmark: execute learner-authored assertions against real nodes."""
import json
from uuid import uuid4
from .linked_list_operations import execute

VERSION = 'linked-list-delete-rubric-v1'
SKILL = 'verification'
TOPIC = 'linked-list-delete'
TASK_TYPE = 'linked-list-boundaries'
DIFFICULTY = 'intro'
TITLE = '单链表删除 · 边界识别与测试'
PROJECT = ['约定只删除第一个匹配节点', '检查头节点更新与后继链接', '运行边界用例并记录断言']
REQUIREMENTS = ('首个匹配', '头节点更新', '无匹配保持原链')
BASE_PROMPTS = (
    '先检查目标在头部、内部和不存在时的预期。想想删除后谁持有新的入口。',
    '头部没有前驱，删除时要返回新表头。删除其他节点时，把前驱连到被删节点的后继。',
    '为删除操作写测试，运行后检查剩余链表。',
    '换到预约取消场景，按新约定独立设计测试，并核对保留的预约顺序。',
)
ADAPT = {
    'verification': ('区分正常与边界', '先列「空链、单节点删中、删头、删尾、未找到、重复值」六类，再逐条写输入、目标和预期剩余链。运行断言定位第一处差异。'),
    'judgment': ('追踪节点连接', '画出 head、当前节点和前驱，分别模拟删除头节点和删除尾节点。'),
    'knowledge': ('解释删除不变量', '先说明删除后谁持有 head，再比较删除首个匹配和删除全部匹配的区别。'),
    'ai_collaboration': ('写清验收条件', '明确只删首个匹配、其余节点顺序不变、找不到时保持原链，并要求附实际执行结果。'),
    'transfer': ('预演迁移', '换一个未见过的任务队列，写出重复项和无匹配时的两个可运行断言。'),
}
STAGES = {'pre':'工单链表','practice':'待办链表','post':'播放队列链表','transfer':'预约取消队列'}
GOALS = {
    'verification':'先用可执行断言覆盖链表删除边界，再用实际输出定位错误',
    'judgment':'先追踪删除前后的头节点和前驱连接，再验证剩余顺序',
    'knowledge':'先解释首个匹配及保留剩余顺序的不变量',
    'ai_collaboration':'先写出链表删除的可验收要求并验证交付',
}
QUESTIONS = {
    'head': ('删除头节点后，调用方应保留哪个引用？', ['原 head','返回的新 head','原头节点的前驱'],1),
    'duplicate': ('重复值出现两次时，约定如何处理？', ['删除全部','跳过全部','只删除第一个'],2),
    'missing': ('找不到目标时，剩余链表应怎样？', ['保持内容和顺序','清空链表','只保留头节点'],0),
    'tail': ('删除尾节点时，前驱的 next 应指向哪里？', ['原 head','空引用','原尾节点'],1),
    'request': ('哪条需求足以指导实现？', ['实现删除','删首个匹配并返回新头，无匹配原样返回，保留剩余顺序','让代码短一点'],1),
    'evidence': ('如何验收？', ['观察普通内节点能删除','函数有返回值','运行边界断言，比较预期和实际剩余链'],2),
    'review': ('重复项测试中应核对什么？', ['计数和剩余顺序','只看链表非空','只看输出第一项'],0),
}


def category(values, target):
    if not values:
        return 'empty'
    if target not in values:
        return 'missing'
    if values.count(target)>1:
        return 'duplicate'
    if len(values)==1:
        return 'singleton'
    if values[0]==target:
        return 'head'
    if values[-1]==target:
        return 'tail'
    return 'middle'


LABELS = {'empty':'空链','singleton':'单节点删中','head':'删头','tail':'删尾',
          'missing':'未找到','duplicate':'重复值','middle':'删中间节点'}
FAULTS = ('empty','head','tail','missing','all')
CORE = ('empty','singleton','head','tail','missing','duplicate')


def form(stage):
    names=('missing','duplicate') if stage=='transfer' else QUESTIONS
    transfer=stage=='transfer'
    description='删除最后一个匹配节点，保留其余节点顺序' if transfer else '删除第一个匹配节点，保留其余节点顺序'
    questions=[{'id':k,'label':QUESTIONS[k][0],'options':QUESTIONS[k][1]} for k in names]
    if transfer:
        questions[1]={'id':'duplicate','label':'在这项新任务中，重复值出现两次时应留下哪一项？',
                      'options':['两项都删','保留最后一项','保留第一次出现的项']}
    return {'stage':stage,'subject':STAGES[stage],'normal_input':description,
            'operation':'linked-list-tests','cases':[],'questions':questions}


def _items(value):
    return isinstance(value,list) and len(value)<=12 and all(type(x) is int and abs(x)<=999 for x in value)


def observe(session_id,stage,submitted,hint_level):
    answers=submitted.get('answers',{})
    names={q['id'] for q in form(stage)['questions']}
    if not isinstance(answers,dict) or not set(answers)<=names or any(type(x) is not int or x not in range(3) for x in answers.values()):
        raise ValueError('请选择题目中的选项')
    raw=submitted.get('test_cases',[])
    if isinstance(raw,str):
        if len(raw)>7000:
            raise ValueError('测试用例内容过长')
        try:
            raw=json.loads(raw)
        except (ValueError, RecursionError) as error:
            raise ValueError('测试用例应为 JSON 数组') from error
    if not isinstance(raw,list) or len(raw)>12:
        raise ValueError('请提交最多 12 条测试用例')
    rows=[]
    last=stage=='transfer'
    for case in raw:
        if (not isinstance(case,dict) or set(case)!={'values','target','expected'}
            or not _items(case['values']) or not _items(case['expected'])
            or type(case['target']) is not int or abs(case['target'])>999):
            raise ValueError('每条用例需包含 values、target、expected，列表最多 12 个整数')
        values,target,expected=case['values'],case['target'],case['expected']
        actual=execute(values,target,last=last)
        passed=actual==expected
        name=category(values,target)
        rows.append({'input':{'values':values,'target':target},'expected':expected,'actual':actual,
                     'passed':passed,'category':name,'label':LABELS[name],
                     'caught':[fault for fault in FAULTS if execute(values,target,fault,last=last)!=expected] if passed else []})
    known={row['category'] for row in rows if row['passed']}
    # A duplicate test needs separated duplicates. Adjacent equal values cannot
    # distinguish which matching node was removed in the observed sequence.
    distinguishable=any(row['passed'] and row['category']=='duplicate'
        and execute(row['input']['values'],row['input']['target'],last=not last)!=row['expected']
        for row in rows)
    if not distinguishable:
        known.discard('duplicate')
    gaps=[LABELS[name] for name in CORE if name not in known]
    return {'id':f'{session_id}:{uuid4().hex}','stage':stage,'benchmark_version':VERSION,'answers':answers,
            'predictions':[],'checks':rows,'hint_level':hint_level,'case_gaps':gaps,'distinguishes_delete_order':distinguishable}


def marks(obs, score):
    correct={k:obs['answers'].get(k)==item[2] for k,item in QUESTIONS.items()}
    passed={r['category'] for r in obs['checks'] if r['passed']}
    caught={fault for r in obs['checks'] for fault in r['caught']}
    consistent=bool(obs['checks']) and all(r['passed'] for r in obs['checks'])
    base=[consistent, not obs['case_gaps'], set(FAULTS)<=caught]
    advanced='middle' in passed
    if obs['stage']=='transfer':
        return {'transfer':score(('missing','duplicate'),obs,[*base,correct['missing'] and correct['duplicate']],advanced) if obs['checks'] else None}
    return {
        'knowledge':score(('head','duplicate'),obs,[correct['head'],correct['duplicate']],correct['tail']),
        'judgment':score(('missing','tail'),obs,[correct['missing'],correct['tail']], 'tail' in passed),
        'ai_collaboration':score(('request','evidence'),obs,[correct['request'],correct['evidence']],correct['review']),
        'verification':score((),obs,base,advanced) if obs['checks'] else None,
    }


def test_passed(obs):
    return not obs['case_gaps'] and all(r['passed'] for r in obs['checks'])

def explain(obs, dimension):
    prompts={
        'knowledge':('head','duplicate','tail'),
        'judgment':('missing','tail'),
        'ai_collaboration':('request','evidence','review'),
        'verification':(),
        'transfer':('missing','duplicate'),
    }
    reasons=[]
    for key in prompts[dimension]:
        label=QUESTIONS[key][0]
        if dimension=='transfer' and key=='duplicate':
            label='重复值时只删除最后一个匹配'
        if key in obs['answers']:
            reasons.append(label+' '+('正确' if obs['answers'][key]==QUESTIONS[key][2] else '答错'))
        else:
            reasons.append(label+' 未作答')
    if dimension in ('verification','transfer'):
        checks=obs['checks']
        reasons.append(f"{sum(row['passed'] for row in checks)}/{len(checks)} 条断言与实际结果一致")
        reasons.append(f"{len({fault for row in checks for fault in row['caught']})}/{len(FAULTS)} 种固定缺陷被测试识别")
    return reasons
