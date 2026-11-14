// randomUUID is unavailable on plain-HTTP LAN origins; getRandomValues remains supported.
function newRequestId(){
 if(typeof globalThis.crypto?.randomUUID==='function')return globalThis.crypto.randomUUID();
 const bytes=new Uint8Array(16);globalThis.crypto.getRandomValues(bytes);bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
 const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);
}
let highlightedRows=null;
let displayedCodeRefs=[];
const $=id=>document.getElementById(id);let task=null,file='app.js',busy=false,saved='',confirmMode='step';
function toast(text){$('toast').textContent=text;$('toast').style.display='block';clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('toast').style.display='none',3500)}
async function api(path,body){if(body&&task&&path.includes('/tasks/'+task.id+'/'))body={...body,runtime_observations:runtimeObservations};const r=await fetch('/api'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'请求失败');return data}
function hasCodeChanges(){return !!(task&&file&&Object.prototype.hasOwnProperty.call(task.files||{},file)&&$('code').value!==String(saved??''))}
function lines(){$('lines').textContent=$('code').value.split('\n').map((_,i)=>i+1).join('\n');paintRowHighlight()}
function openFile(name){clearRowHighlight();if(hasCodeChanges()&&!confirm('当前文件尚未保存，放弃修改并切换？'))return;file=name;saved=task.files[file];$('code').value=saved;$('filename').textContent=file;lines();renderFiles()}
function renderFiles(){$('files').replaceChildren();Object.keys(task.files).forEach(name=>{const b=document.createElement('button');b.className=name===file?'active':'';const icon=document.createElement('em');icon.textContent=name.endsWith('.js')?'JS':name.endsWith('.css')?'#':'<>';b.append(icon,document.createTextNode(name));b.onclick=()=>openFile(name);$('files').append(b)})}
function render(){const dirty=hasCodeChanges()&&task.files[file]!==$('code').value,draft=dirty?$('code').value:null,oldFile=file,oldSaved=saved;$('task-title').textContent=task.title||'新项目';$('project').textContent=task.title||'新项目';renderCodingWorkflow();if(!(file in task.files))file=Object.keys(task.files)[0]||'';renderFiles();saved=task.files[file]||'';$('code').value=saved;lines();$('filename').textContent=file||'空项目';$('code').disabled=!file;$('code').placeholder=file?'':'尚无文件，请在Coding聊天中描述你想开发的项目';$('save').disabled=!file;renderDevelopmentPlan();$('changes').textContent=task.changes.length?'已保存 '+task.changes.length+' 次代码修改':'尚无代码修改';renderChats();$('checks').textContent=task.checks.map(c=>(c.pass?'✓ ':'○ ')+c.name).join('\n');$('run').disabled=busy||!task.plan.length||task.step>=task.plan.length;renderTeacherStatus();if(previewTaskId&&previewTaskId!==task.id){runtimeObservations=[];previewTaskId=null;$('runtime-frame').src='about:blank';if(!$('runtime-panel').hidden)loadPreview()}$('connection').textContent='本地后端已连接 · SQLite 已保存';localStorage.setItem('control-workbench-task',task.id);if(dirty&&file===oldFile){$('code').value=draft;saved=oldSaved;lines()}if(window.renderWorkflow)window.renderWorkflow();if(window.renderTeachingEvolution)window.renderTeachingEvolution()}
function setBusy(value){busy=value;document.querySelectorAll('#run,#save,#review-teaching,#evaluate-teaching,#verify,#plan-confirm,#restart-example,#knowledge-topics button,.plan-choice').forEach(b=>b.disabled=value);if(!value&&task){$('run').disabled=!task.plan.length||task.step>=task.plan.length;$('save').disabled=!file;renderChats()}}
async function waitForCoding(){
 while(['coding_run','verification_run'].some(k=>['queued','running'].includes(task[k]?.status))){
  await new Promise(r=>setTimeout(r,900));
  task=await api('/tasks/'+task.id);render();
 }
 if(task.coding_run?.status==='failed')toast(task.coding_run.detail||'Coding执行失败，阶段未推进');
 if(task.teaching_run?.status==='failed')toast('本次回复未完成，消息已保存，可点击重试');
 if(['queued','running'].includes(task.organizer_run?.status))pollChat();
}
async function perform(fn,optimistic){
 if(busy)return false;
 if(hasCodeChanges()){toast('请先保存代码修改，再发送或执行');return false}
 setBusy(true);
 if(optimistic){const el=$(optimistic.channel+'-messages');el.append(messageNode({role:'user',content:optimistic.message},optimistic.channel));el.append(waitingNode('正在发送并保存你的消息…'));el.scrollTop=el.scrollHeight;}
 $('connection').textContent='正在发送…';
 try{task=await fn();render();await waitForCoding();pollChat();return true}
 catch(e){toast(e.message);$('connection').textContent='连接异常，可重试';if(task)render();return false}
 finally{setBusy(false)}
}
async function codingChat(message){
 if(task.mode==='opencode')return api('/tasks/'+task.id+'/coding/messages',{message});
 return api('/tasks/'+task.id+'/'+(!task.plan.length?'plan':'coding/messages'),{message});
}
let chatPolling=false;
async function pollChat(){if(chatPolling)return;chatPolling=true;try{while(task&&(busy||['coding_run','teaching_run','organizer_run','verification_run','experience_run'].some(k=>['queued','running'].includes(task[k]?.status))||task.messages.some(m=>m.queue_status==='queued'))){await new Promise(r=>setTimeout(r,['queued','running'].includes(task.teaching_run?.status)?350:900));if(!task)break;const polledId=task.id,next=await api('/tasks/'+polledId);if(task?.id!==polledId)continue;task=next;render()}}catch(e){toast(e.message)}finally{chatPolling=false}}
for(const ch of ['coding','teaching'])$(ch+'-form').onsubmit=async e=>{
 e.preventDefault();const input=$(ch+'-input'),message=input.value.trim();if(!message||!task)return;
 const request_id=input.dataset.requestId||newRequestId();input.dataset.requestId=request_id;
 try{task=await api('/tasks/'+task.id+'/chat/send',{channel:ch,message,request_id});input.value='';delete input.dataset.requestId;render();pollChat()}
 catch(e){toast(e.message)}
};
// Share keyboard sending behavior across both chat composers.
for(const channel of ['coding','teaching']){
 const input=$(channel+'-input'),form=$(channel+'-form');
 let composing=false;
 input.addEventListener('compositionstart',()=>{composing=true});
 input.addEventListener('compositionend',()=>{composing=false});
 input.addEventListener('keydown',event=>{
  if(event.key!=='Enter'||event.shiftKey||event.isComposing||composing||event.keyCode===229)return;
  event.preventDefault();
  if(!event.repeat&&input.value.trim())form.querySelector('button.primary').click();
 });
}

$('code').oninput=()=>{clearRowHighlight();lines()};$('code').onscroll=()=>{$('lines').scrollTop=$('code').scrollTop;paintRowHighlight()};
$('save').onclick=async()=>{if(busy||!file||!(file in (task?.files||{})))return;busy=true;try{task=await api('/tasks/'+task.id+'/files',{path:file,content:$('code').value});render();toast('代码已保存')}catch(e){toast(e.message)}finally{busy=false}};
$('run').onclick=()=>{confirmMode='step';$('confirm').querySelector('p').textContent='确认后只执行当前一步，完成即暂停。';$('confirm-run').textContent='确认并执行';$('confirm').querySelector('h2').textContent='确认本步指令';$('instruction').value=task.plan[task.step];$('confirm').showModal()};$('cancel-dialog').onclick=()=>$('confirm').close();$('confirm-run').onclick=()=>{const instruction=$('instruction').value.trim();if(!instruction)return;$('confirm').close();if(confirmMode==='plan')perform(()=>api('/tasks/'+task.id+'/plan/confirm',{plan:instruction.split('\n').map(x=>x.trim()).filter(Boolean),confirmed:true}));else perform(()=>api('/tasks/'+task.id+'/steps/run',{instruction,confirmed:true,expected_step:task.step}))};document.querySelectorAll('[data-question]').forEach(b=>b.onclick=()=>{$('teaching-input').value=b.dataset.question;$('teaching-input').focus()});
let demoStudent=null;
async function init(){await showProjectHome()}
async function enterProject(id){
 if(hasCodeChanges()&&!confirm('当前代码尚未保存，放弃修改并切换项目？'))return;
 try{const next=await api('/tasks/'+encodeURIComponent(id));task=next;file='';saved='';diffHighlightEnabled=false;render();document.body.classList.remove('home-open');pollChat();window.dispatchEvent(new Event('resize'))}catch(e){toast(e.message)}
}
async function createHomeProject(){
 if(hasCodeChanges())return toast('请先保存代码修改');
 try{const next=await api('/tasks',{coding_mode:'opencode',student_id:demoStudent?.id});await enterProject(next.id)}catch(e){toast(e.message)}
}
async function showProjectEvidence(id){
 try{
 const project=await api('/tasks/'+encodeURIComponent(id)),state=project.teaching_evolution||{},dialog=document.createElement('dialog');dialog.className='project-evidence';
 const add=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;dialog.append(n);return n};
 add('h2',project.title);add('p',`${project.messages?.length||0} 条对话 · ${project.changes?.length||0} 次代码改动 · ${state.reviews?.length||0} 次教学反思`);
 add('p','下面是实际保存的反思、评价与经验版本。经验增加不等于教学效果已提升；需结合后续学习表现验证。');
 for(const entry of (state.entries||[]).filter(e=>e.source_project)){add('p',`跨项目试用：${entry.title} · 来源项目 ${entry.source_project} / v${entry.source_revision}（本项目效果待验证）`)}
 for(const r of state.reviews||[]){const details=document.createElement('details'),title=document.createElement('summary');title.textContent=`经验 v${r.playbook_before} → v${r.playbook_after} · 对话 ${r.from_id}—${r.through_id} · ${r.verified?'已有验证标记':'待验证'}`;const pre=document.createElement('pre');pre.textContent=JSON.stringify({scores:r.scores,evaluation:r.evaluation,reflection:r.reflection,changes:r.changes},null,2);details.append(title,pre);dialog.append(details)}
 if(!state.reviews?.length)add('p','这个项目还没有保存教学反思。');
 const close=add('button','关闭');close.onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
 }catch(e){toast(e.message)}
}
async function chooseProjectExperience(targetId){
 try{
 const target=await api('/tasks/'+targetId),projects=(await api('/tasks')).filter(p=>p.id!==targetId&&p.student_id===target.workflow?.student_id);
 const dialog=document.createElement('dialog');dialog.className='project-evidence';
 const add=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;dialog.append(n);return n};
 add('h2','选择要引用的教法');add('p','只引用同一学生其他项目的非初始教法。所选项作为试用保存，是否有效还需在本项目验证。');
 const select=add('select','');select.setAttribute('aria-label','来源项目');for(const p of projects)select.add(new Option(p.title,p.id));
 const list=add('div','');let source=null;const choices=[];
 const refresh=async()=>{list.replaceChildren();choices.length=0;if(!select.value){list.textContent='没有可用的同学生项目';return}source=await api('/tasks/'+select.value);for(const e of source.teaching_evolution?.entries||[]){if(e.origin==='seed'||!['active','trial'].includes(e.status))continue;const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.style.width='auto';box.style.display='inline';label.append(box,document.createTextNode(e.title+' · v'+e.revision));list.append(label);choices.push({box,id:e.id})}if(!choices.length)list.textContent='这个项目尚无可引用的教法。'};
 select.onchange=()=>refresh().catch(e=>toast(e.message));
 const confirm=add('button','引用所选教法（试用）');confirm.onclick=async()=>{try{const selected=choices.filter(x=>x.box.checked).map(x=>x.id);if(!selected.length)return toast('请先选择教法');const result=await api('/tasks/'+targetId+'/teaching/experience-import',{confirmed:true,expected_revision:target.teaching_evolution.revision,source_project:source.id,source_revision:source.teaching_evolution.revision,entry_ids:selected});if(task?.id===targetId){task=result;render()}dialog.close();toast('已引用为试用，效果待验证')}catch(e){toast(e.message)}};
 add('button','关闭').onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();await refresh();
 }catch(e){toast(e.message)}
}
function editProjectName(id,current){
 const dialog=document.createElement('dialog'),heading=document.createElement('h2'),form=document.createElement('form'),input=document.createElement('input'),save=document.createElement('button'),cancel=document.createElement('button');
 heading.textContent='项目名称';input.value=current;input.maxLength=60;input.required=true;input.setAttribute('aria-label','项目名称');save.textContent='保存';save.className='primary';cancel.textContent='取消';cancel.type='button';cancel.onclick=()=>dialog.close();
 form.append(input,save,cancel);form.onsubmit=async event=>{event.preventDefault();try{const updated=await api('/tasks/'+id+'/project/rename',{title:input.value});if(task?.id===id){task=updated;render()}dialog.close();showProjectHome()}catch(e){toast(e.message)}};
 dialog.append(heading,form);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();input.focus();input.select();
}
async function showProjectHome(){
 document.body.classList.add('home-open');let home=$('project-home');
 if(!home){home=document.createElement('main');home.id='project-home';document.body.append(home)}
 home.replaceChildren();const node=(tag,text,parent=home)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n};
 node('p','CONTROL · 学生工作台').className='home-eyebrow';node('h1','从一个想法，做出自己的作品。');node('p','你的项目、对话和学习记录保存在当前服务中，下次可以接着做。');
 node('div','演示学生 · 共享演示身份（未接入真实登录）').className='demo-identity';
 const start=node('button','＋ 开始新项目');start.className='primary';start.onclick=createHomeProject;
 node('h2','我的项目与课程历史');const grid=node('div','');grid.className='project-grid';
 try{demoStudent=await api('/demo-student',{confirmed:true});const projects=(await api('/tasks')).filter(p=>!p.student_id||p.student_id===demoStudent.id);document.querySelector('.demo-identity').textContent='演示学生 · 未关联项目需手动确认，跨项目教法需手动选择';
 const last=localStorage.getItem('control-workbench-task');projects.sort((a,b)=>(Number(b.updated_at)||0)-(Number(a.updated_at)||0));
 if(!projects.length)node('p','还没有项目，开始你的第一节实践课。',grid);
 for(const project of projects){const card=node('article','',grid);node('span',project.id===last?'上次学习':'已保存项目',card).className='home-eyebrow';node('h3',project.title,card);const rename=node('button','重命名',card);rename.className='project-rename';rename.onclick=()=>editProjectName(project.id,project.title);node('p',project.phases===undefined?'项目已保存，打开后继续原来的代码与对话':`阶段 ${project.step||0}/${project.phases||0} · ${project.messages||0} 条对话 · ${project.reviews||0} 次反思`,card);const go=node('button','继续学习 →',card);go.onclick=()=>enterProject(project.id);if(!project.student_id){const attach=node('button','关联到演示学生',card);attach.onclick=async()=>{try{await api('/tasks/'+project.id+'/student/attach',{student_id:demoStudent.id,confirmed:true});showProjectHome()}catch(e){toast(e.message)}}}else{const reuse=node('button','选择已有教法',card);reuse.onclick=()=>chooseProjectExperience(project.id)}const evidence=node('button','查看教学记录',card);evidence.onclick=()=>showProjectEvidence(project.id)}
 }catch(e){node('p','项目列表加载失败：'+e.message,grid);const retry=node('button','重新加载',grid);retry.onclick=showProjectHome}
}


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
  document.querySelector('footer > span:last-child').textContent='真实文件与记录 · Coding OpenCode · 学习记录保存在本地';
 const phases={observe:'观察现象',explain:'解释原因',propose:'提出改法',verify:'设计验证',transfer:'迁移检查'};
 const phase=phases[task.teaching?.phase]||'观察现象';
 document.querySelector('.teacher-context').textContent='当前学习重点：'+(task.teaching?.plan?.goal||phase);
 const record=$('learning-record');
 if(record)record.textContent='当前掌握状态：'+(task.teaching?.assessment||'未检查')+'\n已记录 '+(task.teaching?.turns?.length||0)+' 轮教学反馈、'+task.changes.length+' 次代码修改。';
 const learningSummary=$('learning-summary');
 if(learningSummary)learningSummary.textContent=(task.teaching?.plan?.goal||'查看本项目的目标、证据与技术选学')+' · '+(task.teaching?.assessment||'未检查');
}

$('close-settings').onclick=()=>$('settings-dialog').close();


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
let diffHighlightEnabled=false;
function clearRowHighlight(){highlightedRows=null;$('code').style.backgroundImage='none';paintRowHighlight();}
function paintRowHighlight(){
 const editor=$('code');
 $('project-diff').classList.toggle('diff-active',diffHighlightEnabled);$('project-diff').setAttribute('aria-pressed',String(diffHighlightEnabled));
 if(diffHighlightEnabled){
  const change=[...(task?.changes||[])].reverse().find(c=>c.file===file&&!c.binary&&!c.deleted);
  const current=editor.value.split('\n'),before=(change?.before||'').split('\n');let start=0,end=current.length,oldEnd=before.length;
  while(start<end&&start<oldEnd&&current[start]===before[start])start++;
  while(end>start&&oldEnd>start&&current[end-1]===before[oldEnd-1]){end--;oldEnd--}
  const changed=[];
  if(change&&(end-start)*(oldEnd-start)<=1000000){
   const n=end-start,m=oldEnd-start,dp=Array.from({length:n+1},()=>new Uint32Array(m+1));
   for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)dp[i][j]=current[start+i]===before[start+j]?1+dp[i+1][j+1]:Math.max(dp[i+1][j],dp[i][j+1]);
   let i=0,j=0;while(i<n){if(j<m&&current[start+i]===before[start+j]){i++;j++}else if(j<m&&dp[i][j+1]>dp[i+1][j])j++;else{changed.push(start+i);i++}}
  }else if(change)for(let i=start;i<end;i++)changed.push(i);
  const h=parseFloat(getComputedStyle(editor).lineHeight);
  editor.style.backgroundImage=changed.map(i=>{const a=i*h-editor.scrollTop,b=a+h;return b>0&&a<editor.clientHeight?`linear-gradient(to bottom,transparent ${Math.max(0,a)}px,rgba(244,114,128,.16) ${Math.max(0,a)}px,rgba(244,114,128,.16) ${Math.max(0,b)}px,transparent ${Math.max(0,b)}px)`:null}).filter(Boolean).join(',')||'none';return;
 }
 if(!highlightedRows||highlightedRows.file!==file){editor.style.backgroundImage='none';return;}
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
 const exists=Object.prototype.hasOwnProperty.call(task.files||{},name);let location=exists&&snippet.trim()?resolveCodeLocation(name,snippet,null):null;let reason='';
 if(requestedLine){const ref=displayedCodeRefs.find(r=>r.file===name&&r.start===Number(requestedLine)&&r.end===Number(requestedEnd||requestedLine));if(ref?.valid&&ref.hash===task.file_hashes?.[name])location={line:ref.start,end:ref.end,kind:'版本核验'};else{location=null;reason=ref?.valid?' · 引用已过期':' · 位置未核验';}}
 const button=document.createElement('button');button.type='button';button.className='code-reference';button.textContent=exists?'↗ '+name+(location?' · 第 '+location.line+(location.end&&location.end!==location.line?'-'+location.end:'')+' 行 · '+location.kind:' · 打开文件'+reason):name+'（尚未生成）';button.disabled=!exists;button.onclick=()=>jumpToCode(name,location?.line,location?.end);el.append(button);
}
function linkedText(el,text){
 const pattern=/([A-Za-z0-9_./-]+\.(?:html|css|js|ts|tsx|jsx|json|py|md))(?:[:：](\d+)(?:[-–](\d+))?|`?\s*第\s*(\d+)(?:\s*[-–至]\s*(\d+))?\s*行)?/g;let from=0,m;
 while((m=pattern.exec(text))){inlineText(el,text.slice(from,m.index));fileReference(el,m[1],'',m[2]||m[4],m[3]||m[5]);from=pattern.lastIndex}inlineText(el,text.slice(from));
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
function messageNode(m,ch){displayedCodeRefs=m.code_refs||[];const div=document.createElement('div');div.className='msg '+m.role;const b=document.createElement('b');b.textContent=m.role==='user'?'你':ch==='coding'?(task.mode==='opencode'?(task.coding_provider?.configured?'Coding · OpenCode':'Coding · OpenCode（待配置）'):'Coding Agent · 示例'):m.engine==='model'?'Teaching Agent':'Teaching Agent · 示例';div.append(b);const content=document.createElement('div');content.className='message-content';if(m.role==='user'){const p=document.createElement('p');p.textContent=m.content;content.append(p)}else if(m.content.startsWith('Teaching Agent 暂时未完成本次分析：')){const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='历史调用未完成（保留原始记录）';details.append(summary,document.createTextNode(m.content));content.append(details)}else formatMessage(content,m.content);div.append(content);if(m.execution_status==='failed_no_changes'){const note=document.createElement('p');note.className='reply-error';note.textContent='本轮没有实际文件改动，阶段未完成。以上为模型原话，不代表已经执行成功。';div.append(note)}if(m.execution_warnings?.length){const warning=document.createElement('details');const title=document.createElement('summary');title.textContent='部分工具调用未成功，实际文件已保存，请验收时检查';warning.append(title,document.createTextNode(m.execution_warnings.map(x=>x.tool+'：'+x.error).join('\n')));div.append(warning)}if(ch==='coding'&&m.phase_report){const report=document.createElement('p');report.className='plan-choice-note';report.textContent='本轮对应计划 '+(m.phase_report.index+1)+'：'+m.phase_report.title+(task.coding_workflow?.checkpoints?.[m.phase_report.index]?.status==='accepted_by_student'?' · 验收通过':' · 已执行，待学生验收');div.append(report)}return div}
function waitingNode(text){const row=document.createElement('div');row.className='waiting';row.setAttribute('role','status');row.textContent='◌ '+text;return row}
function renderChats(){
 for(const ch of ['coding','teaching']){const el=$(ch+'-messages');const nearBottom=el.scrollHeight-el.scrollTop-el.clientHeight<100;el.replaceChildren();const messages=task.messages.filter(m=>m.channel===ch);const lastAssistant=messages.findLastIndex(m=>m.role==='assistant');messages.forEach((m,index)=>{const node=messageNode(m,ch);if(ch==='coding'&&index===lastAssistant&&task.mode==='opencode'){const allPhasesAccepted=task.plan?.length>0&&task.step>=task.plan.length;const choice=!task.plan.length&&task.plan_draft?.length?planChoiceNode():currentPhaseCheckpoint()?phaseChoiceNode():!allPhasesAccepted&&task.capabilities?.coding_reply_accept&&messages.slice(0,index).some(row=>row.role==='user'&&!['queued','needs_retry'].includes(row.queue_status))?replyChoiceNode(m):null;if(choice)node.append(choice);}el.append(node)});
  if(ch==='coding'&&task.coding_run){const run=task.coding_run;if(['queued','running'].includes(run.status))el.append(waitingNode(run.detail||'Coding执行中'));if(run.status==='failed'){const error=document.createElement('p');error.className='reply-error';error.textContent=run.detail||'执行失败，阶段未推进';el.append(error)}}
  if(ch==='teaching'){
   const run=task.teaching_run;
   if(run?.partial_reply&&['queued','running','failed'].includes(run.status)){
    const preview=messageNode({role:'assistant',engine:'model',content:run.partial_reply},'teaching');preview.classList.add('streaming-reply');preview.setAttribute('aria-label',run.status==='failed'?'未完成的教学回复':'正在生成的教学回复');el.append(preview);
   }
   if(run&&['queued','running'].includes(run.status)){const elapsed=Math.max(0,Math.floor(Date.now()/1000-run.started_at));el.append(waitingNode((run.detail||'教师正在处理')+' · '+elapsed+' 秒'));}
   if(run?.status==='failed'){const box=document.createElement('div');box.className='reply-error';const p=document.createElement('p');p.textContent=run.error||run.detail||'回复未完成，消息已保存';const retry=document.createElement('button');retry.textContent='重试回复';retry.onclick=()=>perform(()=>api('/tasks/'+task.id+'/teaching/review',{}));box.append(p,retry);const detail=document.createElement('details');const title=document.createElement('summary');title.textContent='查看错误详情';detail.append(title,document.createTextNode(run.error||''));box.append(detail);el.append(box)}
  }
  if(nearBottom)el.scrollTop=el.scrollHeight;
 }
}

function splitParagraph(text){const sentences=text.match(/[^。！？]+[。！？]?[”’」』]?/g)||[text];const groups=[];let chunk='';for(const sentence of sentences){chunk+=sentence;if(chunk.length>=75){groups.push(chunk);chunk=''}}if(chunk)groups.push(chunk);return groups.join('\n')}

const layoutRoot=document.querySelector('.workspace');
const filePanel=document.querySelector('.files');const fileLabel=filePanel?.querySelector('.label');
if(filePanel&&fileLabel){
 const toggle=document.createElement('button');toggle.type='button';toggle.id='sidebar-toggle';toggle.className='icon-button';
 toggle.innerHTML='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg>';
 document.querySelector('header .brand').prepend(toggle);
 const apply=()=>{const collapsed=localStorage.getItem('control-sidebar-collapsed')==='true';document.body.classList.toggle('sidebar-collapsed',collapsed);toggle.title=collapsed?'恢复工作区':'收起工作区';toggle.setAttribute('aria-label',toggle.title);toggle.setAttribute('aria-expanded',String(!collapsed))};
 toggle.onclick=()=>{localStorage.setItem('control-sidebar-collapsed',String(!document.body.classList.contains('sidebar-collapsed')));apply()};apply();
 const edge=document.createElement('div');edge.id='sidebar-width-split';edge.tabIndex=0;edge.setAttribute('role','separator');edge.setAttribute('aria-label','调整工作区宽度');edge.setAttribute('aria-orientation','vertical');filePanel.append(edge);
 let width=Number(localStorage.getItem('control-sidebar-width'))||220,start=null;
 const paint=()=>{width=Math.max(160,Math.min(480,width));layoutRoot.style.setProperty('--sidebar-width',width+'px');edge.setAttribute('aria-valuenow',String(Math.round(width)))};
 const save=()=>localStorage.setItem('control-sidebar-width',String(width));paint();
 edge.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();edge.setPointerCapture(e.pointerId);start={x:e.clientX,width};document.body.classList.add('resizing')};
 edge.onpointermove=e=>{if(start){width=start.width+e.clientX-start.x;paint()}};
 const stop=()=>{if(!start)return;start=null;document.body.classList.remove('resizing');save()};edge.onpointerup=stop;edge.onpointercancel=stop;edge.onlostpointercapture=stop;
 edge.ondblclick=()=>{width=layoutRoot.clientWidth*.195;paint();save()};
 edge.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();width+=e.key==='ArrowRight'?20:-20;paint();save()}};
}
let layout={teacher:390,codeRatio:54};
try{layout={...layout,...JSON.parse(localStorage.getItem('control-layout')||'{}')}}catch{}
function applyLayout(){layout.teacher=Math.max(300,Math.min(620,Number(layout.teacher)||390));layout.codeRatio=Math.max(30,Math.min(70,Number(layout.codeRatio)||54));layoutRoot.style.setProperty('--teacher',layout.teacher+'px');layoutRoot.style.setProperty('--code-ratio',layout.codeRatio+'fr');layoutRoot.style.setProperty('--chat-ratio',(100-layout.codeRatio)+'fr')}
function persistLayout(){localStorage.setItem('control-layout',JSON.stringify(layout))}
document.querySelectorAll('.splitter').forEach(handle=>{
 handle.ondblclick=()=>{if(handle.dataset.split==='height')layout.codeRatio=54;else layout.teacher=layoutRoot.clientWidth*.243;applyLayout();persistLayout()};
 const adjust=(delta)=>{if(handle.dataset.split==='height')layout.codeRatio+=delta;else layout.teacher-=delta;applyLayout()};
 handle.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();handle.setPointerCapture(e.pointerId);let lastX=e.clientX,lastY=e.clientY;document.body.classList.add('resizing');handle.onpointermove=event=>{if(!handle.hasPointerCapture(event.pointerId))return;if(handle.dataset.split==='height'){const height=document.querySelector('.center').clientHeight;adjust((event.clientY-lastY)/height*100);lastY=event.clientY}else{adjust(event.clientX-lastX);lastX=event.clientX}};const stop=()=>{document.body.classList.remove('resizing');handle.onpointermove=null;persistLayout()};handle.onpointerup=stop;handle.onlostpointercapture=stop;};
 handle.onkeydown=e=>{const height=handle.dataset.split==='height';const minus=height?'ArrowUp':'ArrowLeft',plus=height?'ArrowDown':'ArrowRight';if(e.key===minus||e.key===plus){e.preventDefault();adjust((e.key===plus?1:-1)*(height?3:20));persistLayout()}};
});
$('open-settings').onclick=()=>$('settings-dialog').showModal();window.addEventListener('resize',applyLayout);applyLayout();
function planProgress(){
 const steps=(task.plan?.length?task.plan:task.plan_draft)||[];
 if(task.plan?.length)return steps.map((text,i)=>{const status=task.coding_workflow?.checkpoints?.[i]?.status;return {text,state:status==='accepted_by_student'?'done':status==='executed_pending_review'?'review':i===task.step?'active':'pending'}});
 let todos=[];
 for(const event of task.coding_workflow?.tool_events||[]){const p=event.part||{};if(p.tool==='todowrite'&&Array.isArray(p.state?.input?.todos))todos=p.state.input.todos;}
 return steps.map((text,i)=>{const matches=todos.filter(t=>t.content===text);const status=matches.length===1?matches[0].status:null;
  return {text,state:status==='completed'?'review':status==='in_progress'?'active':status==='cancelled'?'cancelled':status==='pending'?'pending':task.plan.length&&task.plan[i]===text&&i<task.step?'review':'pending'};
 });
}
function renderDevelopmentPlan(){
 const rows=planProgress(),done=rows.filter(x=>x.state==='done').length,reported=rows.filter(x=>x.state==='review').length,allDone=rows.length>0&&done===rows.length;
 $('steps').replaceChildren();
 function row(number,title,status){const li=document.createElement('li');li.className='milestone is-'+status;if(status==='active')li.setAttribute('aria-current','step');const n=document.createElement('strong');n.textContent=number;const body=document.createElement('div');const name=document.createElement('div');name.textContent=title;body.append(name);li.append(n,body);$('steps').append(li);return body;}
 row('1','设置计划',task.plan?.length?'done':'active');
 const body=row('2','开发计划',allDone?'done':task.plan?.length?'active':'pending');
 const list=document.createElement('ol');list.className='phase-progress';
 const labels={done:'验收通过',active:'当前阶段',pending:'未开始',review:'已执行，待验收',cancelled:'已取消'};
 rows.forEach((entry,i)=>{
  const item=document.createElement('li');item.className='phase-row is-'+entry.state;item.setAttribute('aria-label','第'+(i+1)+'项，'+entry.text+'，'+labels[entry.state]);
  if(entry.state==='active'||entry.state==='review')item.setAttribute('aria-current','step');
  const num=document.createElement('b');num.className='phase-number';num.textContent=String(i+1);
  const content=document.createElement('span');content.className='phase-title';content.textContent=entry.text;
  item.append(num,content);list.append(item);
 });
 const draftAwaitingApproval=task.mode==='opencode'&&!task.plan?.length&&!!task.plan_draft?.length;
 const gate=document.createElement('li');gate.className='phase-row plan-review-gate is-'+(draftAwaitingApproval?'active':task.plan.length?'done':'pending');
 const marker=document.createElement('b');marker.className='phase-number';marker.textContent=draftAwaitingApproval?'↻':task.plan.length?'✓':'·';
 const title=document.createElement('span');title.className='phase-title';title.textContent='下一步计划 / 调整';gate.append(marker,title);
 gate.setAttribute('aria-label',draftAwaitingApproval?'计划草稿待调整或确认':task.plan.length?'计划已确认':'等待生成计划');
 if(draftAwaitingApproval){gate.setAttribute('aria-current','step');const controls=planChoiceNode();controls.classList.add('sidebar-plan-choices');gate.append(controls)}
 list.append(gate);body.append(list);
 row('3','总结',allDone?'active':'pending');
 $('progress').textContent=rows.length?done+' / '+rows.length+' 已通过':'待设置';
 $('stage').textContent=['queued','running'].includes(task.coding_run?.status)?'● Coding处理中':allDone?'● 全部阶段已验收通过':rows.length?'● 等待交流与审查':'● 等待需求';
 $('plan-confirm').hidden=true;$('run').hidden=true;
}
$('plan-confirm').onclick=()=>{confirmMode='plan';$('confirm').querySelector('p').textContent='先与教师讨论整体目标和拆分。确认后只保存计划，不执行代码。';$('confirm-run').textContent='确认计划';$('confirm').querySelector('h2').textContent='编辑并确认开发计划（每行一步）';$('instruction').value=(task.plan_draft||[]).join('\n');$('confirm').showModal()};
$('restart-example').onclick=createHomeProject;
const homeButton=document.createElement('button');homeButton.type='button';homeButton.textContent='项目首页';homeButton.onclick=()=>{if(hasCodeChanges())return toast('请先保存代码修改');showProjectHome()};document.querySelector('header .actions').prepend(homeButton);
function renderKnowledge(){
 if(task.mode==='opencode'&&task.teaching_library&&typeof renderTeachingLibrary==='function'){renderTeachingLibrary();return}
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


$('open-learning').onclick=()=>$('learning-dialog').showModal();$('close-learning').onclick=()=>$('learning-dialog').close();
const reviewCard=document.querySelector('.review-card');const reviewTitle=document.querySelector('.review-title');
if(reviewCard&&reviewTitle){reviewCard.classList.add('collapsed');const toggleButton=document.createElement('button');toggleButton.type='button';toggleButton.className='review-toggle';toggleButton.textContent='查看审查';toggleButton.setAttribute('aria-expanded','false');reviewTitle.insertBefore(toggleButton,$('review-teaching'));const toggleReview=()=>{const collapsed=reviewCard.classList.toggle('collapsed');toggleButton.textContent=collapsed?'查看审查':'收起审查';toggleButton.setAttribute('aria-expanded',String(!collapsed))};toggleButton.onclick=toggleReview}




function planChoiceNode(){
 const row=document.createElement('div');row.className='plan-choices';row.setAttribute('aria-label','确认开发计划');
 const requestId=newRequestId(),expectedPlan=[...task.plan_draft],taskId=task.id;
 const waiting=busy||['coding_run'].some(k=>['queued','running'].includes(task[k]?.status));
 const revise=document.createElement('button');revise.type='button';revise.className='plan-choice revise';revise.textContent='↻ 这版还要调整';revise.disabled=waiting;
 revise.onclick=()=>perform(()=>api('/tasks/'+taskId+'/coding/plan-decision',{choice:'revise',request_id:requestId,expected_plan:expectedPlan}));
 const approve=document.createElement('button');approve.type='button';approve.className='plan-choice approve';approve.textContent='✓ 我满意，确认计划并开始第一阶段';approve.disabled=waiting;
 approve.onclick=()=>perform(()=>api('/tasks/'+taskId+'/coding/plan-decision',{choice:'approve',request_id:requestId,expected_plan:expectedPlan}));
 row.append(revise,approve);return row;
}
function replyChoiceNode(message){
 const row=document.createElement('div');row.className='plan-choices';
 const id=task.messages.indexOf(message),taskId=task.id,requestId=newRequestId();
 const accepted=task.coding_reply_acceptances?.some(r=>r.message_id===id),finished=task.plan.length&&task.step>=task.plan.length;
 const button=document.createElement('button');button.type='button';button.className='plan-choice approve';
 button.textContent=finished?'✓ 阶段均已验收':accepted?'✓ 已确认':'✓ 这版可以';
 button.disabled=!!(accepted||finished||busy||['coding_run'].some(k=>['queued','running'].includes(task[k]?.status)));
 button.onclick=()=>perform(()=>api('/tasks/'+taskId+'/coding/reply-accept',{message_id:id,expected_content:message.content,request_id:requestId}));
 row.append(button);return row;
}

function currentPhaseCheckpoint(){
 if(task?.mode!=='opencode'||task.coding_workflow?.checkpoints?.[task.step]?.status!=='executed_pending_review')return null;
 const checkpoint=task.coding_checkpoints?.at(-1);
 return checkpoint?.kind==='development'&&checkpoint.stage_index===task.step?checkpoint:null;
}
function phaseChoiceNode(){
 const checkpoint=currentPhaseCheckpoint();
 const row=document.createElement('div');row.className='plan-choices';row.setAttribute('role','group');row.setAttribute('aria-label','检查当前开发阶段');
 if(!checkpoint)return row;
 const taskId=task.id,requestId=newRequestId(),last=task.step===task.plan.length-1;
 const approve=document.createElement('button');approve.type='button';approve.className='plan-choice approve';approve.textContent=last?'✓ 本阶段通过，完成开发':'✓ 本阶段通过，继续下一阶段';
 approve.disabled=busy||['queued','running'].includes(task.coding_run?.status);
 approve.onclick=()=>perform(async()=>{const result=await api('/tasks/'+taskId+'/checkpoints/'+checkpoint.checkpoint_id+'/resume',{session_id:taskId,request_id:requestId,confirmed:true,teaching_completed:true,expected_code_hash:checkpoint.project_evidence.code_hash});return result.task;});
 row.append(approve);return row;
}


// Floating Coding chat is a presentation-only layer; API and task state stay unchanged.
(() => {
 const panel=document.querySelector('.floating-coding'),stage=document.querySelector('.center'),handle=$('coding-drag-handle');
 document.body.append(panel);
 const key='control-floating-coding-v5';let position=null,minimized=false,following=true,dockX=0,dockY=0,drag=null,saveTimer;
 try{position=JSON.parse(localStorage.getItem(key)||'null');following=position?.following!==false}catch{}
 function defaults(){const box=stage.getBoundingClientRect(),w=Math.max(200,box.width-32),h=Math.min(260,Math.max(160,box.height-116));return {x:16,y:Math.max(16,box.height-h-32),w,h}}
 function constrain(){
  const box=stage.getBoundingClientRect();position=position||defaults();
  position.w=Math.min(Math.max(300,Number(position.w)||520),Math.max(200,box.width-16));
  position.h=Math.min(Math.max(160,Number(position.h)||200),Math.max(120,box.height-24));
  const viewportW=document.documentElement.clientWidth,viewportH=document.documentElement.clientHeight;
  const margin=8,availableW=Math.max(1,viewportW-margin*2),availableH=Math.max(1,viewportH-margin*2);
  position.w=Math.min(position.w,availableW);position.h=Math.min(position.h,availableH);
  const clamp=(value,min,max)=>Math.min(Math.max(Number(value)||0,min),Math.max(min,max));
  position.x=clamp(position.x,margin-box.left,viewportW-margin-box.left-position.w);
  position.y=clamp(position.y,margin-box.top,viewportH-margin-box.top-position.h);
  dockX=clamp(dockX,margin,viewportW-margin-192);
  dockY=clamp(dockY,margin,viewportH-margin-44);
 }
 function paint(){
  if(following&&!minimized)position=defaults();
  constrain();
  if(minimized){
   Object.assign(panel.style,{position:'fixed',left:dockX+'px',top:dockY+'px',width:'192px',height:'44px'});
  }else {const box=stage.getBoundingClientRect();Object.assign(panel.style,{position:'fixed',left:(box.left+position.x)+'px',top:(box.top+position.y)+'px',width:position.w+'px',height:position.h+'px'});}
 }

 function remember(){try{localStorage.setItem(key,JSON.stringify({...position,following}))}catch{}}
 function moved(dx,dy){if(!minimized)following=false;if(minimized){dockX+=dx;dockY+=dy}else{position.x+=dx;position.y+=dy}paint()}
 handle.addEventListener('pointerdown',event=>{
  if(event.button!==0||event.target.closest('button'))return;
  event.preventDefault();handle.setPointerCapture(event.pointerId);drag={x:event.clientX,y:event.clientY};panel.classList.add('is-dragging');
 });
 handle.addEventListener('pointermove',event=>{if(!drag)return;moved(event.clientX-drag.x,event.clientY-drag.y);drag={x:event.clientX,y:event.clientY}});
 function restoreDefaultWindow(){
  clearTimeout(saveTimer);following=true;position=defaults();minimized=false;panel.classList.remove('is-minimized');panel.classList.add('is-animating');
  const button=$('coding-minimize');button.textContent='−';button.setAttribute('aria-expanded','true');button.setAttribute('aria-label','收起Coding聊天');
  paint();remember();setTimeout(()=>panel.classList.remove('is-animating'),300);
 }
 const stop=()=>{if(!drag)return;drag=null;panel.classList.remove('is-dragging');remember()};
 handle.addEventListener('pointerup',stop);handle.addEventListener('pointercancel',stop);handle.addEventListener('lostpointercapture',stop);
 handle.addEventListener('keydown',event=>{
  if(event.target.closest('button'))return;const delta={ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]}[event.key];
  if(delta){event.preventDefault();moved(...delta);remember()}
 });
 const resetButton=document.createElement('button');resetButton.type='button';resetButton.id='coding-reset';resetButton.title='恢复默认位置和大小';resetButton.setAttribute('aria-label',resetButton.title);
 resetButton.innerHTML='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 10a9 9 0 1 1 2.5 8M3 4v6h6"/></svg>';
 resetButton.onclick=restoreDefaultWindow;handle.insertBefore(resetButton,$('coding-minimize'));
 $('coding-minimize').onclick=()=>{clearTimeout(saveTimer);minimized=!minimized;if(minimized){const rect=panel.getBoundingClientRect();dockX=rect.left;dockY=rect.bottom-44;}panel.classList.add('is-animating');setTimeout(()=>panel.classList.remove('is-animating'),300);panel.classList.toggle('is-minimized',minimized);$('coding-minimize').textContent=minimized?'+':'−';$('coding-minimize').setAttribute('aria-expanded',String(!minimized));$('coding-minimize').setAttribute('aria-label',minimized?'展开Coding聊天':'收起Coding聊天');paint()};
 $('reset-coding-window').onclick=()=>{following=true;position=defaults();minimized=false;panel.classList.remove('is-minimized');$('coding-minimize').textContent='−';$('coding-minimize').setAttribute('aria-expanded','true');$('coding-minimize').setAttribute('aria-label','收起Coding聊天');paint();remember()};
 handle.addEventListener('dblclick',event=>{if(!event.target.closest('button'))restoreDefaultWindow()});
 const edgeNames={n:'上边',s:'下边',e:'右边',w:'左边',nw:'左上角',ne:'右上角',sw:'左下角',se:'右下角'};
 for(const [edge,label] of Object.entries(edgeNames)){
  const grip=document.createElement('div');grip.className='coding-resize-grip grip-'+edge;grip.tabIndex=0;grip.setAttribute('role','separator');grip.setAttribute('aria-label','调整聊天窗'+label+'尺寸');
  let start=null;
  const resize=(dx,dy)=>{
   const area=stage.getBoundingClientRect(),minW=Math.min(300,area.width-16),minH=160;
   let {x,y,w,h}=start;
   if(edge.includes('e'))w=Math.max(minW,Math.min(start.w+dx,area.width-start.x-8));
   if(edge.includes('w')){w=Math.max(minW,Math.min(start.w-dx,start.x+start.w-8));x=start.x+start.w-w}
   if(edge.includes('s'))h=Math.max(minH,Math.min(start.h+dy,area.height-start.y-8));
   if(edge.includes('n')){h=Math.max(minH,Math.min(start.h-dy,start.y+start.h-8));y=start.y+start.h-h}
   position={x,y,w,h};paint();
  };
  grip.onpointerdown=event=>{if(event.button!==0||minimized)return;event.preventDefault();event.stopPropagation();following=false;grip.setPointerCapture(event.pointerId);start={...position,px:event.clientX,py:event.clientY};panel.classList.add('is-sizing')};
  grip.onpointermove=event=>{if(start){event.preventDefault();resize(event.clientX-start.px,event.clientY-start.py)}};
  const stopResize=()=>{start=null;panel.classList.remove('is-sizing');remember()};grip.onpointerup=stopResize;grip.onpointercancel=stopResize;grip.onlostpointercapture=stopResize;
  grip.onkeydown=event=>{const delta={ArrowLeft:[-12,0],ArrowRight:[12,0],ArrowUp:[0,-12],ArrowDown:[0,12]}[event.key];if(delta&&!minimized){event.preventDefault();following=false;start={...position};resize(...delta);stopResize()}};
  panel.append(grip);
 }
 new ResizeObserver(()=>{if(drag||minimized||panel.classList.contains('is-sizing')||panel.classList.contains('is-animating'))return;clearTimeout(saveTimer);saveTimer=setTimeout(()=>{const rect=panel.getBoundingClientRect();position.w=rect.width;position.h=rect.height;paint();remember()},120)}).observe(panel);
 new ResizeObserver(()=>paint()).observe(stage);
 window.addEventListener('resize',paint);
 paint();
})();


// File/plan divider: local layout only, never changes development progress.
(() => {
 const sidebar=document.querySelector('.files'),divider=$('sidebar-plan-split');let ratio=38,start=null;
 try{ratio=Number(localStorage.getItem('control-sidebar-file-ratio'))||38}catch{}
 function paint(){ratio=Math.max(15,Math.min(75,ratio));sidebar.style.setProperty('--file-share',ratio+'fr');sidebar.style.setProperty('--plan-share',(100-ratio)+'fr');divider.setAttribute('aria-valuemin','15');divider.setAttribute('aria-valuemax','75');divider.setAttribute('aria-valuenow',String(Math.round(ratio)))}
 function save(){try{localStorage.setItem('control-sidebar-file-ratio',String(ratio))}catch{}}
 divider.onpointerdown=event=>{if(event.button!==0)return;event.preventDefault();divider.setPointerCapture(event.pointerId);start={y:event.clientY,ratio};document.body.classList.add('resizing')};
 divider.onpointermove=event=>{if(!start)return;const height=sidebar.clientHeight-sidebar.querySelector('.label').offsetHeight-6;ratio=start.ratio+(event.clientY-start.y)/Math.max(1,height)*100;paint()};
 const stop=()=>{start=null;document.body.classList.remove('resizing');save()};divider.onpointerup=stop;divider.onpointercancel=stop;divider.onlostpointercapture=stop;
 divider.ondblclick=()=>{ratio=22;paint();save()};
 divider.onkeydown=event=>{if(event.key==='ArrowUp'||event.key==='ArrowDown'){event.preventDefault();ratio+=event.key==='ArrowDown'?3:-3;paint();save()}};
 paint();
})();

// Reveal native scroll thumbs only during scrolling; keep their gutters transparent.
(() => {
 const timers=new WeakMap();let held=null;
 function reveal(element){
  if(!(element instanceof Element))return;
  element.classList.add('is-scrolling');clearTimeout(timers.get(element));
  timers.set(element,setTimeout(()=>{if(element!==held)element.classList.remove('is-scrolling')},850));
 }
 document.addEventListener('scroll',event=>reveal(event.target),true);
 document.addEventListener('pointerdown',event=>{
  const element=event.target;if(!(element instanceof HTMLElement))return;
  const box=element.getBoundingClientRect(),style=getComputedStyle(element);
  const vertical=element.scrollHeight>element.clientHeight&&/auto|scroll/.test(style.overflowY)&&event.clientX>=box.right-10;
  const horizontal=element.scrollWidth>element.clientWidth&&/auto|scroll/.test(style.overflowX)&&event.clientY>=box.bottom-10;
  if(vertical||horizontal){held=element;element.classList.add('is-scroll-dragging');reveal(element)}
 },true);
 const release=()=>{if(!held)return;const element=held;held=null;element.classList.remove('is-scroll-dragging');reveal(element)};
 window.addEventListener('pointerup',release,true);window.addEventListener('pointercancel',release,true);window.addEventListener('blur',release);
})();
