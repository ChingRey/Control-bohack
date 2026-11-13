"""Structured rolling summaries with explicit coverage, immutable sources and bounded reads.
Pattern reference: https://langchain-ai.github.io/langmem/guides/summarization/
SQLite remains authoritative; the model proposes summaries, never project facts.
"""
import copy
import hashlib
import json
from datetime import datetime, timezone

MAX_CONTEXT_CHARS=80000
HISTORY_CHARS=10000
SEGMENT_CHARS=16000

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True)
def size(value):return len(encoded(value))
def state(task):
    return task.setdefault('teaching',{}).setdefault('memory',{'schema_version':1,'revision':0,'covered_through':-1,
        'segments':[],'coverage_kind':'exact_contiguous_source_ranges','status':'empty'})

def select_messages(task, evidence_ids=()):
    messages=task['messages'];focus={}
    for channel,key in (('coding','coding_prompt_id'),(None,'student_message_id')):
        focus[key]=next((i for i in range(len(messages)-1,-1,-1) if messages[i]['role']=='user' and (channel is None or messages[i]['channel']==channel)),None)
    selected={i for i in focus.values() if i is not None}
    remaining=HISTORY_CHARS
    # Retain a few original learning witnesses before filling the recent window.
    preferred=list(dict.fromkeys([*range(max(0,len(messages)-12),len(messages)),*evidence_ids]))
    for i in reversed(preferred):
        if type(i) is not int or not 0<=i<len(messages) or i in selected:continue
        cost=size(messages[i])
        if cost<=remaining:selected.add(i);remaining-=cost
    rows=[{'id':i,**messages[i]} for i in sorted(selected)]
    return rows,focus

def prepare(task,summarize,progress):
    """At most two bounded batches; successful batches survive later response failure."""
    s=state(task);stop=max(0,len(task['messages'])-12)
    for _ in range(2):
        start=s['covered_through']+1
        if start>=stop:return
        pending=task['messages'][start:stop]
        if size(pending)<HISTORY_CHARS:return
        rows=[];used=0
        for i in range(start,stop):
            row={'id':i,**task['messages'][i]};cost=size(row)
            if rows and used+cost>SEGMENT_CHARS:break
            if cost>SEGMENT_CHARS:raise ValueError('单条旧消息超过记忆整理预算，原话保留，请拆分后重试')
            rows.append(row);used+=cost
        progress('organizing_memory','正在整理历史对话，原始记录保持不变')
        summary=summarize(rows)
        if not isinstance(summary,str) or not 1<=len(summary.strip())<=1800:raise ValueError('记忆摘要无效；旧记忆和原话保留')
        s['segments'].append({'id':len(s['segments']),'from_id':start,'to_id':rows[-1]['id'],
            'source_digest':hashlib.sha256(encoded(rows).encode()).hexdigest(),
            'summary':summary,'kind':'model_notes_not_verified_facts'})
        s['covered_through']=rows[-1]['id'];s['revision']+=1;s['status']='ready'
    # If history still has gaps, context describes them; it must not pretend all was read.

def view(task,loaded_ids=()):
    s=state(task);notes=task.get('teaching',{}).get('course',{})
    unseen=[i for i in range(s['covered_through']+1,len(task['messages'])) if i not in loaded_ids]
    return {'revision':s['revision'],'covered_through':s['covered_through'],
        'segments':copy.deepcopy(s['segments'][-4:]),'older_segment_count':max(0,len(s['segments'])-4),
        'summary':notes.get('summary','')[:1500],'resume_note':notes.get('resume_note','')[:1500],
        'omitted_unsummarized_count':len(unseen),'omitted_unsummarized_first_id':unseen[0] if unseen else None,
        'notice':'摘要是模型笔记；未加载、未整理的原话不是已读，必要时调用read_message_history。'}

def revision_record(task,code_hash):
    s=state(task);course=task.get('teaching',{}).get('course',{})
    body={'schema_version':1,'revision':s['revision'],'covered_through':s['covered_through'],
          'segments':s['segments'],'summary':course.get('summary',''),'resume_note':course.get('resume_note',''),
          'code_hash':code_hash,'kind':'model_notes_not_mastery_certificate'}
    return body

def report(task):
    s=state(task);course=task.get('teaching',{}).get('course',{});learning=task.get('teaching',{}).get('learning',{})
    out=['# 项目学习记录','','## 系统记录的项目进度','',f"已执行 {task.get('step',0)} 步；保存修改 {len(task.get('changes',[]))} 次；原始消息 {len(task['messages'])} 条。",'',
         '确认计划：',*['- '+x for x in task.get('plan',[])],'','## 教师接续笔记（不是掌握证明）','',course.get('summary','尚无摘要'),'',
         '下次接着做：'+course.get('resume_note','尚未记录'),'','## 学生表现（模型建议，待复核）','']
    for o in learning.get('observations',[])[-20:]:
        out.append(f"- {o['capability_id']}：{o['level']}。{o['explanation']}；来源消息 {o['evidence_ids']}，代码版本 {o['code_hash']}")
    out+=['','## 学生经验与偏好','']
    for e in learning.get('experiences',[]):out.append(f"- [{e['status']}] {e['title']}：{e['rule']}；适用：{e['when']}；限制：{e['limits']}；来源 {e['evidence_ids']}")
    out+=['','## 历史整理范围','',f"当前记忆版本 {s['revision']}；连续整理到消息 {s['covered_through']}。-1表示尚未整理。"]
    for segment in s['segments']:out+=['',f"### 消息 {segment['from_id']}–{segment['to_id']}",'',segment['summary']]
    out+=['','原始对话仍在SQLite；记忆和学习记录的旧版本保留。当前没有证明任何候选Skill能提升真实Coding Agent。','']
    return '\n'.join(out)
