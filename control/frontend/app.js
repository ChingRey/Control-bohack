let highlightedRows=null;
let displayedCodeRefs=[];
const $=id=>document.getElementById(id);let task=null,file='app.js',busy=false,saved='',confirmMode='step';
function toast(text){$('toast').textContent=text;$('toast').style.display='block';clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('toast').style.display='none',3500)}
async function api(path,body){if(body&&task&&path.includes('/tasks/'+task.id+'/'))body={...body,runtime_observations:runtimeObservations};const r=await fetch('/api'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'请求失败');return data}
function hasCodeChanges(){return !!(task&&file&&Object.prototype.hasOwnProperty.call(task.files||{},file)&&$('code').value!==String(saved??''))}
function lines(){$('lines').textContent=$('code').value.split('\n').map((_,i)=>i+1).join('\n')}
function openFile(name){clearRowHighlight();if(hasCodeChanges()&&!confirm('当前文件尚未保存，放弃修改并切换？'))return;file=name;saved=task.files[file];$('code').value=saved;$('filename').textContent=file;lines();renderFiles()}
function renderFiles(){$('files').replaceChildren();Object.keys(task.files).forEach(name=>{const b=document.createElement('button');b.className=name===file?'active':'';const icon=document.createElement('em');icon.textContent=name.endsWith('.js')?'JS':name.endsWith('.css')?'#':'<>';b.append(icon,document.createTextNode(name));b.onclick=()=>openFile(name);$('files').append(b)})}
function render(){$('task-title').textContent=task.title||'新项目';$('project').textContent=task.title||'新项目';renderCodingWorkflow();if(!(file in task.files))file=Object.keys(task.files)[0]||'';renderFiles();saved=task.files[file]||'';$('code').value=saved;lines();$('filename').textContent=file||'空项目';$('code').disabled=!file;$('code').placeholder=file?'':'尚无文件，请在Coding聊天中描述你想开发的项目';$('save').disabled=!file;renderDevelopmentPlan();$('changes').textContent=task.changes.length?'已保存 '+task.changes.length+' 次代码修改':'尚无代码修改';renderChats();$('checks').textContent=task.checks.map(c=>(c.pass?'✓ ':'○ ')+c.name).join('\n');$('run').disabled=busy||!task.plan.length||task.step>=task.plan.length;renderTeacherStatus();if(previewTaskId&&previewTaskId!==task.id){runtimeObservations=[];previewTaskId=null;$('runtime-frame').src='about:blank';if(!$('runtime-panel').hidden)loadPreview()}$('connection').textContent='本地后端已连接 · SQLite 已保存';localStorage.setItem('control-workbench-task',task.id)}
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
$('code').oninput=()=>{clearRowHighlight();lines()};$('code').onscroll=()=>{$('lines').scrollTop=$('code').scrollTop;paintRowHighlight()};
$('save').onclick=async()=>{if(busy||!file||!(file in (task?.files||{})))return;busy=true;try{task=await api('/tasks/'+task.id+'/files',{path:file,content:$('code').value});render();toast('代码已保存')}catch(e){toast(e.message)}finally{busy=false}};
$('run').onclick=()=>{confirmMode='step';$('confirm').querySelector('p').textContent='确认后只执行当前一步，完成即暂停。';$('confirm-run').textContent='确认并执行';$('confirm').querySelector('h2').textContent='确认本步指令';$('instruction').value=task.plan[task.step];$('confirm').showModal()};$('cancel-dialog').onclick=()=>$('confirm').close();$('confirm-run').onclick=()=>{const instruction=$('instruction').value.trim();if(!instruction)return;$('confirm').close();if(confirmMode==='plan')perform(()=>api('/tasks/'+task.id+'/plan/confirm',{plan:instruction.split('\n').map(x=>x.trim()).filter(Boolean),confirmed:true}));else perform(()=>api('/tasks/'+task.id+'/steps/run',{instruction,confirmed:true,expected_step:task.step}))};$('verify').onclick=()=>perform(()=>api('/tasks/'+task.id+'/verify',{}));$('preview').onclick=()=>showView('runtime');document.querySelectorAll('[data-question]').forEach(b=>b.onclick=()=>{$('teaching-input').value=b.dataset.question;$('teaching-input').focus()});
async function init(){try{const id=localStorage.getItem('control-workbench-task');if(id){try{task=await api('/tasks/'+id)}catch{task=await api('/tasks',{coding_mode:'opencode'})}}else task=await api('/tasks',{coding_mode:'opencode'});render();if(['queued','running'].includes(task.teaching_run?.status)||['queued','running'].includes(task.coding_run?.status)){setBusy(true);try{await waitForTeacher()}finally{setBusy(false)}}}catch(e){$('connection').textContent='连接失败';toast(e.message)}}

function renderTeacherStatus(){
 const real=task.teaching_provider?.mode==='model';renderKnowledge();renderLearning();
 const course=task.teaching?.course;
 $('course-overview').textContent=course?('本教程：'+course.title+'\n当前目标：'+(task.teaching?.plan?.goal||'先了解你的判断')+'\n接着上次：'+(course.resume_note||'从当前项目开始审查')):'本项目持续教学 · 刷新后接着学';
 $('transfer-submit').hidden=!task.teaching?.pending_transfer;
 const plan=task.teaching?.plan||{};const turns=task.teaching?.turns||[];const last=turns[turns.length-1];
 const review=$('teacher-plan');review.replaceChildren();
 const addReview=(label,value,kind='')=>{const row=document.createElement('div');row.className='review-line '+kind;const title=document.createElement('span');title.textContent=label;const content=document.createElement('p');content.textContent=value;row.append(title,content);review.append(row)};
 addReview('本轮目标',plan.goal||'等待教师根据当前项目安排');
 addReview('下一步',plan.next_step||'先描述你的观察或提出需要审查的内容','next');
 const questions=plan.open_questions||[];addReview('待验证',questions.length?questions.join('；'):'尚无额外待验证项','pending');
 const evidence=document.createElement('details');evidence.className='review-evidence';const summary=document.createElement('summary');summary.textContent='查看审查依据';const body=document.createElement('div');const warnings=last?.result?.validation_warnings||[];body.textContent=(plan.reason?'依据：'+plan.reason+'\n':'')+'掌握状态：'+(task.teaching?.assessment||'未检查')+'（候选掌握仍待复核）\n'+(warnings.length?'校验提醒：'+warnings.join('；'):'当前没有引用校验提醒')+'\n本轮仅使用只读材料，不代表已执行测试。';evidence.append(summary,body);review.append(evidence);
 const settings=$('settings');
 settings.textContent=real?'已连接 · '+(task.teaching_provider?.model||'模型'):'连接模型';
 settings.classList.toggle('connected',real);
 settings.title=real?'Teaching Agent 已连接；点击可更换模型或配置':'连接 Teaching Agent 使用的模型';
  document.querySelector('footer > span:last-child').textContent='真实文件与记录 · Coding OpenCode · 学习记录保存在本地';
 const phases={observe:'观察现象',explain:'解释原因',propose:'提出改法',verify:'设计验证',transfer:'迁移检查'};
 const phase=phases[task.teaching?.phase]||'观察现象';
 document.querySelector('.teacher-context').textContent='当前学习重点：'+(task.teaching?.plan?.goal||phase);
 const record=$('learning-record');
 if(record)record.textContent='当前掌握状态：'+(task.teaching?.assessment||'未检查')+'\n已记录 '+(task.teaching?.turns?.length||0)+' 轮教学反馈、'+task.changes.length+' 次代码修改。';
 const learningSummary=$('learning-summary');
 if(learningSummary)learningSummary.textContent=(task.teaching?.plan?.goal||'查看本项目的目标、证据与技术选学')+' · '+(task.teaching?.assessment||'未检查');
}

function setProviderForm(provider,model){
 $('provider-choice').value=provider;$('api-key').value='';$('endpoint').value=provider==='openai'?'https://api.openai.com/v1/responses':'https://api.deepseek.com/chat/completions';
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
function resolveCodeLocation(name,snippet='',requestedLine=null){
 const source=task.files?.[name];if(typeof source!=='string')return null;
 const lines=source.split('\n');const meaningful=line=>line.trim()&&!/^\s*(?:\/\/|\/\*|\*|<!--|-->)/.test(line);
 if(snippet.trim()){
  const block=snippet.trim();const first=source.indexOf(block);
  if(first>=0&&source.indexOf(block,first+1)<0){const offset=block.split('\n').findIndex(meaningful);return {line:source.slice(0,first).split('\n').length+Math.max(0,offset),kind:'片段匹配'};}
  const candidates=snippet.split('\n').filter(meaningful);
  for(const candidate of candidates){const matches=lines.map((v,i)=>v.trim()===candidate.trim()?i:-1).filter(i=>i>=0);if(matches.length===1)return {line:matches[0]+1,kind:'片段匹配'};}
 }
 const requested=Number(requestedLine);
 if(requestedLine&&Number.isInteger(requested)&&requested>=1&&requested<=lines.length)return {line:requested,kind:'模型引用'};
 const change=[...(task.changes||[])].reverse().find(c=>c.file===name&&c.after===source);
 if(change){const old=(change.before||'').split('\n');let i=0;while(i<lines.length&&i<old.length&&lines[i]===old[i])i++;for(let j=i;j<lines.length;j++)if(meaningful(lines[j]))return {line:j+1,kind:'最近改动附近'};}
 return null;
}
function clearRowHighlight(){highlightedRows=null;$('code').style.backgroundImage='none';}
function paintRowHighlight(){
 const editor=$('code');if(!highlightedRows||highlightedRows.file!==file){editor.style.backgroundImage='none';return;}
 const style=getComputedStyle(editor),height=parseFloat(style.lineHeight),padding=parseFloat(style.paddingTop)||0;
 const top=padding+(highlightedRows.start-1)*height-editor.scrollTop,bottom=padding+highlightedRows.end*height-editor.scrollTop;
 if(bottom<=0||top>=editor.clientHeight){editor.style.backgroundImage='none';return;}
 const a=Math.max(0,top),b=Math.max(0,bottom);
 editor.style.backgroundImage=`linear-gradient(to bottom,transparent ${a}px,rgba(111,137,173,.23) ${a}px,rgba(111,137,173,.23) ${b}px,transparent ${b}px)`;
}
function jumpToCode(name,lineNumber=null,endLine=null){
 if(!(name in (task.files||{})))return toast('该文件尚未生成');
 if(hasCodeChanges()&&!confirm('当前文件有未保存修改，放弃并打开目标文件？'))return;
 showView('code');openFile(name);const editor=$('code'),lines=editor.value.split('\n');
 if(lineNumber){const line=Math.min(lines.length,Math.max(1,lineNumber));const start=lines.slice(0,line-1).reduce((n,v)=>n+v.length+1,0);editor.focus();editor.setSelectionRange(start,start);highlightedRows={file:name,start:line,end:Math.min(lines.length,endLine||line)};editor.scrollTop=Math.max(0,line-3)*parseFloat(getComputedStyle(editor).lineHeight);paintRowHighlight();}
 else{editor.focus();editor.setSelectionRange(0,0);toast('已打开文件，原回复未提供可核实的代码位置');}
 editor.scrollIntoView({behavior:'smooth',block:'center'});
}
function fileReference(el,name,snippet='',requestedLine=null,requestedEnd=null){
 const exists=Object.prototype.hasOwnProperty.call(task.files||{},name);let location=exists?resolveCodeLocation(name,snippet,null):null;let reason='';
 if(requestedLine){const ref=displayedCodeRefs.find(r=>r.file===name&&r.start===Number(requestedLine)&&r.end===Number(requestedEnd||requestedLine));if(ref?.valid&&ref.hash===task.file_hashes?.[name])location={line:ref.start,end:ref.end,kind:'版本核验'};else{location=null;reason=ref?.valid?' · 引用已过期':' · 位置未核验';}}
 const button=document.createElement('button');button.type='button';button.className='code-reference';button.textContent=exists?'↗ '+name+(location?' · 第 '+location.line+(location.end&&location.end!==location.line?'-'+location.end:'')+' 行 · '+location.kind:' · 打开文件'+reason):name+'（尚未生成）';button.disabled=!exists;button.onclick=()=>jumpToCode(name,location?.line,location?.end);el.append(button);
}
function linkedText(el,text){
 const pattern=/([A-Za-z0-9_./-]+\.(?:html|css|js|ts|tsx|jsx|json|py|md))(?:[:：](\d+)(?:[-–](\d+))?)?/g;let from=0,m;
 while((m=pattern.exec(text))){inlineText(el,text.slice(from,m.index));fileReference(el,m[1],'',m[2],m[3]);from=pattern.lastIndex}inlineText(el,text.slice(from));
}
function formatMessage(el,text){
 let fence=false,code=[],lastFile=null,unfenced=false;
 const emitCode=()=>{if(!code.length)return;const known=lastFile||Object.keys(task.files||{}).find(name=>{const first=code.find(x=>x.trim());return first&&task.files[name].includes(first)})||null;
  const p=document.createElement('p');if(known)fileReference(p,known,code.join('\n'));else p.textContent='代码未在聊天中展开；尚无法定位到已生成的项目文件。';el.append(p);code=[];};
 for(const line of text.split('\n')){
  if(/^\s*```/.test(line)){if(fence){emitCode();fence=false}else fence=true;continue}
  if(fence){code.push(line);continue}
  if(!unfenced&&/^\s*(?:const |let |var |function |class |import |<!doctype|<html|\/\/)/i.test(line))unfenced=true;
  if(unfenced){code.push(line);continue}
  const ref=line.match(/([A-Za-z0-9_./-]+\.(?:html|css|js|ts|tsx|jsx|json|py|md))/);if(ref)lastFile=ref[1];
  if(!line.trim())continue;const p=document.createElement(/^#{1,4} /.test(line)?'h4':'p');linkedText(p,line.replace(/^#{1,4} /,''));el.append(p);
 }
 emitCode();
}
function messageNode(m,ch){displayedCodeRefs=m.code_refs||[];const div=document.createElement('div');div.className='msg '+m.role;const b=document.createElement('b');b.textContent=m.role==='user'?'你':ch==='coding'?(task.mode==='opencode'?(task.coding_provider?.configured?'Coding · OpenCode':'Coding · OpenCode（待配置）'):'Coding Agent · 示例'):m.engine==='model'?'Teaching Agent':'Teaching Agent · 示例';div.append(b);const content=document.createElement('div');content.className='message-content';if(m.role==='user'){const p=document.createElement('p');p.textContent=m.content;content.append(p)}else if(m.content.startsWith('Teaching Agent 暂时未完成本次分析：')){const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='历史调用未完成（保留原始记录）';details.append(summary,document.createTextNode(m.content));content.append(details)}else formatMessage(content,m.content);div.append(content);return div}
function waitingNode(text){const row=document.createElement('div');row.className='waiting';row.setAttribute('role','status');row.textContent='◌ '+text;return row}
function renderChats(){
 for(const ch of ['coding','teaching']){const el=$(ch+'-messages');const nearBottom=el.scrollHeight-el.scrollTop-el.clientHeight<100;el.replaceChildren();task.messages.filter(m=>m.channel===ch).forEach(m=>el.append(messageNode(m,ch)));
  if(ch==='coding'&&task.coding_run){const run=task.coding_run;if(['queued','running'].includes(run.status))el.append(waitingNode(run.detail||'Coding执行中'));if(run.status==='failed'){const error=document.createElement('p');error.className='reply-error';error.textContent=run.detail||'执行失败，阶段未推进';el.append(error)}}
  if(ch==='teaching'){
   const run=task.teaching_run;
   if(run&&['queued','running'].includes(run.status)){const elapsed=Math.max(0,Math.floor(Date.now()/1000-run.started_at));el.append(waitingNode((run.detail||'教师正在处理')+' · '+elapsed+' 秒'));}
   if(run?.status==='failed'){const box=document.createElement('div');box.className='reply-error';const p=document.createElement('p');p.textContent=run.detail||'回复未完成，消息已保存';const retry=document.createElement('button');retry.textContent='重试回复';retry.onclick=()=>perform(()=>api('/tasks/'+task.id+'/teaching/review',{}));box.append(p,retry);const detail=document.createElement('details');const title=document.createElement('summary');title.textContent='查看错误详情';detail.append(title,document.createTextNode(run.error||''));box.append(detail);el.append(box)}
  }
  if(nearBottom)el.scrollTop=el.scrollHeight;
 }
}

function splitParagraph(text){const sentences=text.match(/[^。！？]+[。！？]?[”’」』]?/g)||[text];const groups=[];let chunk='';for(const sentence of sentences){chunk+=sentence;if(chunk.length>=75){groups.push(chunk);chunk=''}}if(chunk)groups.push(chunk);return groups.join('\n')}

const layoutRoot=document.querySelector('.workspace');
const filePanel=document.querySelector('.files');const fileLabel=filePanel?.querySelector('.label');
if(filePanel&&fileLabel){const sidebarToggle=document.createElement('button');sidebarToggle.type='button';sidebarToggle.className='sidebar-toggle';sidebarToggle.title='收起工作区';sidebarToggle.textContent='‹';fileLabel.append(sidebarToggle);const applySidebar=()=>{const collapsed=localStorage.getItem('control-sidebar-collapsed')==='true';document.body.classList.toggle('sidebar-collapsed',collapsed);sidebarToggle.textContent=collapsed?'›':'‹';sidebarToggle.title=collapsed?'展开工作区':'收起工作区';fileLabel.firstChild.textContent=collapsed?'☰':'工作区 '};applySidebar();sidebarToggle.onclick=()=>{localStorage.setItem('control-sidebar-collapsed',String(!document.body.classList.contains('sidebar-collapsed')));applySidebar()}}
let layout={teacher:390,codeRatio:54};
try{layout={...layout,...JSON.parse(localStorage.getItem('control-layout')||'{}')}}catch{}
function applyLayout(){layout.teacher=Math.max(300,Math.min(620,Number(layout.teacher)||390));layout.codeRatio=Math.max(30,Math.min(70,Number(layout.codeRatio)||54));layoutRoot.style.setProperty('--teacher',layout.teacher+'px');layoutRoot.style.setProperty('--code-ratio',layout.codeRatio+'fr');layoutRoot.style.setProperty('--chat-ratio',(100-layout.codeRatio)+'fr')}
function persistLayout(){localStorage.setItem('control-layout',JSON.stringify(layout))}
document.querySelectorAll('.splitter').forEach(handle=>{
 const adjust=(delta)=>{if(handle.dataset.split==='height')layout.codeRatio+=delta;else layout.teacher-=delta;applyLayout()};
 handle.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();handle.setPointerCapture(e.pointerId);let lastX=e.clientX,lastY=e.clientY;document.body.classList.add('resizing');handle.onpointermove=event=>{if(!handle.hasPointerCapture(event.pointerId))return;if(handle.dataset.split==='height'){const height=document.querySelector('.center').clientHeight;adjust((event.clientY-lastY)/height*100);lastY=event.clientY}else{adjust(event.clientX-lastX);lastX=event.clientX}};const stop=()=>{document.body.classList.remove('resizing');handle.onpointermove=null;persistLayout()};handle.onpointerup=stop;handle.onlostpointercapture=stop;};
 handle.onkeydown=e=>{const height=handle.dataset.split==='height';const minus=height?'ArrowUp':'ArrowLeft',plus=height?'ArrowDown':'ArrowRight';if(e.key===minus||e.key===plus){e.preventDefault();adjust((e.key===plus?1:-1)*(height?3:20));persistLayout()}};
});
$('open-settings').onclick=()=>$('settings').click();window.addEventListener('resize',applyLayout);applyLayout();
function planProgress(){
 const steps=(task.plan?.length?task.plan:task.plan_draft)||[];
 if(task.plan?.length)return steps.map((text,i)=>{const status=task.coding_workflow?.checkpoints?.[i]?.status;return {text,state:status==='accepted_by_student'?'done':status==='executed_pending_review'?'review':i===task.step&&['queued','running'].includes(task.coding_run?.status)?'active':'pending'}});
 let todos=[];
 for(const event of task.coding_workflow?.tool_events||[]){const p=event.part||{};if(p.tool==='todowrite'&&Array.isArray(p.state?.input?.todos))todos=p.state.input.todos;}
 return steps.map((text,i)=>{const matches=todos.filter(t=>t.content===text);const status=matches.length===1?matches[0].status:null;
  return {text,state:status==='completed'?'review':status==='in_progress'?'active':status==='cancelled'?'cancelled':status==='pending'?'pending':task.plan.length&&task.plan[i]===text&&i<task.step?'review':'pending'};
 });
}
function renderDevelopmentPlan(){
 const rows=planProgress(),done=rows.filter(x=>x.state==='done').length,reported=rows.filter(x=>x.state==='review').length,allDone=rows.length>0&&done===rows.length;
 const planKey=rows.map(x=>x.text).join('\n');if(rows.length&&$('plan-panel').dataset.planKey!==planKey){$('plan-panel').open=true;$('plan-panel').dataset.planKey=planKey}
 $('steps').replaceChildren();
 function row(number,title,note,status){const li=document.createElement('li');li.className='milestone is-'+status;if(status==='active')li.setAttribute('aria-current','step');const n=document.createElement('strong');n.textContent=status==='done'?'✓':number;const body=document.createElement('div');const name=document.createElement('div');name.textContent=title;body.append(name);const small=document.createElement('small');small.textContent=note;body.append(small);li.append(n,body);$('steps').append(li);return body;}
 row('1','设置计划',rows.length?'计划已形成，可继续在聊天中调整':'在Coding聊天中交流目标',rows.length?'done':'active');
 const body=row('2','开发计划',allDone?'任务清单已完成，仍可检查与修改':rows.length?'已通过 '+done+' / '+rows.length+' · 待检查 '+reported:'等待生成',allDone?'done':rows.length?'active':'pending');
 const list=document.createElement('ol');list.className='phase-progress';const labels={done:'已完成',active:'进行中',pending:'未开始',review:'报告完成 · 待检查',cancelled:'已取消'};
 rows.forEach((entry,i)=>{const item=document.createElement('li');item.className='phase-row is-'+entry.state+(entry.state==='done'?' done':entry.state==='active'?' current':'');if(entry.state==='active')item.setAttribute('aria-current','step');const num=document.createElement('b');num.className='phase-number';num.textContent=String(i+1);num.setAttribute('aria-label','第'+(i+1)+'项');const content=document.createElement('div');const title=document.createElement('span');title.textContent=entry.text;const status=document.createElement('small');status.textContent=labels[entry.state];content.append(title,status);const marker=document.createElement('span');marker.className='phase-marker';marker.textContent=entry.state==='active'?'◉':entry.state==='done'?'✓':entry.state==='review'?'○':'';marker.setAttribute('aria-label',labels[entry.state]);item.append(num,content,marker);list.append(item)});body.append(list);
 row('3','总结','暂不展开','pending');
 $('progress').textContent=rows.length?done+' / '+rows.length+' 已通过':'待设置';
 $('stage').textContent=['queued','running'].includes(task.coding_run?.status)?'● Coding处理中':allDone?'● 任务清单已完成':rows.length?'● 等待交流与审查':'● 等待需求';
 $('plan-confirm').hidden=true;$('run').hidden=true;
}
$('plan-confirm').onclick=()=>{confirmMode='plan';$('confirm').querySelector('p').textContent='先与教师讨论整体目标和拆分。确认后只保存计划，不执行代码。';$('confirm-run').textContent='确认计划';$('confirm').querySelector('h2').textContent='编辑并确认开发计划（每行一步）';$('instruction').value=(task.plan_draft||[]).join('\n');$('confirm').showModal()};
$('restart-example').onclick=()=>{if(confirm('新建空白项目？当前记录会保留。'))perform(()=>api('/tasks',{coding_mode:'opencode'}))};
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
 for(const item of task.project_knowledge||[]){
  add('项目知识：'+item.title+' ['+item.status+']\n'+item.content);
  const actions=item.status==='pending_review'?[['approve','审核采用'],['reject','不采用']]:item.status==='approved'?[['withdraw','停用']]:item.status==='withdrawn'?[['approve','重新启用']]:[];
  for(const [decision,label] of actions){const button=document.createElement('button');button.textContent=label;button.onclick=()=>perform(()=>api('/tasks/'+task.id+'/knowledge/'+item.id+'/review',{confirmed:true,decision,reviewer:'local_student'}));box.append(button)}
 }
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
$('add-project-knowledge').onclick=()=>{const title=$('knowledge-title').value.trim(),content=$('knowledge-content').value.trim();if(!title||!content)return toast('请填写标题与经验内容');perform(()=>api('/tasks/'+task.id+'/knowledge/manual',{title,content,confirmed:true}))};
$('knowledge-enabled').onchange=()=>perform(()=>api('/tasks/'+task.id+'/knowledge/settings',{enabled:$('knowledge-enabled').checked}));
$('export-learning').onclick=async()=>{
 try{const r=await fetch('/api/tasks/'+task.id+'/learning-record.md');if(!r.ok)throw Error('导出失败');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='Control-学习记录.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}
};

function renderCodingWorkflow(){$('knowledge-enabled').checked=task.knowledge_enabled!==false;}
$('coding-settings').onclick=()=>{$('settings-dialog').close();$('coding-settings-dialog').showModal()};
$('coding-settings-close').onclick=()=>{$('coding-key').value='';$('coding-settings-dialog').close()};
$('coding-connect').onclick=async()=>{try{await api('/settings/coding',{api_key:$('coding-key').value,model:$('coding-model').value.trim(),region:$('coding-region').value});$('coding-key').value='';$('coding-settings-dialog').close();task=await api('/tasks/'+task.id);render();toast('Coding配置已保存；实际调用尚待验证')}catch(e){toast(e.message)}};


$('open-learning').onclick=()=>$('learning-dialog').showModal();$('close-learning').onclick=()=>$('learning-dialog').close();
const reviewCard=document.querySelector('.review-card');const reviewTitle=document.querySelector('.review-title');
if(reviewCard&&reviewTitle){reviewCard.classList.add('collapsed');const toggleButton=document.createElement('button');toggleButton.type='button';toggleButton.className='review-toggle';toggleButton.textContent='查看审查';toggleButton.setAttribute('aria-expanded','false');reviewTitle.insertBefore(toggleButton,$('review-teaching'));const toggleReview=()=>{const collapsed=reviewCard.classList.toggle('collapsed');toggleButton.textContent=collapsed?'查看审查':'收起审查';toggleButton.setAttribute('aria-expanded',String(!collapsed))};toggleButton.onclick=toggleReview}

