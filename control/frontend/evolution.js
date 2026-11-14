// Project-local experience controls. Model text is always rendered as text, never HTML.
(() => {
 const host=document.createElement('details');host.id='teaching-evolution';
 const heading=document.createElement('summary');heading.textContent='教学反思与经验库';
 const status=document.createElement('p'),open=document.createElement('button');open.textContent='查看与管理';open.id='experience-open';
 host.append(heading,status,open);document.querySelector('.teaching-overview')?.append(host);
 const dialog=document.createElement('dialog');dialog.id='experience-dialog';dialog.className='learning-dialog';document.body.append(dialog);
 const limitSettings=document.createElement('details');limitSettings.id='model-timeouts';
 limitSettings.append(document.createElement('summary'));limitSettings.firstChild.textContent='模型超时（秒）';
 const limitFields={teacher_request_seconds:'Teacher单次请求',teacher_total_seconds:'Teacher整轮回复',background_request_seconds:'后台单次请求',background_total_seconds:'后台整批评价与反思'};
 const limitInputs={};
 for(const [key,title] of Object.entries(limitFields)){const label=document.createElement('label');label.textContent=title;const input=document.createElement('input');input.type='number';input.min='5';input.max=key.includes('request')?'300':'900';input.step='1';input.id='timeout-'+key;label.append(input);limitInputs[key]=input;limitSettings.append(label)}
 const limitSave=document.createElement('button');limitSave.type='button';limitSave.id='save-model-timeouts';limitSave.textContent='保存超时';
 const limitNote=document.createElement('p');limitNote.textContent='下一次请求生效；超时保留消息，不无限重试。后台总时限包含评价和反思。';
 const loadLimits=async()=>{try{const health=await api('/health');for(const [key,input] of Object.entries(limitInputs))input.value=health.model_timeouts?.[key]??''}catch(e){limitNote.textContent=e.message}};
 limitSave.onclick=async()=>{try{const value=Object.fromEntries(Object.entries(limitInputs).map(([key,input])=>[key,Number(input.value)]));await api('/settings/timeouts',value);limitNote.textContent='已保存，下次任务生效；当前请求不强制中断。'}catch(e){limitNote.textContent=e.message}};
 limitSettings.append(limitNote,limitSave);document.getElementById('settings-dialog').append(limitSettings);
 document.getElementById('settings').addEventListener('click',loadLimits);
 const labels={active:'已启用（不等于验证有效）',trial:'局部试用',candidate:'候选',inactive:'已停用'};
 const el=(tag,value)=>{const node=document.createElement(tag);if(value!==undefined)node.textContent=value;return node};
 const button=(label,fn)=>{const b=el('button',label);b.type='button';if(label==='分析新交互')b.id='experience-review';if(label==='保存模式')b.id='experience-options';if(label==='恢复所选版本')b.id='experience-restore';b.onclick=fn;return b};
 async function change(body){if(await perform(()=>api('/tasks/'+task.id+'/teaching/experience-manage',{expected_revision:task.teaching_evolution.revision,...body})))draw()}
 function draw(){
  const s=task?.teaching_evolution;if(!s)return;
  dialog.replaceChildren(el('h2','教学反思与经验库'),el('p',`项目内经验 · v${s.revision} · 原话和评分均可回查；加载不代表采用或效果已验证。`));
  const mode=el('select');mode.id='experience-mode';mode.setAttribute('aria-label','经验工作模式');
  for(const [value,title] of [['adaptive','参考初始教法并局部试用候选'],['observe','仅参考已启用教法，新反思不自动试用'],['off','关闭经验注入与反思']])mode.add(new Option(title,value));mode.value=s.mode;
  const autoLabel=el('label',' 自动后台反思（评价、反思各调用一次，失败可能重试） '),auto=el('input');auto.id='experience-auto';auto.type='checkbox';auto.checked=s.auto;autoLabel.className='experience-auto-option';autoLabel.prepend(auto);
  dialog.append(mode,autoLabel,button('保存模式',()=>change({action:'options',mode:mode.value,auto:auto.checked})),
   button('分析新交互',async()=>{await perform(()=>api('/tasks/'+task.id+'/teaching/experience-review',{}));draw()}),el('p',s.run.detail||'尚无反思记录'));
  dialog.append(el('h3','六维评价（固定量表v1，未经教学实验校准）'),el('p','每项：未达到0、部分达到0.5、达到1；维度分=100×有效条目均值。缺证据不计分，不合成总分。')); 
  if(s.run.error)dialog.append(el('p',`${s.run.error_code||'后台错误'}：${s.run.error}`));
  if(s.run.new_message_ids)dialog.append(el('p',`本批新消息：${s.run.new_message_ids.join('、')}；待送达后补分析：${s.run.deferred_ids?.join('、')||'无'}`));
  if(s.run.request_trace?.length){const traces=el('details');traces.append(el('summary','后台请求耗时'));for(const r of s.run.request_trace)traces.append(el('p',`${r.phase} · 请求${r.attempt} · ${r.status} · ${r.elapsed_seconds??'进行中'}秒${r.http_status?' · HTTP '+r.http_status:''}`));dialog.append(traces)}
  if(s.run.status!=='completed'&&s.run.evaluation){const partial=el('details');partial.append(el('summary','已完成的评价（本批尚未入经验库）'));const body=el('pre',JSON.stringify({scores:s.run.scores,evaluation:s.run.evaluation},null,2));body.style.whiteSpace='pre-wrap';partial.append(body);dialog.append(partial)}
  const latest=s.reviews.at(-1);
  if(latest){
   dialog.append(el('p',`来源消息 ${latest.from_id}—${latest.through_id} · ${latest.rubric_version} · 模型观察，不是掌握认证`));
   for(const score of latest.scores)dialog.append(el('p',`${score.name}：${score.score===null?'证据不足':score.score+'分'} · 有效观察 ${score.count} · 消息 ${score.evidence_ids.join('、')||'无'}`));
   dialog.append(el('h3','最近反思'),el('p',latest.reflection.summary));
   const evidence=el('details');evidence.append(el('summary','展开评分依据与经验反馈'));
   const pre=el('pre',JSON.stringify(latest.evaluation,null,2));pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';evidence.append(pre);dialog.append(evidence);
  }else dialog.append(el('p','还没有评价；连接Teaching模型并积累交互后分析。'));
  dialog.append(el('h3','经验条目'));
  for(const entry of s.entries){
   const row=el('details');row.dataset.entryId=entry.id;row.append(el('summary',`${entry.title} · ${labels[entry.status]} · r${entry.revision}`));
   for(const [key,label] of [['when','适用'],['action','动作'],['verify','验证目标'],['limits','边界'],['source','来源']])row.append(el('p',`${label}：${entry[key]}`));
   row.append(el('p',`模型支持 ${entry.helpful}／反对 ${entry.harmful}／不确定 ${entry.uncertain}；不代表因果有效。来源消息 ${(entry.evidence_ids||[]).join('、')||'初始教法'}`));
   if(entry.quotes)for(const q of entry.quotes)row.append(el('p',`消息 ${q.message_id}：“${q.quote}”`));
   row.append(button(entry.status==='inactive'?'恢复试用':'停用',()=>change({action:'status',entry_id:entry.id,status:entry.status==='inactive'?'trial':'inactive'})));
   if(entry.status!=='active')row.append(button('设为启用（人工选择）',()=>change({action:'status',entry_id:entry.id,status:'active'})));
   dialog.append(row);
  }
  if(s.versions.length){
   const versions=el('select');versions.id='experience-versions';versions.setAttribute('aria-label','恢复经验版本');
   for(const v of [...s.versions].reverse())versions.add(new Option(`v${v.revision} · ${v.reason}`,String(v.revision)));
   dialog.append(el('h3','回退经验库'),versions,button('恢复所选版本',()=>change({action:'restore',target_revision:Number(versions.value)})),el('p','恢复后关闭自动反思并切到观察模式；原话、评价记录和源码不回退。'));
  }
  dialog.append(button('关闭',()=>dialog.close()));
 }
 window.renderTeachingEvolution=()=>{const s=task?.teaching_evolution;status.textContent=s?`v${s.revision} · ${s.entries.filter(e=>e.status!=='inactive').length}条可用／候选 · ${s.reviews.length}批评价 · ${s.run.detail||'尚未反思'}`:'请先打开项目';if(dialog.open)draw()};
 open.onclick=()=>{if(!task)return;draw();dialog.showModal()};
 window.renderTeachingEvolution();
})();
