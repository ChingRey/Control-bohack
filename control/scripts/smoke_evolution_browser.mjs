import {readFile,writeFile,mkdtemp,rm,copyFile,mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import {tmpdir} from 'node:os';

const [browser, evidenceDir, output] = process.argv.slice(2);
const batch = evidenceDir.startsWith('--batch-');
const fresh = evidenceDir === '--fresh' || batch;
const neutral = evidenceDir.includes('neutral');
const linked = evidenceDir.includes('linked-list') || evidenceDir==='--batch-linked';
const profile = await mkdtemp(join(tmpdir(),'control-evolution-browser-'));
const verifyData=join(profile,'verify-data');
await mkdir(verifyData);
if(!fresh) await copyFile(join(evidenceDir,'records.sqlite3'),join(verifyData,'records.sqlite3'));
const freePort=async()=>await new Promise(resolve=>{const s=createServer();s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});
const port=await freePort();
const server=spawn('python',['-X','utf8','backend.py','--port',String(port)],{windowsHide:true,env:{...process.env,CONTROL_WORKBENCH_DATA:verifyData,CONTROL_ALLOW_SIMULATION:'1'}});
const edge=spawn(browser,['--headless=new','--disable-gpu',...(process.env.CONTROL_BROWSER_NO_SANDBOX==='1'?['--no-sandbox']:[]),'--disable-software-rasterizer','--disable-gpu-compositing','--no-first-run','--disable-background-networking',
 '--window-size='+(process.env.CONTROL_TEST_VIEWPORT||'1440,1000'),'--user-data-dir='+profile,'--remote-debugging-port=0','about:blank'],{windowsHide:true});
const wait=async fn=>{
  for(let i=0;i<100;i++) {try{const v=await fn();if(v)return v;}catch{} await new Promise(resolve=>setTimeout(resolve,100));}
  throw Error('Browser check timed out');
};
server.stderr.on('data',data=>process.stderr.write(data));
edge.on('error',err=>console.error(err));
edge.stderr.on('data',data=>process.stderr.write(data));
let ws;
try {
 const base='http://127.0.0.1:'+port;
 await wait(async()=>(await fetch(base+'/api/health')).ok);
 const debug=(await wait(()=>readFile(join(profile,'DevToolsActivePort'),'utf8'))).split(/\r?\n/)[0];
 const tab=await wait(async()=>{for(const host of ['127.0.0.1','[::1]']) {try {return (await (await fetch('http://'+host+':'+debug+'/json')).json())[0];} catch {}}});
 ws=new WebSocket(tab.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 let id=0;
 const pending=new Map();
 ws.onmessage=event=>{const data=JSON.parse(event.data);if(pending.has(data.id)){pending.get(data.id)(data);pending.delete(data.id);}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{
  const self=++id;
  pending.set(self,d=>d.error?reject(Error(d.error.message)):resolve(d.result));
  ws.send(JSON.stringify({id:self,method,params}));
 });
 async function evaluate(expression) {
  const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description||expression);
  return result.result.value;
 }
 await call('Page.navigate',{url:base});
 await wait(()=>evaluate("document.body.classList.contains('home-open') && typeof window.canSwitchControlProject==='function'"));
 if(!linked) await evaluate("document.querySelector('#evolution-benchmark').value='input-boundary-rubric-v1'");
 await evaluate("document.querySelector('#evolution-open').click()");
 await wait(()=>evaluate("document.querySelector('#evolution-board').innerText.includes('0')"));
 if(batch) {
  await evaluate("(()=>{const s=document.querySelector('#evolution-cohort');s.value='simulation';s.dispatchEvent(new Event('change'))})()");
  const isVisible=await evaluate("!document.querySelector('#ev-sim-controls').hidden");
  if(!isVisible) throw Error('Automatic simulation controls missing');
  await evaluate("document.querySelector('#ev-sim-users').value='8';document.querySelector('#ev-sim-returns').value='2';document.querySelector('#ev-sim-start').click()");
  await wait(()=>evaluate("document.querySelector('#ev-sim-start').disabled && !document.querySelector('#ev-sim-progress').hidden"));
  await wait(()=>evaluate("document.querySelector('#ev-sim-status').textContent.includes('模拟已完成')"));
  await wait(()=>evaluate("document.querySelector('#evolution-board').innerText.includes('10')"));
  const result=await (await fetch(base+'/api/teaching/strategy-simulation')).json();
  if(result.target!==10 || result.completed!==10 || result.board.participant_count!==8 ||
     result.board.benchmark_version!==(linked?'linked-list-delete-rubric-v1':'input-boundary-rubric-v1') ||
     result.recent.length!==6 || !result.recent[0].repeat_visit) throw Error(JSON.stringify(result).slice(0,800));
  await evaluate("document.querySelector('#ev-sim-run-log').open=true");
  const log=await evaluate("document.querySelector('#ev-sim-recent').innerText");
  if(!log.includes('第 10 轮')||!log.includes('回访')) throw Error(log);
  await writeFile(output,Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  console.log('Verified 8 adjustable participants, 2 visits and live/final progress for '+result.benchmark_version);
 } else {
 if(!fresh) {
  await evaluate("(()=>{const select=document.querySelector('#evolution-cohort');select.value='manual';select.dispatchEvent(new Event('change'))})()");
  if(neutral) {
   await wait(()=>evaluate("document.querySelector('.ev-version-picker select')?.options.length"));
   await evaluate("(()=>{const select=document.querySelector('.ev-version-picker select');select.value='2';select.dispatchEvent(new Event('change'))})()");
   await wait(()=>evaluate("document.querySelector('#evolution-board').innerText.includes('未达条件')"));
  } else {
   await wait(()=>evaluate("document.querySelector('#evolution-board').innerText.includes('v1 → v2')"));
   const receipt=await evaluate("document.querySelector('#evolution-board').innerText");
   for(const token of ['学生卡在哪里','下一版怎么教','试用结果怎样','后续有没有用上',...(linked?['2 组配对','缺少有效断言']:['5 组配对','31']),'通过模拟门槛']) {
    if(!receipt.includes(token)) throw Error('Missing '+token);
   }
  }
  const layout=await evaluate("(()=>{const d=document.querySelector('#evolution-dialog');return {width:d.clientWidth,scroll:d.scrollWidth,trialHidden:document.querySelector('#evolution-trial-panel').hidden}})()");
  if(layout.scroll>layout.width+1 || !layout.trialHidden) throw Error(JSON.stringify(layout));
  await writeFile(output,Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  if(neutral) console.log('Verified rejected candidate and its failing criteria');
 }
 await evaluate("document.querySelector('#evolution-show-trial').click()");
 await evaluate("document.querySelector('#evolution-trial-panel details').open=true");
 async function start(name, arm) {
  const previous=await evaluate("document.querySelector('#evolution-profile-select').value");
  const expression=JSON.stringify(name);
  await evaluate(`document.querySelector('#evolution-profile-name').value=${expression};document.querySelector('#evolution-profile').click()`);
  await wait(()=>evaluate(`(()=>{const s=document.querySelector('#evolution-profile-select');return s.value && s.value!==${JSON.stringify(previous)}})()`));
  await evaluate(`document.querySelector('#evolution-arm').value=${JSON.stringify(arm)}`);
  await evaluate("document.querySelector('#evolution-simulate').click()");
  await see('独立前测');
  await see('手工模拟');
  await wait(()=>evaluate("!document.body.classList.contains('home-open') && Boolean(localStorage.getItem('control-workbench-task'))"));
 }
 async function see(label) {
  await wait(()=>evaluate(`document.querySelector('#evolution-trial').innerText.includes(${JSON.stringify(label)})`));
  await wait(()=>evaluate("document.querySelector('#evolution-dialog').getAttribute('aria-busy')===null"));
 }
 async function submit(values) {
  await evaluate(`(()=>{const f=document.querySelector('#evolution-trial form');f.querySelectorAll('select').forEach((x,i)=>x.value=${JSON.stringify(values)}[i]);f.requestSubmit()})()`);
 }
 if(linked) {
  await start('Browser linked-list','default');
  await evaluate(`(()=>{const form=document.querySelector('#evolution-trial form');
    const answers=[1,2,0,1,1,2,0];
    form.querySelectorAll('select').forEach((field,index)=>field.value=answers[index]);
    form.querySelector('textarea').value=JSON.stringify([{values:[3,6,9],target:6,expected:[3,9]}]);
    form.requestSubmit()})()`);
  await see('引导练习');
 } else {
 const gap=[1,0,1,1,1,2,1,1,0,1,1];
 const correct=[1,0,2,1,1,2,1,1,0,0,0];
 await start('Browser A','default');
 await submit(gap);await see('引导练习');
 await submit(gap);await see('反馈后的新练习');
 if(fresh) {
  await submit(gap);await see('独立后测');
  await submit(gap);await see('独立迁移');
  await submit([1,1,1,1,0,1,1]);await see('试验完成');
  await evaluate("document.querySelector('#evolution-show-board').click()");
  await wait(()=>evaluate("document.querySelector('.ev-version-heading').innerText.includes('等待试用')"));
  await evaluate("document.querySelector('#evolution-show-trial').click()");
  await start('Browser B','candidate');
  await submit(gap);await see('已登记的候选版本');
  await submit(correct);await see('独立后测');
  await submit(correct);await see('独立迁移');
  await submit([2,1,1,1,0,0,0]);await see('试验完成');
  await evaluate("document.querySelector('#evolution-show-board').click()");
  await wait(()=>evaluate("document.querySelector('.ev-version-heading').innerText.includes('通过模拟门槛')"));
  await evaluate("document.querySelector('#evolution-show-trial').click()");
  await start('Browser C','default');
  await submit(gap);await see('使用已验证的匹配策略');
  await writeFile(output,Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
 }
 }
 console.log(fresh?'Verified browser A → B → C, including v2 adoption':'Verified stored dashboard and feedback-driven UI in Chromium');

 }
} finally {
 ws?.close();
 edge.kill();
 server.kill();
 await new Promise(resolve=>setTimeout(resolve,400));
 if(profile.startsWith(join(tmpdir(),'control-evolution-browser-'))) await rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:200});
}

