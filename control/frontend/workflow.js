// Workflow controls reuse the current task and mutation/polling helpers.
const workflowNames={requirements:'需求与验收单',design:'功能设计单',experiences:'项目经验（最多15条有效规则）',coverage:'教学覆盖记录',learner:'学习观察（待核实）'};
const workflowStages=['定义作品','看懂原型','逐项开发与验证','独立扩展','交付'];
workflowStages.forEach((name,index)=>$('workflow-stage').add(new Option(name,index)));
Object.entries(workflowNames).forEach(([key,name])=>$('workflow-kind').add(new Option(name,key)));
function showMaterial(){const rows=task.workflow?.materials?.[$('workflow-kind').value]||[];const last=rows.at(-1);$('workflow-history').replaceChildren();for(const row of [...rows].reverse())$('workflow-history').add(new Option('v'+row.revision+' · '+row.status,row.revision));$('workflow-content').value=last?.content||'';$('workflow-material-status').textContent=last?`版本 ${last.revision} · ${last.status==='confirmed'?'学生已确认':'草稿'} · 历史 ${rows.length} 版`:'尚未整理，不推断学生能力'}
$('project-materials').onclick=()=>{if(!task)return;$('workflow-stage').value=task.workflow?.stage||0;showMaterial();$('workflow-dialog').showModal()};
$('workflow-kind').onchange=showMaterial;
async function saveMaterial(confirmed){const ok=await perform(()=>api('/tasks/'+task.id+'/workflow/material',{kind:$('workflow-kind').value,content:$('workflow-content').value,expected_revision:task.workflow.revision,confirmed}));if(ok)showMaterial()}
$('workflow-draft').onclick=()=>saveMaterial(false);$('workflow-confirm').onclick=()=>saveMaterial(true);
$('workflow-stage-save').onclick=()=>perform(()=>api('/tasks/'+task.id+'/workflow/stage',{stage:Number($('workflow-stage').value),expected_revision:task.workflow.revision}));
function listVersions(){$('versions-list').replaceChildren();for(const version of [...(task.version_history||[])].reverse()){const row=document.createElement('p'),button=document.createElement('button');row.append(document.createTextNode(version.label+' · '+version.created_at+' '));button.textContent='恢复这个版本';button.onclick=async()=>{if(!confirm('恢复项目文件？当前代码会自动保存为版本，聊天和学习记录保留。'))return;const current=await api('/tasks/'+task.id+'/versions/current',{});const ok=await perform(()=>api('/tasks/'+task.id+'/versions/restore',{version_id:version.id,expected_hash:current.hash}));if(ok)listVersions()};row.append(button);$('versions-list').append(row)}}

$('version-save').onclick=async()=>{if(await perform(()=>api('/tasks/'+task.id+'/versions/save',{label:'手动保存 '+new Date().toLocaleString()})))listVersions()};
$('project-diff').onclick=()=>{diffHighlightEnabled=!diffHighlightEnabled;showView('code');paintRowHighlight()};

let behaviorHash=null;
$('behavior-open').onclick=async()=>{try{behaviorHash=(await api('/tasks/'+task.id+'/versions/current',{})).hash;$('behavior-history').textContent=(task.behavior_records||[]).slice(-10).map(r=>`${r.result}: ${r.operation} → ${r.actual}（源码 ${r.hash.slice(0,8)}）`).join('\n');$('behavior-dialog').showModal()}catch(e){toast(e.message)}};
$('behavior-save').onclick=async()=>{const ok=await perform(()=>api('/tasks/'+task.id+'/behavior/record',{expected_hash:behaviorHash,operation:$('behavior-operation').value,expected:$('behavior-expected').value,actual:$('behavior-actual').value,result:$('behavior-result').value}));if(ok)$('behavior-dialog').close()};

$('workflow-prototype').onclick=async()=>{const ok=await perform(()=>api('/tasks/'+task.id+'/coding/prototype',{expected_revision:task.workflow.revision}));if(ok)$('workflow-dialog').close()};

const flowHints=['明确使用者、核心操作与验收，再确认需求生成原型。','沿真实页面走一遍事件与状态；把条件、数据、存储决定写入设计。','每次一个功能：看改动，测正常与边界，修复后审核经验。','独立描述扩展，核对接口密钥、超时与错误处理。','说明如何运行、测过什么、已知限制，保存最终版本与交接包。'];
const flowSafe=async fn=>{try{return await fn()}catch(e){toast(e.message)}};
function flowButton(label,fn){const b=document.createElement('button');b.textContent=label;b.type='button';b.onclick=()=>flowSafe(fn);return b}
function renderFlowReview(){const s=task.workflow;$('flow-features').replaceChildren();for(const feature of s.features||[]){const p=document.createElement('p');p.append(document.createTextNode((feature.id===s.current_feature_id?'当前 · ':'')+feature.title+' · '+feature.status+' '));p.append(flowButton('选为当前功能',()=>perform(()=>api('/tasks/'+task.id+'/workflow/feature',{action:'select',feature_id:feature.id,expected_revision:task.workflow.revision}))));$('flow-features').append(p)}$('flow-proposals').replaceChildren();for(const row of s.proposals||[]){if(row.status!=='pending_review')continue;const card=document.createElement('section'),title=document.createElement('b'),text=document.createElement('textarea'),evidence=document.createElement('p');title.textContent=workflowNames[row.kind]||row.title||row.concept||row.kind;text.value=row.content;const prior=task.workflow.materials[row.kind]?.at(-1);if(prior){const current=document.createElement('p');current.textContent='当前材料 v'+prior.revision+'：'+prior.content.slice(0,700);card.append(current)}if(row.base_revision!==task.workflow.revision){const outdated=document.createElement('p');outdated.textContent='此建议生成后项目材料已更新，请对照当前内容再决定是否采用。';card.append(outdated)}evidence.textContent='来源：'+row.quotes.map(q=>`#${q.message_id} ${q.quote}`).join('；');card.append(title,text,evidence);let merge=null;if(row.kind==='rule'){merge=document.createElement('select');merge.add(new Option('作为新规则',''));for(const rule of s.rules||[])merge.add(new Option('修订：'+rule.title,rule.id));merge.value=row.replaces_id||'';card.append(merge);if(row.similar_rules?.length){const note=document.createElement('p');note.textContent='发现近似规则，请核对是否修订；近似不证明语义相同。';card.append(note)}}for(const [decision,label] of [['accept','核对并确认'],['reject','不采用']])card.append(flowButton(label,async()=>{const ok=await perform(()=>api('/tasks/'+task.id+'/workflow/proposals/review',{proposal_id:row.id,decision,content:text.value,expected_revision:task.workflow.revision,...(merge?{replaces_id:merge.value||null}:{})}));if(ok)renderFlowReview()}));$('flow-proposals').append(card)}
 $('flow-rules').replaceChildren();for(const rule of s.rules||[]){const p=document.createElement('p');p.append(document.createTextNode(`${rule.title}（v${rule.revision} · ${rule.status}） ${rule.content}；适用：${rule.when}；边界：${rule.limits} `));p.append(flowButton(rule.status==='active'?'停用':'启用',()=>perform(()=>api('/tasks/'+task.id+'/workflow/rules/status',{rule_id:rule.id,status:rule.status==='active'?'inactive':'active',expected_revision:task.workflow.revision}))));$('flow-rules').append(p)}
 const levels={unknown:'尚无证据',explained:'已讲解',practiced:'已练习（待核实）',independent_candidate:'独立表现建议（待核实）'};$('flow-concepts').textContent=Object.entries(s.concepts||{}).map(([n,r])=>`${n}：${levels[r.status]||r.status}`).join('；');$('flow-organize-status').textContent=task.organizer_run?.detail||'';
}
window.renderWorkflow=()=>{
 const s=task.workflow;
 if(!s)return;
 renderTeachingReferences();
 renderLessonSelection();
 $('flow-adopt').disabled=!task.teaching?.turns?.length;
 if(task.mode==='opencode'){
  const feature=s.features?.find(r=>r.id===s.current_feature_id);
  $('course-overview').textContent='项目阶段：'+workflowStages[s.stage]+' · 当前功能：'+(feature?.title||'尚未选定');
 }
 const queued=task.messages.filter(m=>m.queue_status==='queued').length;
 $('flow-status').textContent=workflowStages[s.stage]+(queued?' · 排队 '+queued+' 条':'');
 $('flow-next').textContent=s.mode==='free'?'自由开发，可按需记录材料和验证结果。':flowHints[s.stage]||'';
 if($('flow-review-dialog').open&&!$('flow-proposals').contains(document.activeElement))renderFlowReview();
 if($('flow-delivery-dialog').open)renderFlowDelivery();
};
$('flow-review').onclick=()=>{$('flow-mode').value=task.workflow.mode;$('flow-auto').checked=task.workflow.auto_organize;renderFlowReview();$('flow-review-dialog').showModal()};
$('flow-organize').onclick=()=>perform(()=>api('/tasks/'+task.id+'/workflow/organize',{}));
$('flow-options').onclick=()=>perform(()=>api('/tasks/'+task.id+'/workflow/options',{mode:$('flow-mode').value,auto_organize:$('flow-auto').checked}));
$('flow-adopt').onclick=()=>{
 const reply=task.messages.findLast(m=>m.channel==='teaching'&&m.role==='assistant');
 if(!reply)return;
 if(document.querySelector('.floating-coding.is-minimized'))$('coding-minimize').click();
 $('coding-input').value='请结合以下建议，我会先检查和调整范围：'+reply.content;
 $('coding-input').focus();
 toast('教学建议已填入 Coding 输入框');
};
async function listStudents(){const list=await api('/students');$('flow-student-select').replaceChildren();for(const s of list)$('flow-student-select').add(new Option(s.name,s.id));if(task.workflow.student_id)$('flow-student-select').value=task.workflow.student_id}
$('flow-student').onclick=()=>flowSafe(async()=>{await listStudents();$('flow-promote-rules').replaceChildren();for(const r of task.workflow.rules||[]){if(r.status!=='active')continue;const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.value=r.id;label.append(check,document.createTextNode(r.title));$('flow-promote-rules').append(label)}$('flow-student-dialog').showModal()});
$('flow-student-create').onclick=()=>flowSafe(async()=>{const p=await api('/students',{name:$('flow-student-name').value});await listStudents();$('flow-student-select').value=p.id});
$('flow-student-attach').onclick=()=>perform(()=>api('/tasks/'+task.id+'/student/attach',{student_id:$('flow-student-select').value,confirmed:true}));
$('flow-promote').onclick=()=>perform(async()=>{const r=await api('/tasks/'+task.id+'/student/promote',{confirmed:true,rule_ids:[...$('flow-promote-rules').querySelectorAll('input:checked')].map(e=>e.value),include_profile:$('flow-profile').checked});return r.task});
const browserActions={fill:'填写输入',click:'点击',assert_text:'检查文本包含',assert_count:'检查元素数量',assert_exists:'检查元素存在',assert_absent:'检查元素不存在',assert_value:'检查输入值',reload:'刷新页面',wait:'等待（毫秒）'};
function addBrowserStep(){const row=document.createElement('div'),a=document.createElement('select'),s=document.createElement('input'),v=document.createElement('input');for(const [key,label] of Object.entries(browserActions))a.add(new Option(label,key));s.placeholder='CSS选择器，例如 #add';v.placeholder='填写值 / 预期文本 / 数量';row.className='flow-browser-step';row.append(a,s,v,flowButton('移除',()=>row.remove()));$('flow-browser-steps').append(row)}
$('flow-browser-add').onclick=addBrowserStep;
function browserCases(){return [...$('flow-browser-steps').children].map(row=>{const [a,s,v]=row.querySelectorAll('select,input');return {action:a.value,selector:s.value,...(a.value==='assert_count'?{count:Number(v.value)}:a.value==='wait'?{ms:Number(v.value)}:a.value==='assert_text'?{text:v.value}:{value:v.value})}})}
function renderFlowDelivery(){$('flow-runtime-status').textContent=JSON.stringify(task.runtime_process,null,2);$('flow-runtime-link').hidden=task.runtime_process?.status!=='running';if(task.runtime_process?.url)$('flow-runtime-link').href=task.runtime_process.url;$('flow-safety').textContent=task.safety_report?.findings.map(r=>`${r.path}${r.line?':'+r.line:''}：${r.message}`).join('\n')||'未发现已登记静态信号，不等于安全测试通过。';$('flow-verification').textContent=[task.verification_run?.detail||'',...(task.browser_records||[]).slice(-2).map(r=>JSON.stringify(r,null,2)),...(task.execution_records||[]).slice(-2).map(r=>JSON.stringify(r,null,2))].join('\n');const d=$('flow-delivery-download');d.hidden=!task.delivery_report;d.href='/api/tasks/'+task.id+'/delivery.zip';d.download='project-handoff.zip'}
$('flow-delivery').onclick=()=>{if(!$('flow-browser-steps').children.length)addBrowserStep();renderFlowDelivery();$('flow-how-run').value=task.delivery_statement?.how_to_run||'';$('flow-tested').value=task.delivery_statement?.tested||'';$('flow-limits').value=task.delivery_statement?.limitations||'';$('flow-delivery-dialog').showModal()};
$('flow-browser-run').onclick=()=>perform(()=>api('/tasks/'+task.id+'/project/browser',{expected_hash:task.project_hash,cases:browserCases()}));
$('flow-test-run').onclick=()=>perform(()=>api('/tasks/'+task.id+'/project/test',{expected_hash:task.project_hash,recipe:$('flow-test-recipe').value}));
$('flow-delivery-prepare').onclick=()=>perform(()=>api('/tasks/'+task.id+'/delivery/prepare',{expected_hash:task.project_hash,student_statement:{how_to_run:$('flow-how-run').value,tested:$('flow-tested').value,limitations:$('flow-limits').value}}));

$('flow-runtime-start').onclick=()=>perform(()=>api('/tasks/'+task.id+'/project/runtime/start',{expected_hash:task.project_hash,kind:$('flow-runtime-kind').value,entry:$('flow-runtime-entry').value}));
$('flow-runtime-stop').onclick=()=>perform(()=>api('/tasks/'+task.id+'/project/runtime/stop',{}));

$('flow-feature-create').onclick=()=>perform(()=>api('/tasks/'+task.id+'/workflow/feature',{action:'create',title:$('flow-feature-title').value,expected_revision:task.workflow.revision}));
$('flow-feature-accept').onclick=()=>perform(()=>api('/tasks/'+task.id+'/workflow/feature',{action:'accept',feature_id:task.workflow.current_feature_id,explanation:$('flow-feature-explanation').value,expected_revision:task.workflow.revision}));

$('workflow-history').onchange=()=>{const row=task.workflow.materials[$('workflow-kind').value].find(r=>String(r.revision)===$('workflow-history').value);if(row){$('workflow-content').value=row.content;$('workflow-material-status').textContent='正在查看历史 v'+row.revision+'；保存或确认将创建新版本'}};


function renderLessonSelection(){
 const library=task.teaching_library;
 const ids=library?.suggested_lesson_ids||[];
 const titles=ids.map(id=>library.topics.find(card=>card.id===id)?.title).filter(Boolean);
 $('lesson-selection').textContent=titles.length?'建议学习：'+titles.join('、'):'你可以直接提问，或选择一张课卡。';
}

function requestLesson(id){
 return perform(()=>api('/tasks/'+task.id+'/teaching/resources',{lesson_id:id,choice:'learn'}));
}

function renderTeachingLibrary(){
 const library=task.teaching_library,host=$('knowledge-topics');
 const previous=$('teaching-library-choice');
 const selected=host.dataset.projectId===task.id?previous?.value:null;
 const restoreFocus=document.activeElement===previous;
 const prefs=library.preferences||{},ids=library.suggested_lesson_ids||[];
 host.dataset.projectId=task.id;
 host.replaceChildren();

 const note=document.createElement('p');
 note.textContent=ids.length?'建议学习 '+ids.map(id=>library.topics.find(card=>card.id===id)?.title).filter(Boolean).join('、'):'可以选择一个与当前项目有关的主题。';
 host.append(note);

 const label=document.createElement('label');
 label.htmlFor='teaching-library-choice';
 label.textContent='课卡主题';
 const select=document.createElement('select');
 select.id='teaching-library-choice';
 for(const card of library.topics){
  const deferred=prefs.deferred_lesson_ids?.includes(card.id);
  select.add(new Option(card.title+(deferred?' · 稍后':''),card.id));
 }
 const wanted=selected||prefs.focus_lesson_id||ids[0];
 if(library.topics.some(card=>card.id===wanted))select.value=wanted;
 host.append(label,select);

 const actions=document.createElement('div');
 actions.className='teaching-actions';
 actions.append(
  flowButton('预览所选课卡',()=>showLessonCard(select.value)),
  flowButton('请学习助手讲解',()=>{$('lesson-topics-dialog').close();return requestLesson(select.value)}),
  flowButton('稍后再学',()=>perform(()=>api('/tasks/'+task.id+'/teaching/resources',{lesson_id:select.value,choice:'later'}))),
  flowButton('恢复自动推荐',()=>perform(()=>api('/tasks/'+task.id+'/teaching/resources',{choice:'auto'})))
 );
 actions.children[1].id='teaching-library-learn';
 actions.children[2].id='teaching-library-later';
 actions.children[3].id='teaching-library-auto';
 for(const button of Array.from(actions.children).slice(1))button.disabled=busy;
 host.append(actions);
 if(restoreFocus)select.focus();
}
function renderTeachingReferences(){
 const host=$('teaching-reference-list');if(!host||!task)return;host.replaceChildren();const library=task.teaching_library,trace=library?.last_turn;
 if(!trace){host.textContent='完成一轮教学后，这里会显示该轮参考的课卡和来源。';return}
 const title=document.createElement('p');title.textContent=(trace.submitted_to_model?'最近一轮已提供给模型：':'最近一轮为示例，未提交模型：')+(trace.lesson_ids?.map(id=>trace.lessons?.find(c=>c.id===id)?.title||library.topics.find(c=>c.id===id)?.title||id).join('、')||'通用教学指导');host.append(title);
 for(const id of [...new Set([...(trace.source_ids||[]),...(trace.policy_source_ids||[])])]){const source=[...(trace.sources||[]),...(trace.policy_sources||[]),...library.sources].find(s=>s.id===id);if(!source||!source.url.startsWith('https://'))continue;const p=document.createElement('p'),a=document.createElement('a');a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=source.title;p.append(a);host.append(p)}
 const status=document.createElement('small');status.textContent='资料版本 '+trace.revision+'；提供资料不代表模型实际采用或学生掌握。';host.append(status);
}

if(task)render();

async function showLessonCard(id){
 try{
 const data=await api('/teaching/library/'+encodeURIComponent(id)),card=data.lesson;
 let dialog=$('lesson-card-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='lesson-card-dialog';dialog.className='learning-dialog';document.body.append(dialog)}
 dialog.replaceChildren();const title=document.createElement('h2');title.textContent=card.title;dialog.append(title);
 const note=document.createElement('p');note.textContent='教学课卡 · '+data.revision+' · 查看不代表已学习或掌握';dialog.append(note);
 for(const [key,label] of [['concept_explanation','概念讲解'],['illustrative_example','例子'],['suggested_checks','检查要点'],['student_activity','可以尝试的练习'],['transfer_prompt','换个场景想一想']]){
  const section=document.createElement('section'),h=document.createElement('h3'),body=document.createElement('div');h.textContent=label;body.style.whiteSpace='pre-wrap';body.textContent=Array.isArray(card[key])?card[key].join('\n'):card[key]||'';section.append(h,body);dialog.append(section);
 }
const learn=document.createElement('button');
 learn.type='button';
 learn.textContent='请学习助手讲解';
 learn.onclick=()=>{
  dialog.close();
  $('lesson-topics-dialog').close();
  return requestLesson(id);
 };
 const close=document.createElement('button');close.textContent='关闭';close.onclick=()=>dialog.close();dialog.append(learn,close);dialog.showModal();
 }catch(e){toast(e.message)}
}
$('open-lesson-cards').onclick=()=>{
 if(task)$('lesson-topics-dialog').showModal();
};
$('close-lesson-topics').onclick=()=>$('lesson-topics-dialog').close();
