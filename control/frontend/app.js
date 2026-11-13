const $=id=>document.getElementById(id);let task=null,file='app.js',busy=false,saved='',confirmMode='step';
function toast(text){$('toast').textContent=text;$('toast').style.display='block';clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('toast').style.display='none',3500)}
async function api(path,body){if(body&&task&&path.includes('/tasks/'+task.id+'/'))body={...body,runtime_observations:runtimeObservations};const r=await fetch('/api'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'请求失败');return data}
function hasCodeChanges(){return !!(task&&file&&Object.prototype.hasOwnProperty.call(task.files||{},file)&&$('code').value!==String(saved??''))}
function lines(){$('lines').textContent=$('code').value.split('\n').map((_,i)=>i+1).join('\n')}
function openFile(name){if(hasCodeChanges()&&!confirm('当前文件尚未保存，放弃修改并切换？'))return;file=name;saved=task.files[file];$('code').value=saved;$('filename').textContent=file;lines();renderFiles()}
function renderFiles(){$('files').replaceChildren();Object.keys(task.files).forEach(name=>{const b=document.createElement('button');b.className=name===file?'active':'';const icon=document.createElement('em');icon.textContent=name.endsWith('.js')?'JS':name.endsWith('.css')?'#':'<>';b.append(icon,document.createTextNode(name));b.onclick=()=>openFile(name);$('files').append(b)})}
function render(){renderCodingWorkflow();if(!(file in task.files))file=Object.keys(task.files)[0]||'';renderFiles();saved=task.files[file]||'';$('code').value=saved;lines();$('filename').textContent=file||'空项目';$('code').disabled=!file;$('code').placeholder=file?'':'尚无文件，请在Coding聊天中描述你想开发的项目';$('save').disabled=!file;renderDevelopmentPlan();$('changes').textContent=task.changes.length?'已保存 '+task.changes.length+' 次代码修改':'尚无代码修改';renderChats();$('checks').textContent=task.checks.map(c=>(c.pass?'✓ ':'○ ')+c.name).join('\n');$('run').disabled=busy||!task.plan.length||task.step>=task.plan.length;renderTeacherStatus();if(previewTaskId&&previewTaskId!==task.id){runtimeObservations=[];previewTaskId=null;$('runtime-frame').src='about:blank';if(!$('runtime-panel').hidden)loadPreview()}$('connection').textContent='本地后端已连接 · SQLite 已保存';localStorage.setItem('control-workbench-task',task.id)}
function setBusy(value){busy=value;document.querySelectorAll('form button,#run,#save,#review-teaching,#evaluate-teaching,#verify,#plan-confirm,#restart-example,#knowledge-topics button').forEach(b=>b.disabled=value);if(!value&&task){$('run').disabled=!task.plan.length||task.step>=task.plan.length;$('save').disabled=!file}}
async function waitForTeacher(){
 while(['queued','running'].includes(task.teaching_run?.status)||['queued','running'].includes(task.coding_run?.status)){
  await new Promise(r=>setTimeout(r,900));
  task=await api('/tasks/'+task.id);render();
 }
 if(task.coding_run?.status==='failed')toast(task.coding_run.detail||'Coding执行失败，阶段未推进');
 if(task.teaching_run?.status==='failed')toast('本次回复未完成，消息已保存，可点击重试');
}
async function perform(fn,optimistic){
 if(busy)return false;
 if(hasCodeChanges()){toast('请先保存代码修改，再发送或执行');return false}
 setBusy(true);
 if(optimistic){const el=$(optimistic.channel+'-messages');el.append(messageNode({role:'user',content:optimistic.message},optimistic.channel));el.append(waitingNode('正在发送并保存你的消息…'));el.scrollTop=el.scrollHeight;}
 $('connection').textContent='正在发送…';
 try{task=await fn();render();await waitForTeacher();return true}
 catch(e){toast(e.message);$('connection').textContent='连接异常，可重试';if(task)render();return false}
 finally{setBusy(false)}
}
async function codingChat(message){
 if(task.mode==='opencode')return api('/tasks/'+task.id+'/coding/messages',{message});
 return api('/tasks/'+task.id+'/'+(!task.plan.length?'plan':'coding/messages'),{message});
}
for(const ch of ['coding','teaching'])$(ch+'-form').onsubmit=async e=>{
 e.preventDefault();if(busy)return;const input=$(ch+'-input'),message=input.value.trim();if(!message)return;
 if(hasCodeChanges())return toast('请先保存代码修改');input.value='';
 const ok=await perform(()=>ch==='coding'?codingChat(message):api('/tasks/'+task.id+'/teaching/messages',{message}),{channel:ch,message});
 if(!ok&&!input.value)input.value=message;
};
$('code').oninput=lines;$('code').onscroll=()=>{$('lines').scrollTop=$('code').scrollTop};
$('save').onclick=async()=>{if(busy||!file||!(file in (task?.files||{})))return;busy=true;try{task=await api('/tasks/'+task.id+'/files',{path:file,content:$('code').value});render();toast('代码已保存')}catch(e){toast(e.message)}finally{busy=false}};
$('run').onclick=()=>{confirmMode='step';$('confirm').querySelector('p').textContent='确认后只执行当前一步，完成即暂停。';$('confirm-run').textContent='确认并执行';$('confirm').querySelector('h2').textContent='确认本步指令';$('instruction').value=task.plan[task.step];$('confirm').showModal()};$('cancel-dialog').onclick=()=>$('confirm').close();$('confirm-run').onclick=()=>{const instruction=$('instruction').value.trim();if(!instruction)return;$('confirm').close();if(confirmMode==='plan')perform(()=>api('/tasks/'+task.id+'/plan/confirm',{plan:instruction.split('\n').map(x=>x.trim()).filter(Boolean),confirmed:true}));else perform(()=>api('/tasks/'+task.id+'/steps/run',{instruction,confirmed:true,expected_step:task.step}))};$('verify').onclick=()=>perform(()=>api('/tasks/'+task.id+'/verify',{}));$('preview').onclick=()=>showView('runtime');document.querySelectorAll('[data-question]').forEach(b=>b.onclick=()=>{$('teaching-input').value=b.dataset.question;$('teaching-input').focus()});
async function init(){try{const id=localStorage.getItem('control-workbench-task');if(id){try{task=await api('/tasks/'+id)}catch{task=await api('/tasks',{})}}else task=await api('/tasks',{});render();if(['queued','running'].includes(task.teaching_run?.status)||['queued','running'].includes(task.coding_run?.status)){setBusy(true);try{await waitForTeacher()}finally{setBusy(false)}}}catch(e){$('connection').textContent='连接失败';toast(e.message)}}

function renderTeacherStatus(){
 const real=task.teaching_provider?.mode==='model';renderKnowledge();renderLearning();
 const course=task.teaching?.course;
 $('course-overview').textContent=course?('本教程：'+course.title+'\n当前目标：'+(task.teaching?.plan?.goal||'先了解你的判断')+'\n接着上次：'+(course.resume_note||'从当前项目开始审查')):'本项目持续教学 · 刷新后接着学';
 $('transfer-submit').hidden=!task.teaching?.pending_transfer;
 const plan=task.teaching?.plan||{};const turns=task.teaching?.turns||[];const last=turns[turns.length-1];
 $('teacher-plan').textContent='目标：'+(plan.goal||'等待教师安排')+'\n依据：'+(plan.reason||'暂无')+'\n下一步：'+(plan.next_step||'暂无')+'\n待解决：'+(plan.open_questions||[]).join('；')+'\n状态：'+(task.teaching?.assessment||'未检查')+'（候选掌握仍待复核）\n本轮使用工具：'+(last?.tools||[]).map(x=>x.name+' '+JSON.stringify(x.arguments)).join('；')+'\n证据校验：'+((last?.result?.validation_warnings||[]).join('；')||'暂无警告');
 document.querySelector('.badge').textContent=(task.mode==='opencode'?(task.coding_provider?.configured?'OpenCode 已配置 / Teaching ':'OpenCode 待配置 / Teaching '):'Coding 示例 / Teaching ')+(real?'模型 · '+(task.teaching_provider?.provider==='openai'?'OpenAI':'DeepSeek'):'示例');
 document.querySelector('footer > span:last-child').textContent=task.mode==='opencode'?'阶段工作流 · OpenCode执行器/模型待连接 · 经验与Skill接口预留':'真实文件与记录 · Coding 固定示例 · 教学结论待验证 · 升级仅预留接口';
 const phases={observe:'观察现象',explain:'解释原因',propose:'提出改法',verify:'设计验证',transfer:'迁移检查'};
 const phase=phases[task.teaching?.phase]||'观察现象';
 document.querySelector('.teacher-context').textContent='当前学习重点：'+(task.teaching?.plan?.goal||phase);
}

function setProviderForm(provider,model){
 $('provider-choice').value=provider;$('api-key').value='';
 $('model-choice').value=model||(provider==='deepseek'?'deepseek-flash':'');
 $('model-suggestions').replaceChildren();
 if(provider==='deepseek')for(const value of ['deepseek-flash','deepseek-v4-pro']){const option=document.createElement('option');option.value=value;$('model-suggestions').append(option)}
 $('provider-note').textContent='当前项目代码和教学记录将发给 '+(provider==='openai'?'OpenAI（官方 Responses API）':'DeepSeek')+'。请填写账户有权限、支持工具调用和JSON输出的模型ID。保存不等于连接已验证。';
}
$('provider-choice').onchange=()=>setProviderForm($('provider-choice').value);
$('settings').onclick=()=>{const config=task?.teaching_provider;const provider=config?.provider==='openai'?'openai':'deepseek';setProviderForm(provider,config?.mode==='model'?config.model:null);$('settings-dialog').showModal()};
$('close-settings').onclick=()=>{$('api-key').value='';$('settings-dialog').close()};
$('connect-teacher').onclick=async()=>{try{await api('/settings/teaching',{provider:$('provider-choice').value,api_key:$('api-key').value,model:$('model-choice').value.trim()});$('api-key').value='';$('settings-dialog').close();task=await api('/tasks/'+task.id);render();toast('配置已保存，请点击审查代码验证连接')}catch(e){toast(e.message)}};

$('review-teaching').onclick=()=>perform(()=>api('/tasks/'+task.id+'/teaching/review',{}));
$('evaluate-teaching').onclick=()=>perform(()=>api('/tasks/'+task.id+'/evaluate',{}));
$('transfer-submit').onclick=()=>{const message=$('teaching-input').value.trim();if(!message)return toast('先填写迁移题作答');perform(()=>api('/tasks/'+task.id+'/teaching/transfer',{message}))};

function inlineText(el,text){
 const re=/(\*\*([^*]+)\*\*|`([^`]+)`)/g;let start=0,m;
 while((m=re.exec(text))){el.append(document.createTextNode(text.slice(start,m.index)));const node=document.createElement(m[2]?'strong':'code');node.textContent=m[2]||m[3];el.append(node);start=re.lastIndex}el.append(document.createTextNode(text.slice(start)));
}
function formatMessage(el,text){
 let code=false,pre=null;
 for(const block of text.split(/\n\s*\n/)){
  if(!block.trim())continue;
  const readable=block.length>150&&!block.includes('\n')&&!block.includes('```')?splitParagraph(block):block;
  for(const line of readable.split('\n')){
   if(line.trim().startsWith('```')){code=!code;if(code){pre=document.createElement('pre');el.append(pre)}continue}
   if(code){pre.textContent+=line+'\n';continue}
   const p=document.createElement(/^#{1,4} /.test(line)?'h4':'p');let content=line.replace(/^#{1,4} /,'');
   if(/^[-*] /.test(content)){p.className='list-line';content='• '+content.slice(2)}
   inlineText(p,content);el.append(p);
  }
 }
}
function messageNode(m,ch){const div=document.createElement('div');div.className='msg '+m.role;const b=document.createElement('b');b.textContent=m.role==='user'?'你':ch==='coding'?(task.mode==='opencode'?(task.coding_provider?.configured?'Coding · OpenCode':'Coding · OpenCode（待配置）'):'Coding Agent · 示例'):m.engine==='model'?'Teaching Agent':'Teaching Agent · 示例';div.append(b);const content=document.createElement('div');content.className='message-content';if(m.role==='user'){const p=document.createElement('p');p.textContent=m.content;content.append(p)}else if(m.content.startsWith('Teaching Agent 暂时未完成本次分析：')){const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='历史调用未完成（保留原始记录）';details.append(summary,document.createTextNode(m.content));content.append(details)}else formatMessage(content,m.content);div.append(content);return div}
function waitingNode(text){const row=document.createElement('div');row.className='waiting';row.setAttribute('role','status');row.textContent='◌ '+text;return row}
function renderChats(){
 for(const ch of ['coding','teaching']){const el=$(ch+'-messages');const nearBottom=el.scrollHeight-el.scrollTop-el.clientHeight<100;el.replaceChildren();task.messages.filter(m=>m.channel===ch).forEach(m=>el.append(messageNode(m,ch)));
  if(ch==='coding'&&task.coding_run){const run=task.coding_run;if(['queued','running'].includes(run.status))el.append(waitingNode(run.detail||'Coding执行中'));if(run.status==='failed'){const error=document.createElement('p');error.className='reply-error';error.textContent=run.detail||'执行失败，阶段未推进';el.append(error)}}
  if(ch==='teaching'){
   const run=task.teaching_run;
   if(run&&['queued','running'].includes(run.status)){const elapsed=Math.max(0,Math.floor(Date.now()/1000-run.started_at));el.append(waitingNode((run.detail||'教师正在处理')+' · '+elapsed+' 秒'));}
   if(run?.status==='failed'){const box=document.createElement('div');box.className='reply-error';const p=document.createElement('p');p.textContent=run.detail||'回复未完成，消息已保存';const retry=document.createElement('button');retry.textContent='重试回复';retry.onclick=()=>perform(()=>api('/tasks/'+task.id+'/teaching/review',{}));box.append(p,retry);const detail=document.createElement('details');const title=document.createElement('summary');title.textContent='查看错误详情';detail.append(title,document.createTextNode(run.error||''));box.append(detail);el.append(box)}
  }
  if(nearBottom||busy)el.scrollTop=el.scrollHeight;
 }
}

function splitParagraph(text){const sentences=text.match(/[^。！？]+[。！？]?[”’」』]?/g)||[text];const groups=[];let chunk='';for(const sentence of sentences){chunk+=sentence;if(chunk.length>=75){groups.push(chunk);chunk=''}}if(chunk)groups.push(chunk);return groups.join('\n')}

const layoutRoot=document.querySelector('.workspace');
let layout={files:160,plan:220,teacher:420,codeRatio:54};
try{layout={...layout,...JSON.parse(localStorage.getItem('control-layout')||'{}')}}catch{}
function applyLayout(){const width=Math.max(960,layoutRoot.clientWidth);layout.files=Math.max(120,Math.min(layout.files,width*.18));layout.plan=Math.max(160,Math.min(layout.plan,width*.23));layout.teacher=Math.max(300,Math.min(layout.teacher,width-layout.files-layout.plan-278));layoutRoot.style.setProperty('--files',layout.files+'px');layoutRoot.style.setProperty('--plan',layout.plan+'px');layoutRoot.style.setProperty('--teacher',layout.teacher+'px');layoutRoot.style.setProperty('--code-ratio',layout.codeRatio+'fr');layoutRoot.style.setProperty('--chat-ratio',(100-layout.codeRatio)+'fr')}
function persistLayout(){localStorage.setItem('control-layout',JSON.stringify(layout))}
document.querySelectorAll('.splitter').forEach(handle=>{
 const adjust=(delta)=>{const split=handle.dataset.split;if(split==='vertical'){layout.codeRatio=Math.max(25,Math.min(75,layout.codeRatio+delta));}else{const key=['files','plan','teacher'][Number(split)];layout[key]+=(split==='2'?-delta:delta);}applyLayout()};
 handle.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();handle.setPointerCapture(e.pointerId);let last=e.clientX,lastY=e.clientY;document.body.classList.add('resizing');handle.onpointermove=event=>{if(!handle.hasPointerCapture(event.pointerId))return;adjust(handle.dataset.split==='vertical'?(event.clientY-lastY)/document.querySelector('.center').clientHeight*100:event.clientX-last);last=event.clientX;lastY=event.clientY};const stop=()=>{document.body.classList.remove('resizing');handle.onpointermove=null;persistLayout()};handle.onpointerup=stop;handle.onlostpointercapture=stop;};
 handle.onkeydown=e=>{const vertical=handle.dataset.split==='vertical';const minus=vertical?'ArrowUp':'ArrowLeft',plus=vertical?'ArrowDown':'ArrowRight';if(e.key===minus||e.key===plus){e.preventDefault();adjust((e.key===plus?1:-1)*(vertical?3:20));persistLayout()}};
});
$('reset-layout').onclick=()=>{layout={files:160,plan:220,teacher:420,codeRatio:54};applyLayout();persistLayout()};window.addEventListener('resize',applyLayout);applyLayout();

function renderDevelopmentPlan(){
 const confirmed=task.plan.length>0,draft=task.plan_draft||[],steps=draft.length?draft:task.plan;
 $('steps').replaceChildren();
 function row(number,title,note){const li=document.createElement('li');const n=document.createElement('strong');n.textContent=number;const body=document.createElement('div');const name=document.createElement('div');name.textContent=title;body.append(name);if(note){const small=document.createElement('small');small.textContent=note;body.append(small)}li.append(n,body);$('steps').append(li);return body}
 row('1','设置计划',confirmed?'计划已确认':draft.length?'草稿待讨论；在Coding聊天中确认':'在Coding聊天中交流目标');
 const body=row('2','开发计划',confirmed?'每阶段结束后暂停，检查后在聊天中继续':draft.length?'以下为草稿，尚未执行':'等待生成');
 const list=document.createElement('ol');list.className='phase-progress';
 steps.forEach((text,i)=>{const item=document.createElement('li');item.className='phase-row';const title=document.createElement('span');title.textContent=text;const state=document.createElement('small');state.textContent=!confirmed?'草稿':i<task.step?'已执行 · 待审查':i===task.step?'当前阶段 · 等待指令':'待开始';item.append(title,state);list.append(item)});body.append(list);
 row('3','总结','暂不展开');
 $('progress').textContent=confirmed?task.step+' / '+task.plan.length:'待设置';
 $('stage').textContent=['queued','running'].includes(task.coding_run?.status)?'● Coding执行中':confirmed?'● 已暂停':draft.length?'● 草稿待确认':'● 等待需求';
 $('plan-confirm').hidden=true;$('run').hidden=true;
}
$('plan-confirm').onclick=()=>{confirmMode='plan';$('confirm').querySelector('p').textContent='先与教师讨论整体目标和拆分。确认后只保存计划，不执行代码。';$('confirm-run').textContent='确认计划';$('confirm').querySelector('h2').textContent='编辑并确认开发计划（每行一步）';$('instruction').value=(task.plan_draft||[]).join('\n');$('confirm').showModal()};
$('restart-example').onclick=()=>{if(confirm('从设置计划开始一个新的示例？当前记录会保留，不会删除。'))perform(()=>api('/tasks',{}))};
function renderKnowledge(){
 const course=task.teaching?.course||{},prefs=course.knowledge_preferences||{};const el=$('knowledge-topics');el.replaceChildren();
 const topics=task.knowledge_topics||{};
 Object.entries(topics).forEach(([id,topic])=>{const row=document.createElement('div');row.className='knowledge-topic';const label=document.createElement('span');label.textContent=topic.title+(prefs[id]==='later'?' · 稍后再学':prefs[id]==='learn'?' · 已选择':'');row.append(label);for(const [choice,title] of [['learn','学一下'],['later','稍后']]){const b=document.createElement('button');b.textContent=title;b.disabled=busy;b.onclick=()=>perform(()=>api('/tasks/'+task.id+'/teaching/knowledge',{topic:id,choice}));row.append(b)}el.append(row)});
}
let mapScale=1;
function fallbackMap(){const steps=task.plan.length?task.plan:task.plan_draft||[];return {title:'待办项目',branches:[{label:'要解决什么',children:[{label:'记录事项与完成情况'},{label:'边界由学生明确'}]},{label:task.plan.length?'已确认的开发计划':'计划讨论中',children:(steps.length?steps:['先明确目标，再拆分步骤']).map(label=>({label}))},{label:'技术基础（选学）',children:[{label:'页面与事件'},{label:'输入与数据保留'}]}]}}
function svgElement(tag,attrs={},text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n}
function drawMap(){
 const map=task.teaching?.mindmap||fallbackMap(),branches=map.branches||[];const h=Math.max(480,branches.length*200+60);$('map-title').textContent=map.title;$('map-caption').textContent=task.teaching?.mindmap?'教师生成的讲解图 · 方案不代表实现或测试通过':'系统结构视图 · 可请教师根据当前讨论重新绘制';const host=$('map-canvas');host.replaceChildren();
 const svg=svgElement('svg',{viewBox:'0 0 1060 '+h,role:'img','aria-label':map.title});svg.style.width=(mapScale*100)+'%';svg.style.minWidth='700px';const colors=['#a6e3c0','#b9cafa','#efc789','#dab5ee'];
 function card(x,y,w,height,label,color,root=false){svg.append(svgElement('rect',{x,y,width:w,height,rx:root?20:12,fill:root?'#c0f0d1':'#223342',stroke:color,'stroke-width':root?0:1.5}));const chars=[...label];const chunks=[];const per=Math.floor((w-28)/14);for(let i=0;i<chars.length;i+=per)chunks.push(chars.slice(i,i+per).join(''));chunks.slice(0,2).forEach((line,i)=>svg.append(svgElement('text',{x:x+16,y:y+height/2+(i-(Math.min(chunks.length,2)-1)/2)*20+5,fill:root?'#173c27':'#e4eef5','font-size':14,'font-family':'Microsoft YaHei, sans-serif','font-weight':root?650:450},line)))}
 const mid=h/2;card(24,mid-44,235,88,map.title,colors[0],true);
 branches.forEach((branch,i)=>{const y=65+i*200,color=colors[i%4];svg.append(svgElement('path',{d:`M259 ${mid} C300 ${mid},300 ${y+30},340 ${y+30}`,fill:'none',stroke:color,'stroke-width':2.5}));card(340,y,220,60,branch.label,color);const children=branch.children||[];children.slice(0,4).forEach((child,j)=>{const yy=y-20+j*48;svg.append(svgElement('path',{d:`M560 ${y+30} C610 ${y+30},610 ${yy+20},650 ${yy+20}`,fill:'none',stroke:color,'stroke-width':1.4,opacity:.7}));card(650,yy,380,40,child.label,color)})});host.append(svg);
}
$('open-map').onclick=()=>{mapScale=1;drawMap();$('map-dialog').showModal()};$('map-close').onclick=()=>$('map-dialog').close();$('map-in').onclick=()=>{mapScale=Math.min(2,mapScale+.2);drawMap()};$('map-out').onclick=()=>{mapScale=Math.max(.6,mapScale-.2);drawMap()};$('map-fit').onclick=()=>{mapScale=1;drawMap()};$('map-ask').onclick=()=>{$('map-dialog').close();$('teaching-input').value='请根据我们当前项目、计划与讨论，用思维导图梳理整体目标、实现拆分和相关技术。标明待讨论与已确认，不直接给修复答案。';$('teaching-input').focus()};

let runtimeObservations=[],previewTaskId=null;
function showView(view){const runtime=view==='runtime';document.querySelector('.code-area').hidden=runtime;$('runtime-panel').hidden=!runtime;$('code-view').classList.toggle('view-active',!runtime);$('runtime-view').classList.toggle('view-active',runtime);$('filename').hidden=runtime;if(runtime)loadPreview()}
function loadPreview(){if(!task)return;previewTaskId=task.id;runtimeObservations=[];$('runtime-logs').replaceChildren();$('runtime-status').textContent='正在加载真实项目页面…';$('runtime-frame').src=task.preview_url+'?v='+Date.now()}
$('code-view').onclick=()=>showView('code');$('runtime-view').onclick=()=>showView('runtime');$('refresh-runtime').onclick=loadPreview;$('external-runtime').onclick=()=>window.open(task.preview_url,'_blank','noopener');
window.addEventListener('message',event=>{if(!task||event.source!==$('runtime-frame').contentWindow||event.origin!==new URL(task.preview_url,location.href).origin||event.data?.channel!=='control-preview'||event.data?.task_id!==task.id)return;const data=event.data;if(!['ready','error'].includes(data.type)||typeof data.message!=='string')return;runtimeObservations.push({type:data.type,message:data.message.slice(0,500),line:data.line||0});runtimeObservations=runtimeObservations.slice(-20);$('runtime-status').textContent=runtimeObservations.some(x=>x.type==='error')?'发现运行错误，展开查看详情':'页面已加载 · 请实际操作验证';const p=document.createElement('p');p.textContent=(data.type==='error'?'错误：':'状态：')+data.message+(data.line?'（第 '+data.line+' 行）':'');p.className=data.type==='error'?'runtime-error':'';$('runtime-logs').append(p)});
init();

function renderLearning(){
 const box=$('learning-view');box.replaceChildren();
 const add=text=>{const p=document.createElement('p');p.textContent=text;box.append(p)};
 const m=task.teaching?.memory||{};
 add('历史记忆：版本 '+(m.revision||0)+'，整理到消息 '+(m.covered_through??-1)+'；原话保留。-1表示尚未整理。');
 const levels={unknown:'尚未观察',needs_help:'仍需帮助',supported:'提示后能做',independent:'本情境可独立做（待复核）',transfer_candidate:'迁移表现待复核'};
 for(const row of task.learning_overview?.profile||[])add(row.title+'：'+(levels[row.level]||row.level)+' · '+row.evidence_count+'条原话证据');
 for(const card of task.teaching?.learning?.experiences||[]){
  const p=document.createElement('p');p.textContent='经验：'+card.title+' ['+card.status+']\n'+card.rule+'\n适用：'+card.when+'；验证：'+card.verification+'；限制：'+card.limits;box.append(p);
  for(const [action,label] of card.status==='draft'?[['confirm','我理解并保留'],['reject','不保留']]:card.status==='confirmed'?[['disable','停用']]:card.status==='disabled'?[['confirm','重新启用']]:[]){
   const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=()=>perform(()=>api('/tasks/'+task.id+'/experiences/'+card.id+'/'+action,{confirmed:true}));box.append(b);
  }
 }
 for(const skill of task.learning_overview?.skills||[]){
  add('候选Skill：'+skill.title+' · '+(skill.student_ready_for_review?'学生证据可申请复核':'学生证据待补充')+' · Coding效果未验证，未安装');
  if(skill.student_ready_for_review){const b=document.createElement('button');b.type='button';b.textContent='申请复核 '+skill.title;b.onclick=()=>perform(()=>api('/tasks/'+task.id+'/skill-unlocks/'+skill.id,{confirmed:true}));box.append(b)}
 }
}
$('export-learning').onclick=async()=>{
 try{const r=await fetch('/api/tasks/'+task.id+'/learning-record.md');if(!r.ok)throw Error('导出失败');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='Control-学习记录.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}
};

function renderCodingWorkflow(){
 const active=task.mode==='opencode';$('coding-workflow-panel').hidden=!active;if(!active)return;
 const w=task.coding_workflow||{};$('experience-toggle').checked=w.experience_enabled!==false;
 $('save-phase-draft').disabled=!!task.plan.length;
 $('coding-preflight').disabled=!task.plan.length;
 $('coding-trace').textContent='状态：'+(w.status||'planning')+'\n模型：'+(task.coding_provider?.model||'未选择')+'；执行器：'+(task.coding_provider?.installed?'已安装':'未安装')+'\n运行：'+(task.coding_run?.detail||'尚未执行')+'\n'+(w.events||[]).map(e=>e.id+'. '+e.kind+'：'+e.detail).join('\n')+'\n能力加载预检：'+JSON.stringify(w.loads||[],null,2)+'\n工具轨迹：'+JSON.stringify(w.tool_events||[],null,2);
}
$('new-opencode').onclick=()=>perform(()=>api('/tasks',{coding_mode:'opencode'}));
$('save-phase-draft').onclick=()=>perform(()=>api('/tasks/'+task.id+'/coding/plan-draft',{plan:$('phase-draft').value.split('\n').map(x=>x.trim()).filter(Boolean)}));
$('experience-toggle').onchange=()=>perform(()=>api('/tasks/'+task.id+'/coding/capabilities',{experience_enabled:$('experience-toggle').checked}));
$('coding-preflight').onclick=()=>perform(()=>api('/tasks/'+task.id+'/coding/preflight',{}));

$('coding-settings').onclick=()=>$('coding-settings-dialog').showModal();
$('coding-settings-close').onclick=()=>{$('coding-key').value='';$('coding-settings-dialog').close()};
$('coding-connect').onclick=async()=>{try{await api('/settings/coding',{api_key:$('coding-key').value,model:$('coding-model').value.trim(),region:$('coding-region').value});$('coding-key').value='';$('coding-settings-dialog').close();task=await api('/tasks/'+task.id);render();toast('Coding配置已保存；实际调用尚待验证')}catch(e){toast(e.message)}};
$('generate-phase-plan').onclick=()=>{const message=$('coding-input').value.trim();if(!message)return toast('先在Coding聊天输入框填写需求');perform(()=>api('/tasks/'+task.id+'/coding/generate-plan',{message}))};
