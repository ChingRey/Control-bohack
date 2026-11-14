// Native Chromium DevTools Protocol, no third-party browser package.
const fs=require('node:fs');
async function main(){
 const packet=JSON.parse(fs.readFileSync(0,'utf8'));
 const pages=await(await fetch(packet.debug+'/json/list')).json();const page=pages.find(p=>p.type==='page');if(!page)throw Error('浏览器未提供页面');
 const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
 let sequence=0;const pending=new Map(),errors=[];
 function send(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(Error('浏览器步骤超时'))},10000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}))})}
 ws.onmessage=e=>{const value=JSON.parse(e.data);if(value.id){const item=pending.get(value.id);if(!item)return;clearTimeout(item.timer);pending.delete(value.id);value.error?item.reject(Error(value.error.message)):item.resolve(value.result);return}
  if(value.method==='Page.javascriptDialogOpening')send('Page.handleJavaScriptDialog',{accept:packet.acceptDialogs===true}).catch(()=>{});
  if(value.method==='Runtime.exceptionThrown')errors.push(value.params.exceptionDetails.text);
  if(value.method==='Fetch.requestPaused'){const p=value.params;const allowed=p.request.url.startsWith(packet.url)||p.request.url.startsWith('data:')||p.request.url.startsWith('blob:');send(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:p.requestId}:{requestId:p.requestId,errorReason:'BlockedByClient'}).catch(()=>{})}
 };
 async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value}
 async function ready(){for(let i=0;i<80;i++){try{if(await evaluate('document.readyState==="complete"'))return}catch{}await new Promise(r=>setTimeout(r,100))}throw Error('页面加载超时')}
 let results=[];
 try{
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await send('Runtime.enable');await send('Page.enable');await send('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  await send('Page.navigate',{url:packet.url+packet.path});await new Promise(r=>setTimeout(r,150));await ready();
  for(const step of packet.cases){
   try{
    let actual;
    if(step.action==='reload'){await send('Page.reload');await new Promise(r=>setTimeout(r,150));await ready();actual='reloaded'}
    else if(step.action==='wait'){await new Promise(r=>setTimeout(r,Math.min(3000,step.ms||200)));actual='waited'}
    else actual=await evaluate(`(${function(s){const nodes=[...document.querySelectorAll(s.selector)],el=nodes[0];if(s.action==='assert_count'){if(nodes.length!==s.count)throw Error('数量预期 '+s.count+'，实际 '+nodes.length);return nodes.length}if(s.action==='assert_absent'){if(el)throw Error('元素应不存在');return true}if(!el)throw Error('找不到元素 '+s.selector);if(s.action==='fill'){el.value=s.value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));return 'filled'}if(s.action==='click'){el.click();return 'clicked'}if(s.action==='assert_text'){const text=el.textContent;if(!text.includes(s.text))throw Error('元素文本与预期不符');return text.slice(0,500)}if(s.action==='assert_exists')return true;if(s.action==='assert_value'){if(el.value!==s.value)throw Error('输入值与预期不符');return true}throw Error('未知操作')}.toString()})(${JSON.stringify(step)})`);
    results.push({action:step.action,selector:step.selector,passed:true,actual});
   }catch(e){results.push({action:step.action,selector:step.selector,passed:false,error:e.message});break}
  }
  if(packet.screenshot){const image=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(packet.screenshot,Buffer.from(image.data,'base64'))}
  process.stdout.write(JSON.stringify({passed:results.every(r=>r.passed)&&errors.length===0,results,runtime_errors:errors,source:'real_chromium_browser',external_network:'blocked',scope:'only_supplied_cases_not_full_acceptance'}));
 }finally{try{await send('Browser.close')}catch{}ws.close()}
}
main().catch(e=>{process.stderr.write(String(e.message));process.exitCode=1});
