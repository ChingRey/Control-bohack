(() => {
  const $ = id => document.getElementById(id);
  const status=$('ev-sim-status'), progress=$('ev-sim-progress'), start=$('ev-sim-start');
  const users=$('ev-sim-users'), returns=$('ev-sim-returns'), scenario=$('ev-sim-scenario');
  const stages={setup:'建立试验',pre:'独立前测',practice:'引导练习',post:'独立后测',transfer:'独立迁移'};
  const phase={starting:'准备模拟数据',between_trials:'正在安排下一轮',checking:'正在核对记录并生成报告'};
  const strategyState={baseline:'基线',testing:'候选试用',validated:'已验证'};
  let timer, board=null, runId=null, starting=false, loading=false;
  const path='/api/teaching/strategy-simulation';
  const benchmark=()=>$('evolution-benchmark').value;
  async function call(method,body) {
    const options=body?{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{};
    const reply=await fetch(path,options);
    const data=await reply.json();
    if(!reply.ok) throw new Error(data.error||'服务暂不可用');
    return data;
  }
  function lock(disabled) {
    for(const control of [start,users,returns,scenario]) control.disabled=disabled;
  }
  function paint(run, notify=true) {
    const running=run.state==='running', failed=run.state==='failed';
    const hasRun=running||failed||run.state==='completed';
    const otherCase=hasRun && run.benchmark_version!==benchmark();
    lock(running||starting);
    progress.hidden=!hasRun;
    progress.max=run.target||1;
    progress.value=run.completed||0;

    if(hasRun) {
      const source=otherCase?' · '+(run.benchmark_version.startsWith('linked')?'单链表删除':'待办输入边界'):'';
      const active=run.active;
      const step=active
        ? '第 '+active.index+' 轮 · 学生 '+active.student+(active.repeat_visit?'回访':'')+' · '+(stages[active.stage]||active.stage)
        : phase[run.phase]||'正在运行';
      const count=run.completed+' / '+run.target+' 轮 · '+run.users+' 位首次参与者 + '+run.return_visits+' 次回访';
      status.textContent=running?'正在模拟'+source+' · '+count+' · '+step
        : failed?'模拟未完成'+source+' · '+count+'。'+run.error
        :'模拟已完成'+source+' · '+count;
    } else {
      status.textContent='设置人数和回访轮数，再开始自动模拟。';
    }

    const recent=$('ev-sim-recent');
    recent.replaceChildren();
    for(const [offset,row] of (run.recent||[]).entries()) {
      const item=document.createElement('div');
      item.textContent='第 '+(run.completed-offset)+' 轮 · 学生 '+row.student+
        (row.repeat_visit?'回访':'')+' · v'+row.strategy_version+' '+
        (strategyState[row.strategy_status_during_teaching]||row.strategy_status_during_teaching)+
        (row.post_score==null?' · 后测证据不足':' · 后测 '+row.post_score+' 分');
      recent.append(item);
    }
    $('ev-sim-run-log').hidden=!recent.childElementCount;
    if(run.board && run.id!==runId) {
      runId=run.id;
      board=run.board;
      if(notify) window.dispatchEvent(new Event('control:simulation-ready'));
    } else if(run.board) {
      board=run.board;
    }
    clearTimeout(timer);
    if(running) timer=setTimeout(()=>update(),500);
    return board;
  }
  async function update(notify=true) {
    if(loading||starting) return board;
    loading=true;
    try { return paint(await call('GET'),notify); }
    catch(error) {
      status.textContent='无法读取模拟进度：'+error.message+'。将自动重试。';
      timer=setTimeout(()=>update(),1800);
      return board;
    } finally { loading=false; }
  }

  users.oninput=()=>{returns.max=users.value;};
  start.onclick=async()=>{
    returns.max=users.value;
    if(!users.reportValidity()||!returns.reportValidity()) return;
    if(starting) return;
    starting=true;
    clearTimeout(timer);
    lock(true);
    status.textContent='正在启动后台模拟…';
    try {
      const run=await call('POST',{scenario:scenario.value,users:users.valueAsNumber,
        return_visits:returns.valueAsNumber,benchmark_version:benchmark()});
      starting=false;
      paint(run);
    } catch(error) {
      status.textContent='启动失败：'+error.message;
      lock(false);
    } finally { starting=false; }
  };
  $('ev-sim-refresh').onclick=async()=>{
    await update(false);
    window.dispatchEvent(new Event('control:simulation-ready'));
  };
  window.strategySimulation={update,board:version=>board?.benchmark_version===version?board:null};
})();
