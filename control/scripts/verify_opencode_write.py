"""Run the installed OpenCode against a local synthetic provider: no real model or key.

Checks actual CLI tool discovery, project JS creation and return-file adoption.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents import opencode_executor as executor


def main():
    import argparse,base64
    parser=argparse.ArgumentParser();parser.add_argument('--path',default='src/main.js');args=parser.parse_args()
    target_name=args.path
    requests = []
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):pass
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(data)
            tool_result = any(m.get('role') == 'tool' for m in data.get('messages', []))
            if not tool_result:
                tools = {t['function']['name']: t['function'] for t in data.get('tools', []) if t.get('type') == 'function'}
                write = tools.get('write')
                if write is None:
                    self.send_response(400);self.end_headers();self.wfile.write(b'write tool unavailable');return
                properties = write.get('parameters', {}).get('properties', {})
                path_key = 'filePath' if 'filePath' in properties else 'path'
                args = {path_key: target_name,
                        'content': 'console.log("project write smoke");\n'}
                delta = {'role':'assistant','tool_calls':[{'index':0,'id':'write-js','type':'function',
                          'function':{'name':'write','arguments':json.dumps(args)}}]}
                reason = 'tool_calls'
            else:
                delta = {'role':'assistant','content':'已创建 src/main.js；这是本机模拟服务的工具联调。'}
                reason = 'stop'
            if data.get('stream'):
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                for content, finish in ((delta,None),({},reason)):
                    chunk={'id':'smoke','object':'chat.completion.chunk','created':0,'model':'smoke',
                           'choices':[{'index':0,'delta':content,'finish_reason':finish}]}
                    self.wfile.write(('data: '+json.dumps(chunk,ensure_ascii=False)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
            else:
                message={k:v for k,v in delta.items()}
                for call in message.get('tool_calls',[]):call.pop('index',None)
                result={'id':'smoke','object':'chat.completion','created':0,'model':'smoke',
                        'choices':[{'index':0,'message':message,'finish_reason':reason}]}
                raw=json.dumps(result,ensure_ascii=False).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
    exe=executor.binary()
    if not exe:raise SystemExit('OpenCode is not installed; run scripts/install_opencode.ps1 first.')
    server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    original_config=executor.CONFIG;original_root=executor.ROOT;original_binary=executor.binary
    timeout=os.environ.get('CONTROL_CODING_TIMEOUT_SECONDS')
    try:
        with tempfile.TemporaryDirectory() as folder:
            executor.ROOT=Path(folder);executor.binary=lambda:exe
            executor.CONFIG={'key':'local-smoke-token','model':'smoke','url':'http://127.0.0.1:'+str(server.server_port)+'/v1'}
            os.environ['CONTROL_CODING_TIMEOUT_SECONDS']='60'
            assets={'assets/preserved.binary':base64.b64encode(b'\x00\xffexisting asset').decode()}
            result=executor.execute({}, {'instruction':'创建 '+target_name+' 并写入一条 console.log，然后停止。'},binary_files=assets)
            assert result['binary_files']==assets,'Binary asset was not preserved'
            assert result['files'].get(target_name)=='console.log("project write smoke");\n', 'CLI did not return the created JS file'
            assert any(e.get('part',{}).get('tool')=='write' and e['part'].get('state',{}).get('status')=='completed' for e in result['events']), 'No completed write tool event'
            print(json.dumps({'status':'passed','file':target_name,'binary_preserved':True,'provider':'local_synthetic',
                              'model_requests':len(requests),'real_model_called':False},ensure_ascii=False))
    finally:
        executor.CONFIG=original_config;executor.ROOT=original_root;executor.binary=original_binary
        if timeout is None:os.environ.pop('CONTROL_CODING_TIMEOUT_SECONDS',None)
        else:os.environ['CONTROL_CODING_TIMEOUT_SECONDS']=timeout
        server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':main()
