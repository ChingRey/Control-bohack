"""Windows sockets, real HTTP/browser and actual OpenCode lifecycle; no paid model."""
import asyncio,copy,json,os,re,secrets,sys,tempfile,threading,time,urllib.request,urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import opencode_executor as executor,browser_runner,teaching_v021 as v

class Provider(BaseHTTPRequestHandler):
 count=0
 def log_message(self,*a):pass
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));Provider.count+=1
  tool_result=any(m.get('role')=='tool' for m in data.get('messages',[]))
  content='\n'.join(str(m.get('content','')) for m in data.get('messages',[]) if m.get('role')=='user')
  target='src/cart.js' if re.search(r'phase_index[^0-9]{0,12}1',content) else 'src/products.js'
  if not tool_result:
   tools={t['function']['name']:t['function'] for t in data.get('tools',[]) if t.get('type')=='function'}
   if 'write' not in tools:self.send_error(400,'write tool missing');return
   key='filePath' if 'filePath' in tools['write']['parameters']['properties'] else 'path'
   delta={'role':'assistant','tool_calls':[{'index':0,'id':'write-project','type':'function','function':{'name':'write','arguments':json.dumps({key:target,'content':'export const fixture = '+json.dumps(target)+';\n'})}}]};reason='tool_calls'
  else:delta={'role':'assistant','content':'已创建项目文件；本轮暂停，等待学生确认。本地模拟服务，不是实际模型。'};reason='stop'
  if data.get('stream'):
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
   for item,finish in ((delta,None),({},reason)):
    chunk={'id':'v021-smoke','object':'chat.completion.chunk','created':0,'model':'smoke','choices':[{'index':0,'delta':item,'finish_reason':finish}]}
    self.wfile.write(('data: '+json.dumps(chunk,ensure_ascii=False)+'\n\n').encode())
   self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
  else:
   for call in delta.get('tool_calls',[]):call.pop('index',None)
   raw=json.dumps({'choices':[{'index':0,'message':delta,'finish_reason':reason}]}).encode()
   self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

class Quiet(b.Handler):
 def log_message(self,*a):pass


def main():
 report_path=b.ROOT/'data/verification/v021';report_path.mkdir(parents=True,exist_ok=True)
 exe=executor.binary()
 if not exe:raise RuntimeError('actual OpenCode CLI required')
 provider=ThreadingHTTPServer(('127.0.0.1',0),Provider);threading.Thread(target=provider.serve_forever,daemon=True).start()
 token=secrets.token_urlsafe(32);examples=[]
 try:
  with tempfile.TemporaryDirectory(dir=report_path,ignore_cleanup_errors=True) as tmp,patch.object(b,'DATA',Path(tmp)/'workbench'),patch.object(b,'DB',Path(tmp)/'records.sqlite3'),patch.object(executor,'ROOT',Path(tmp)),patch.object(executor,'binary',return_value=exe),patch.object(executor,'CONFIG',{'key':'synthetic-test-only','model':'smoke','url':f'http://127.0.0.1:{provider.server_port}/v1'}),patch.dict(os.environ,{'CONTROL_V021_ACCESS_TOKEN':token,'TEACHING_MODE':'sample','CONTROL_CODING_TIMEOUT_SECONDS':'60'}):
   b.DATA.mkdir()
   server=b.LocalHTTPServer(('127.0.0.1',0),Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
   def http(path,body=None,authenticated=True):
    headers={'Content-Type':'application/json'}
    if authenticated:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
     with urllib.request.urlopen(req,timeout=130) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
   def success(path,body):
    status,value=http(path,body);assert status in (200,202),(status,value);return value
   async def native_http():
    reader,writer=await asyncio.open_connection('127.0.0.1',server.server_port)
    writer.write(f'GET /api/health HTTP/1.0\r\nHost: 127.0.0.1:{server.server_port}\r\n\r\n'.encode());await writer.drain()
    raw=await asyncio.wait_for(reader.read(),timeout=5);writer.close();await writer.wait_closed()
    assert b'200 OK' in raw and b'sqlite' in raw
   asyncio.run(native_http())
   t=success('/api/tasks',{'coding_mode':'opencode','checkpoint_delivery':'manual'});tid=t['id'];path='/api/tasks/'+tid;port=path+'/teaching-v021'
   with b.task_lock(tid):
    draft=b.load(tid);draft['plan_draft']=['创建 src/products.js','创建 src/cart.js'];b.save(draft)
   success(path+'/plan/confirm',{'confirmed':True,'plan':['创建 src/products.js','创建 src/cart.js']})
   def wait():
    for _ in range(900):
     status,t=http(path)
     if not b.task_busy(t):
      assert t.get('coding_run',{}).get('status')!='failed',t.get('coding_run');return t
     time.sleep(.1)
    raise RuntimeError('Coding lifecycle timeout')
   success(path+'/steps/run',{'confirmed':True,'expected_step':0,'instruction':'创建 src/products.js'});t=wait()
   assert 'src/products.js' in t['files'] and t['step']==0
   assert http(port,authenticated=False)[0]==403
   def command(op,rid,**kw):
    value=success(port+'/'+op,{'request_id':rid,**kw})
    examples.append({'operation':op,'http_request':{'request_id':rid,**kw},'http_response':value});return value
   command('configure','config');decision=command('decide','decide')['response']
   assert decision['decision_id']=='decide-decide' and decision['knowledge_point_ids']==['acceptance-criteria']
   initial=command('teach','teach0')['response']
   assert initial['action']['type']=='ask' and initial['action']['evidence_refs']==decision['evidence_refs']
   command('respond','student0',message='我会核对正常显示和空列表，并记录实际结果。')
   command('evaluate','evaluation0',assessment_mode='formative');command('teach','teach1')
   command('allow-switch','switch',reason='operator authorized synthetic integration check');command('teach','teach2')
   command('respond','student2',message='我会独立检查边界操作，保留操作和结果记录。')
   command('evaluate','evaluation2',assessment_mode='independent_transfer');command('evolve','evolve')
   first=command('resume','resume',confirmed=True,teaching_completed=True);t=wait()
   assert t['step']==1 and 'src/cart.js' in t['files'],list(t['files'])
   duplicate=command('resume','resume',confirmed=True,teaching_completed=True)
   assert duplicate['operation']['request_id']==first['operation']['request_id']
   assert http(path)[1]['step']==1
   _,view=http(port);assert len(view['assignments'])==3 and not view['skill_unlocks']
   for rid in ('decide','teach0','teach1','teach2','evaluation0','evaluation2','evolve'):
    entry=view['requests'][rid];examples.append({'contract_request':entry['contract_request'],'contract_response':entry['receipt']['response']})
   second_req=view['requests']['teach1']['contract_request'];assert second_req['teaching_history']['recent_turns'][0]['student_reply'] and second_req['teaching_history']['recent_evaluations']
   # The browser sees the same isolated project via actual frontend and HTTP handler.
   class BrowserHandler(Quiet):
    def do_GET(self):
     if self.path in ('/','/index.html'):
      html=(b.ROOT/'frontend/index.html').read_text(encoding='utf-8').replace('<head>','<head><script>localStorage.setItem("control-workbench-task",'+json.dumps(tid)+')</script>',1)
      return self.reply(200,html.encode(),'text/html; charset=utf-8')
     return super().do_GET()
   cases=[]
   def step(action,selector=None,**kw):cases.append({'action':action,**({'selector':selector} if selector else {}),**kw})
   def pause():step('wait',ms=350)
   step('wait',ms=700);step('click','#open-settings');step('click','#teaching-tools-settings > summary');step('click','#open-v021');step('fill','#v021-token',value=token);step('click','#v021-login');pause()
   step('assert_text','#v021-status',text='当前策略');step('assert_value','#v021-token',value='')
   step('click','#v021-decide');pause();step('click','#v021-teach');pause();step('assert_text','#v021-result',text='学习目标')
   step('fill','#v021-message',value='我会检查购物车操作和边界条件。');step('click','#v021-respond');pause()
   step('click','#v021-formative');pause();step('assert_text','#v021-result',text='MOCK');step('click','#v021-teach');pause();step('assert_text','#v021-status',text='已执行动作：5')
   browser=browser_runner.run({}, {},cases,handler=BrowserHandler,screenshot=report_path/'v021-browser.png')
   assert browser['passed'],browser
   report={'windows_asyncio_native_http':True,'real_http':True,'actual_opencode_cli':True,'pause_resume_once':True,'project_files':['src/products.js','src/cart.js'],
     'real_provider':False,'teaching_service':'DecideTeachingService (rules, teaching subplans, Mock evaluation/evolution)','mock_mastery_applied':False,'skill_unlocks':[],
     'browser':browser,'public_contract_version':'0.2.1','examples_file':'http-examples.json','synthetic_provider_requests':Provider.count}
   (report_path/'http-examples.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf-8')
   (report_path/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps(report,ensure_ascii=True));server.shutdown();server.server_close()
 finally:provider.shutdown();provider.server_close()

if __name__=='__main__':main()
