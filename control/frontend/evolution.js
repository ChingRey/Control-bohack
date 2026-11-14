// Shared single-user experience library. Render all model material as plain text.
(() => {
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
 const dialog=el('dialog',undefined,'experience-library');dialog.id='experience-dialog';document.body.append(dialog);
 let book=null,pending=false,lastKey='',highlight=true;
 const expanded=new Set();
 const labels={active:'初始教法',trial:'待验证',candidate:'候选',inactive:'已停用'};
 const fields=[['when','适用场景'],['action','教学策略'],['verify','预期效果'],['limits','适用边界']];
 const btn=(text,fn,cls)=>{const b=el('button',text,cls);b.type='button';b.onclick=fn;return b};
 const details=(text)=>{const d=el('details');d.append(el('summary',text));return d};
 const stamp=n=>n?new Date(n*1000).toLocaleString('zh-CN'):'';
 const note=el('p','', 'library-notice');note.setAttribute('role','status');
 async function refresh(force=false){
  try{
   const next=await api('/experience-library'),key=JSON.stringify([next.revision,next.project_names,next.project_runs,next.trial_observations,next.uses?.length,task?.id]);book=next;
   if(force||key!==lastKey){lastKey=key;draw()}
  }catch(e){note.textContent=e.message}
 }
 async function change(body){
  if(pending)return;pending=true;note.textContent='';
  try{book=await api('/experience-library',{expected_revision:book.revision,...body});lastKey='';await refresh(true);if(task){const id=task.id;const next=await api('/tasks/'+id);if(task?.id===id){task=next;render()}}}
  catch(e){note.textContent=e.message;await refresh()}
  finally{pending=false}
 }
 function textFields(host,entry){
  if(!entry){host.append(el('p','尚无此条经验'));return}
  host.append(el('h4',entry.title));
  for(const [key,label] of fields)host.append(el('p',label+'：'+entry[key]));
  host.append(el('small',(labels[entry.status]||entry.status)+' · r'+entry.revision));
 }
 function evidence(host,batch){
  const review=batch.review;if(!review)return;
  const scores=details('评分与证据 · '+review.rubric_version);
  scores.append(el('p','每维分数 = 100 × 有证据条目分之和 ÷ 有证据条目数。0 / 0.5 / 1 对照固定条目；缺证据记空，不算总分。模型观察不等于因果效果。'));
  for(const score of review.scores||[]){
   const row=el('section',undefined,'library-score');row.append(el('h4',score.name+' · '+(score.score===null?'证据不足':score.score+'分')));
   const obs=review.evaluation.observations.find(x=>x.dimension===score.id);
   if(obs)row.append(el('p',obs.reason));
   for(const item of obs?.items||[]){
    const criteria=review.rubric_snapshot.dimensions.find(x=>x.id===score.id)?.items?.find(x=>x.id===item.id);
    row.append(el('p',(criteria?.name||item.id)+'：'+(item.value===null?'证据不足':item.value)+'；'+item.reason));
    if(criteria)row.append(el('small','评分锚点：'+criteria.anchors));
    row.append(el('small','证据：'+(item.evidence_ids||[]).join('、')));
    for(const q of item.quotes||[])row.append(el('blockquote','消息 '+q.message_id+'：'+q.quote));
   }
   if(!obs?.items)for(const q of obs?.quotes||[])row.append(el('blockquote','消息 '+q.message_id+'：'+q.quote));
   scores.append(row);
  }
  const sources=details('本轮采集的证据快照（聊天／改动／验证）');
  for(const item of batch.evidence||[])sources.append(el('pre',JSON.stringify(item,null,2)));
  scores.append(sources);host.append(scores);
 }
 function significant(changeItem){
  const before=changeItem.before,after=changeItem.after;
  return !before||!after||['title','when','action','verify','limits','status','tags'].some(k=>JSON.stringify(before[k])!==JSON.stringify(after[k]));
 }
 function entryMeta(entry){
  const batches=book.batches.filter(b=>b.changes.some(c=>c.entry_id===entry.id&&significant(c)));
  const created=batches.find(b=>b.changes.some(c=>c.entry_id===entry.id&&!c.before));
  const latest=batches.at(-1);
  // Initial seeds predate the first import. Unknown historical origins are not invented.
  const initial=['seed','preset'].includes(entry.origin)||(entry.history||[]).some(e=>['seed','preset'].includes(e.origin));
  const projectName=(id,fallback)=>book.project_names?.[id]||fallback||'历史仓库';
  const source=batch=>batch.kind==='preset_import'?'系统预设':batch.project_id?projectName(batch.project_id,batch.project_title):'经验库管理';
  const added=created?source(created):initial?'系统预设':entry.source_project?projectName(entry.source_project,entry.source_title):'历史导入';
  const changed=latest&&latest!==created?source(latest):null;
  const lastChange=latest?.changes.find(c=>c.entry_id===entry.id);
  const verb=lastChange?.after?.status==='inactive'?'停用':'修改';
  return {batches,updated:latest?.after_revision??0,added,changed,verb,source};
 }
 function entriesView(main){
  const rows=el('div',undefined,'library-matrix');
  const latest=[...book.batches].reverse().find(b=>b.changes.some(significant));
  const currentIds=new Set((latest?.changes||[]).filter(significant).map(c=>c.entry_id));
  const entries=book.entries.map((entry,index)=>({entry,index,meta:entryMeta(entry)}))
   .sort((a,b)=>b.meta.updated-a.meta.updated||b.index-a.index);
  if(!entries.length)rows.append(el('p','尚无经验。'));
  for(const {entry,meta} of entries){
   const card=details('');card.className='library-entry';card.dataset.entryId=entry.id;
   card.dataset.version=meta.updated;card.classList.toggle('is-current-change',highlight&&currentIds.has(entry.id));
   card.open=expanded.has(entry.id);card.ontoggle=()=>{if(card.open)expanded.add(entry.id);else expanded.delete(entry.id)};
   const summary=card.firstChild;summary.replaceChildren(el('strong',entry.title),el('small',
    meta.added+' · 加入'+(meta.changed?'\n'+meta.changed+' · '+meta.verb:'')));
   const content=el('div',undefined,'library-entry-content');textFields(content,entry);
   content.append(el('p','加入来源：'+meta.added));
   if(meta.changed)content.append(el('p','最近'+meta.verb+'：'+meta.changed));
   if(entry.rationale)content.append(el('p','适用分析：'+entry.rationale));
   if(entry.example)content.append(el('blockquote','教学示例（设计，不是学生实录）：'+entry.example));
   if(entry.source_refs?.length){const sources=details('预设来源与版本');for(const source of entry.source_refs)sources.append(el('p',source.path+' · '+source.section),el('small','源码SHA256：'+source.sha256));content.append(sources)}
   if(entry.evidence_plan?.length){const observations=details('下次怎样验证');for(const plan of entry.evidence_plan)observations.append(el('p',plan.observe),el('small','对应条目 '+plan.dimension+'/'+plan.item_id+'；证据：'+plan.evidence_sources.join('、')));content.append(observations)}
   const validation=book.trial_observations?.[entry.id];if(validation)content.append(el('p','已提供 '+validation.provided_count+' 轮；后续观察：'+entry.verify));
   const audit=details('变更、评分与回退');
   for(const batch of [...meta.batches].reverse()){
    const item=batch.changes.find(c=>c.entry_id===entry.id);const section=el('section',undefined,'library-change');
    section.append(el('h4',meta.source(batch)+' · '+(!item.before?'加入':item.after?.status==='inactive'?'停用':'修改')+(item.undone?' · 已撤销':'')));
    const diff=el('div',undefined,'library-diff'),before=el('div'),after=el('div');
    before.append(el('strong','修改前'));after.append(el('strong','修改后'));textFields(before,item.before);textFields(after,item.after);diff.append(before,after);section.append(diff);
    if(item.after?.reason)section.append(el('p','修改依据：'+item.after.reason));
    evidence(section,batch);
    if(!item.undone&&['reflection','preset_import'].includes(batch.kind))section.append(btn('撤销此项',()=>change({action:'undo',batch_id:batch.id,entry_id:entry.id}),'library-undo-entry'));
    audit.append(section);
   }
   if(!meta.batches.length)audit.append(el('p','初始经验，尚无变更记录。'));content.append(audit);
   if(entry.history?.length){const history=details('条目历史版本');for(const version of [...entry.history].reverse()){const section=el('section');textFields(section,version);history.append(section)}content.append(history)}
   if(entry.stop_reason)content.append(el('p','停用依据：'+entry.stop_reason));
   const uses=details('教学引用与后续反馈');
   const matches=(book.uses||[]).filter(r=>r.entries.some(e=>e.id===entry.id));
   if(!matches.length)uses.append(el('p','尚无教学加载记录。'));
   for(const use of matches.slice(-8)){
    uses.append(el('h4',(use.project_title||use.project_id)+' · 消息 '+use.reply_message_id),el('p','提交版本 r'+use.entries.find(e=>e.id===entry.id).revision+'；加载不等于实际采用'),el('blockquote',use.reply));
    for(const batch of book.batches.filter(b=>b.project_id===use.project_id))for(const feedback of batch.review?.evaluation.feedback||[])if(feedback.entry_id===entry.id&&feedback.reply_message_id===use.reply_message_id){
     uses.append(el('p',({helpful:'有帮助的观察',harmful:'负面观察',uncertain:'不能归因'})[feedback.outcome]+'：'+feedback.reason));
     for(const q of feedback.quotes)uses.append(el('blockquote','消息 '+q.message_id+'：'+q.quote));
    }
   }
   content.append(uses,btn(['inactive','candidate'].includes(entry.status)?'试用这条经验':'停用',()=>change({action:'status',entry_id:entry.id,status:['inactive','candidate'].includes(entry.status)?'trial':'inactive'})));
   card.append(content);rows.append(card);
  }
  main.append(rows);
 }
 function draw(){
  const scroll=dialog.scrollTop;dialog.replaceChildren();
  const header=el('div',undefined,'library-header');
  const toggle=btn('本轮经验变更',()=>{highlight=!highlight;draw()},'library-highlight-toggle');
  toggle.setAttribute('aria-pressed',String(highlight));
  const close=btn('×',()=>dialog.close(),'library-close');close.setAttribute('aria-label','关闭经验库');
  header.append(el('h2','经验库'),toggle,close);dialog.append(header,note);
  const main=el('main');entriesView(main);dialog.append(main);dialog.scrollTop=scroll;
 }
 async function open(){if(!dialog.open){highlight=true;expanded.clear()}await refresh(true);if(!dialog.open)dialog.showModal()}
 document.getElementById('evolution-open').onclick=open;
 const settings=document.getElementById('settings-dialog');const settingsButton=btn('打开经验库',()=>{settings.close();open()});settingsButton.id='experience-open';settings.append(settingsButton);
 window.renderTeachingEvolution=()=>{if(dialog.open)refresh()};
 setInterval(()=>{if(dialog.open)refresh()},1800);
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
 document.getElementById('open-settings').addEventListener('click',loadLimits);
})();
