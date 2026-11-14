/* Independent Mock integration console, separate from ordinary teaching chat. */
async function v021Request(operation,body){
 const path='/api/tasks/'+task.id+'/teaching-v021'+(operation?'/'+operation:'');
 const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 const value=await response.json();if(!response.ok)throw Error(value.error||'V0.2.1请求失败');return value;
}
async function v021Refresh(){
 const value=await v021Request('');
 const current=value.active_strategy;
 $('v021-status').textContent='模式：'+value.mode+'（联调不认证能力、不解锁Skill）\n'+(value.configured?'已配置隔离Mock课程':'尚未配置')+'\n当前策略：'+(current?current.id+' v'+current.version:'未分配')+'\n已执行动作：'+(value.turns?.length||0)+'；评价记录：'+(value.evaluations?.length||0);
 const failed=Object.entries(value.requests||{}).filter(([id,r])=>r.status==='failed');
 $('v021-retries').replaceChildren();
 for(const [id,row] of failed){const button=document.createElement('button');button.textContent='重试 '+row.operation+' · '+id;button.onclick=()=>v021Action(row.operation,{...row.body,retry:true});$('v021-retries').append(button)}
}
async function v021Action(operation,extra={}){
 const buttons=[...$('v021-dialog').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
 try{
  const result=await v021Request(operation,{request_id:crypto.randomUUID(),...extra});
  if(result.operation)$('v021-result').textContent='恢复请求：'+result.operation.status;
  else $('v021-result').textContent=operation==='teach'?result.response.action.content:operation==='evaluate'?result.response.reason:operation==='evolve'?'已保存候选策略和待执行实验；未发布。':'操作已保存';
  task=await api('/tasks/'+task.id);render();await v021Refresh();pollChat();
 }catch(e){$('v021-result').textContent=e.message;try{await v021Refresh()}catch{}}
 finally{buttons.forEach(b=>b.disabled=false)}
}
$('open-v021').onclick=()=>{$('v021-dialog').showModal();v021Refresh().catch(e=>{$('v021-status').textContent=e.message})};
$('v021-login').onclick=async()=>{
 const field=$('v021-token'),token=field.value;field.value='';
 try{const response=await fetch('/api/teaching-v021/session',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({task_id:task.id})});const value=await response.json();if(!response.ok)throw Error(value.error);await v021Refresh()}catch(e){$('v021-result').textContent=e.message}
};
for(const operation of ['configure','decide','teach','evolve'])$('v021-'+operation).onclick=()=>v021Action(operation);
$('v021-respond').onclick=async()=>{const input=$('v021-message');if(!input.value.trim())return;await v021Action('respond',{message:input.value});input.value=''};
$('v021-formative').onclick=()=>v021Action('evaluate',{assessment_mode:'formative'});
$('v021-transfer').onclick=()=>v021Action('evaluate',{assessment_mode:'independent_transfer'});
$('v021-resume').onclick=()=>{if(confirm('确认教学检查点结束，并允许Coding继续下一阶段？Mock评价不会解锁Skill。'))v021Action('resume',{confirmed:true,teaching_completed:true})};
