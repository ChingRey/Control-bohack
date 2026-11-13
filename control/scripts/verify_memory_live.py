"""Exercise real Teaching through the local backend; no access to its API key."""
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

BASE='http://127.0.0.1:8772/api'

def call(path,body=None):
    req=Request(BASE+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=15) as response:return json.load(response)

def wait(task):
    deadline=time.monotonic()+150
    while task.get('teaching_run',{}).get('status') in ('queued','running'):
        if time.monotonic()>deadline:raise RuntimeError('后端教师任务超过实验等待预算')
        time.sleep(1);task=call('/tasks/'+task['id'])
    return task

def main():
    health=call('/health')
    if health['teaching']['mode']!='model':
        print('SKIPPED: 请先在工作台连接DeepSeek；未执行真实模型实验。');return 2
    task=call('/tasks',{'scenario':'teaching'});path='/tasks/'+task['id']
    # Synthetic dialogue only; these are test fixtures, never a real student study.
    call(path+'/coding/messages',{'message':'实验约束：不联网；页面刷新后要保留数据。请先检查输入再创建事项。'})
    for i in range(28):
        call(path+'/coding/messages',{'message':f'实验讨论{i}：'+('这是用于长对话记忆实验的合成消息，不代表真实学生能力。'*16)})
    prompt='请检查当前输入处理：空白内容不能新增事项；先解释输入流，再列出正常和边界验证。'
    call(path+'/coding/messages',{'message':prompt})
    task=wait(call(path+'/teaching/messages',{'message':'我认为应该先读取输入、检查是否为空，再创建列表项；因为先创建再检查会产生无效事项。请指出我的判断还缺什么，不要直接给完整代码。'}))
    attempts=[{'status':task['teaching_run']['status'],'error':task['teaching_run'].get('error'),'elapsed_seconds':task['teaching_run'].get('elapsed_seconds')}]
    if task['teaching_run']['status']=='failed':
        task=wait(call(path+'/teaching/review',{}))
        attempts.append({'status':task['teaching_run']['status'],'error':task['teaching_run'].get('error'),'elapsed_seconds':task['teaching_run'].get('elapsed_seconds')})
    teacher=task['teaching'];result={'mode':'real_model_synthetic_dialogue','task_id':task['id'],
      'provider':task['teaching_provider'],'status':task['teaching_run']['status'],'attempts':attempts,
      'memory_revision':teacher['memory']['revision'],'covered_through':teacher['memory']['covered_through'],
      'raw_message_count':len(task['messages']),'skill_installed':False,'human_review_required':True}
    if task['teaching_run']['status']=='completed':
        turn=teacher['turns'][-1];update=turn['result'].get('learning_update',{})
        result.update(context_usage=turn.get('context_usage'),provider_usage=turn.get('provider_usage'),
                      actual_reply=turn['result']['reply'],learning_update=update,
                      validation_warnings=turn['result'].get('validation_warnings',[]))
        expected=next(i for i,m in enumerate(task['messages']) if m['channel']=='coding' and m['role']=='user' and m['content']==prompt)
        result['current_prompt_included']=expected in turn['context_usage']['loaded_message_ids']
    else:result['error']=task['teaching_run'].get('error')
    target=Path(__file__).resolve().parents[1]/'docs/experiments/memory-live.json'
    target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('actual_reply','learning_update')},ensure_ascii=False,indent=2))
    return 0 if result['status']=='completed' and result.get('current_prompt_included') else 1

if __name__=='__main__':raise SystemExit(main())
