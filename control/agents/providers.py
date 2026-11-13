"""Provider-specific wire formats. Secrets stay in process memory, never metadata."""
import copy
import json
import os
import re
from urllib.parse import urlparse
from urllib.request import Request

ENDPOINTS={'deepseek':'https://api.deepseek.com/chat/completions','openai':'https://api.openai.com/v1/responses'}

def settings():
    endpoint=os.getenv('TEACHING_ENDPOINT','')
    provider=os.getenv('TEACHING_PROVIDER','')
    if not provider:
        if endpoint:
            host=urlparse(endpoint).hostname
            provider='openai' if host=='api.openai.com' else 'deepseek' if host=='api.deepseek.com' else 'compatible'
        else:provider='openai' if os.getenv('OPENAI_API_KEY') and not os.getenv('DEEPSEEK_API_KEY') else 'deepseek'
    if provider not in ('openai','deepseek','compatible'):raise ValueError('不支持的教学服务商')
    if os.getenv('TEACHING_PROVIDER') in ENDPOINTS:endpoint=ENDPOINTS[provider]
    key=os.getenv('OPENAI_API_KEY' if provider=='openai' else 'DEEPSEEK_API_KEY','') if provider!='compatible' else os.getenv('TEACHING_API_KEY','')
    if not key and not os.getenv('TEACHING_PROVIDER'):key=os.getenv('TEACHING_API_KEY','')
    return {'provider':provider,'endpoint':endpoint or ENDPOINTS.get(provider,''),'key':key,
            'model':os.getenv('TEACHING_MODEL','' if provider=='openai' else 'deepseek-flash'),
            'protocol':'responses' if provider=='openai' else 'chat_completions'}

def configure(provider,key,model):
    if provider not in ENDPOINTS:raise ValueError('请选择DeepSeek或OpenAI')
    if not isinstance(key,str) or not key.strip() or not key.isascii() or any(c.isspace() for c in key.strip()) or len(key)>1024:raise ValueError('请输入有效API Key，不能含换行或空格')
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}',model):raise ValueError('请输入账户可用的模型ID')
    os.environ['OPENAI_API_KEY' if provider=='openai' else 'DEEPSEEK_API_KEY']=key.strip()
    os.environ['TEACHING_PROVIDER']=provider;os.environ['TEACHING_MODE']='model'
    os.environ['TEACHING_ENDPOINT']=ENDPOINTS[provider];os.environ['TEACHING_MODEL']=model

def metadata(config,mode):
    return {'mode':mode,'provider':config['provider'],'model':config['model'] if mode=='model' else 'scripted-demo','protocol':config['protocol']}

def response_input(messages):
    inputs=[]
    for message in messages:
        if '_response_items' in message:
            inputs.extend(copy.deepcopy(message['_response_items']))
        elif message['role']=='tool':
            inputs.append({'type':'function_call_output','call_id':message['tool_call_id'],'output':message['content']})
        else:inputs.append({'role':message['role'],'content':message.get('content') or ''})
    return inputs

def request(config,messages,max_tokens,tools=None,json_mode=False):
    endpoint=config['endpoint'];target=urlparse(endpoint)
    if not config['model'] or not target.hostname or (target.scheme!='https' and not(target.scheme=='http' and target.hostname in ('localhost','127.0.0.1'))):raise ValueError('模型地址或名称未正确配置')
    if target.hostname in ('api.openai.com','api.deepseek.com') and not config['key']:raise ValueError('请先配置所选服务商的API Key')
    if config['protocol']=='responses':
        payload={'model':config['model'],'input':response_input(messages),'max_output_tokens':max(4000,max_tokens),
                 'store':False,'include':['reasoning.encrypted_content'],'text':{'format':{'type':'json_object'}}}
        if tools:
            payload['tools']=[{'type':'function',**copy.deepcopy(t['function']),'strict':False} for t in tools]
        if config['model'].startswith(('gpt-5','gpt-6','o3','o4')):payload['reasoning']={'effort':'low'}
    else:
        payload={'model':config['model'],'messages':messages,'max_tokens':max_tokens}
        if tools:payload['tools']=tools
        if target.hostname=='api.deepseek.com':payload['thinking']={'type':'disabled'}
        if json_mode:payload['response_format']={'type':'json_object'}
    return Request(endpoint,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+config['key']} if config['key'] else {})})

def normalize(config,raw):
    if config['protocol']!='responses':return raw
    if raw.get('status') in ('failed','incomplete','cancelled'):raise ValueError('OpenAI响应未完成，请重试或更换可用模型；作答已保存')
    output=raw.get('output')
    if not isinstance(output,list):raise ValueError('OpenAI响应缺少output列表')
    text=[];calls=[]
    for item in output:
        if item.get('type')=='function_call':
            if not all(isinstance(item.get(k),str) for k in ('call_id','name','arguments')):raise ValueError('OpenAI工具调用格式无效')
            calls.append({'id':item['call_id'],'type':'function','function':{'name':item['name'],'arguments':item['arguments']}})
        elif item.get('type')=='message':
            for part in item.get('content',[]):
                if part.get('type')=='refusal':raise ValueError('模型拒绝了本次请求；请调整问题，原始作答已保存')
                if part.get('type')=='output_text':text.append(part['text'])
    return {'choices':[{'message':{'role':'assistant','content':''.join(text),'tool_calls':calls,'_response_items':copy.deepcopy(output)}}],
            'usage':raw.get('usage',{})}
