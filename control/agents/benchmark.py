"""Versioned input validation benchmark. Grades explicit submissions, not chat."""
from __future__ import annotations

import os
from uuid import uuid4

VERSION = 'input-boundary-rubric-v1'
SKILL = 'verification'
TOPIC = 'input-validation'
TASK_TYPE = 'form-boundary'
DIFFICULTY = 'intro'
DIMENSIONS = {
    'knowledge': ('知识理解', 15),
    'judgment': ('工程判断', 25),
    'ai_collaboration': ('AI 协作指导', 20),
    'verification': ('验证与纠错', 25),
    'transfer': ('独立迁移', 15),
}
ANCHORS = ('明确答错或未完成', '只识别一个关键点', '部分完成，或定向提示后完成',
           '无提示完成标准任务', '完成标准任务并覆盖额外边界或说明关键决策')
FIELDS = (
    ('concept', '为什么需要检查空白输入？', ['输入必须是数字', '空格也是字符，只检查字符串长度会漏掉', '浏览器会自动删除所有空格']),
    ('reason', '为什么要保留正常输入的内部空格？', ['内部空格可能属于有效内容', '内部空格会导致提交失败', '所有空格都无意义']),
    ('order', '选择你要运行的处理顺序', ['先原样保存，再清理', '检查原始值是否为空，再清理并保存', '先清理两端，再拒绝空结果，只保存有效内容', '拒绝所有含空格的输入']),
    ('failure', '失败时界面应该怎样？', ['仍创建一条记录', '保持原列表不变并说明原因', '删除已有记录']),
    ('instruction', '选择交给 Coding Agent 的要求', ['把代码优化一下', '规范化两端空白，空结果不新增；保留有效内容内部空格', '所有字符串都新增']),
    ('review', '怎样验收 Coding Agent 的交付？', ['只看有没有使用清理函数', '预览能加载就通过', '要求列出用例、运行并比较预期和实际结果']),
    ('regression', '修复后额外检查什么？', ['只看按钮颜色', '确认已有记录和含内部空格的正常输入不受影响', '不用检查其他情况']),
)
EXPECTED = dict(concept=1, reason=0, order=2, failure=1, instruction=1, review=2, regression=1)
CASES = ('普通文本', '空字符串', '纯空格', '制表符与换行')
EXAMPLES = {
    'pre': ('代办标题', '阅读 代码'),
    'practice': ('待办标题', '写 单测'),
    'post': ('笔记标题', '记录 结果'),
    'transfer': ('搜索预设标签', '课程 作业'),
}
HINT_CAP = {0: 4, 1: 3, 2: 2, 3: 1}


def form(stage):
    subject, normal = EXAMPLES[stage]
    fields = FIELDS if stage != 'transfer' else tuple(x for x in FIELDS if x[0] in ('order', 'failure', 'regression'))
    return {
        'stage': stage, 'subject': subject, 'normal_input': normal,
        'questions': [{'id': k, 'label': label, 'options': options} for k, label, options in fields],
        'cases': list(CASES),
    }


def threshold():
    value = int(os.getenv('CONTROL_MASTERY_THRESHOLD', '80'))
    if not 0 <= value <= 100:
        raise ValueError('CONTROL_MASTERY_THRESHOLD 必须在 0～100 之间')
    return value


def run_cases(stage, operation):
    """Execute the learner-selected rule over fixed cases; no arbitrary code input."""
    normal = EXAMPLES[stage][1]
    inputs = (normal, '', '   ', '\t\n', '  '+normal+'  ')
    rows = []
    for value in inputs:
        expected = value.strip() or None
        if operation == 0:
            actual = value
        elif operation == 1:
            actual = value.strip() if value else None
        elif operation == 2:
            actual = value.strip() or None
        else:
            actual = value if value and not any(c.isspace() for c in value) else None
        rows.append({'input': value, 'expected': expected, 'actual': actual, 'passed': actual == expected})
    return rows


def observe(session_id, stage, submitted, hint_level=0):
    if stage not in EXAMPLES or not isinstance(submitted, dict):
        raise ValueError('考核提交格式不正确')
    questions = {q['id']: q['options'] for q in form(stage)['questions']}
    picks, predictions = submitted.get('answers', {}), submitted.get('predictions', [])
    if (not isinstance(picks, dict) or not set(picks) <= set(questions)
            or any(type(v) is not int or not 0 <= v < len(questions[k]) for k,v in picks.items())
            or not isinstance(predictions, list) or len(predictions) > 4
            or any(v is not None and type(v) is not bool for v in predictions)):
        raise ValueError('请选择题目中的选项')
    checks = run_cases(stage, picks['order']) if 'order' in picks else []
    return {'id': f'{session_id}:{uuid4().hex}', 'stage': stage, 'benchmark_version': VERSION,
            'answers': picks, 'predictions': predictions, 'checks': checks, 'hint_level': hint_level}
