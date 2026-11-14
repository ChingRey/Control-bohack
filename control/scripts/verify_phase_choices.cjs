const fs=require('fs'),assert=require('assert'),crypto=require('crypto');
const source=fs.readFileSync(require('path').join(__dirname,'../frontend/app.js'),'utf8');
const code=source.slice(source.indexOf('function currentPhaseCheckpoint(){'));
const task={id:'task',mode:'opencode',step:0,plan:['界面','交互'],coding_workflow:{checkpoints:[{status:'executed_pending_review'}]},coding_checkpoints:[{kind:'development',stage_index:0,checkpoint_id:'cp',project_evidence:{code_hash:'hash'}}]};
const element=()=>({children:[],setAttribute(){},append(...xs){this.children.push(...xs)}});
const input={focus(){this.focused=true}};let request,toast;
const api=async(path,body)=>{request={path,body};return {task:{id:'updated'}}};
const {currentPhaseCheckpoint,phaseChoiceNode}=new Function('task','busy','crypto','document','api','perform','$','toast',code+';return {currentPhaseCheckpoint,phaseChoiceNode};')(task,false,crypto,{createElement:element},api,fn=>fn(),()=>input,x=>toast=x);
(async()=>{
 assert.equal(currentPhaseCheckpoint().checkpoint_id,'cp');
 const row=phaseChoiceNode();assert.match(row.children[0].textContent,/继续下一阶段/);
 row.children[1].onclick();assert(input.focused);assert(!request,'Reject must not resume or launch a model');
 const result=await row.children[0].onclick();assert.equal(result.id,'updated');assert.equal(request.path,'/tasks/task/checkpoints/cp/resume');assert.equal(request.body.expected_code_hash,'hash');assert(request.body.confirmed);
 const id=request.body.request_id;await row.children[0].onclick();assert.equal(request.body.request_id,id,'Double click reuses idempotency key');
 task.plan=['界面'];assert.match(phaseChoiceNode().children[0].textContent,/完成开发/);
 task.coding_workflow.checkpoints[0].status='accepted_by_student';assert.equal(currentPhaseCheckpoint(),null);
 task.coding_workflow.checkpoints[0].status='executed_pending_review';task.coding_checkpoints[0].stage_index=1;assert.equal(currentPhaseCheckpoint(),null);
 console.log('PASS: stage choices, reject pauses, versioned resume, stable request ID, final stage, stale button hidden');
})().catch(e=>{console.error(e);process.exitCode=1});
