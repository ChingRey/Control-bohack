(() => {
  const $ = id => document.getElementById(id);
  const dialog = $('evolution-dialog'), scoreboard = $('evolution-board'), trialNode = $('evolution-trial');
  const initialSource = new URLSearchParams(location.search).get('evolution');
  let cohort = initialSource==='simulation'?'simulation':'human', session = null, trialPath = null, pending = false, requestId = 0, boardRequestId = 0;
  let selectedVersion=null;
  $('evolution-cohort').value=cohort;
  const labels = {pre:'独立前测',practice:'引导练习',post:'独立后测',transfer:'独立迁移',complete:'试验完成'};
  const dimensions = {knowledge:'知识理解',judgment:'工程判断',ai_collaboration:'AI 协作指导',verification:'验证与纠错',transfer:'独立迁移'};
  const fmt = (x) => x == null ? '证据不足' : String(x);
  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text != null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }
  async function request(path, body) {
    const res = await fetch(path, body == null ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await res.json();
    if (!res.ok) throw Error(data.error || '读取失败');
    return data;
  }
  function report(error) { $('evolution-status').textContent = error?.message || ''; }
  function guard(action) {
    return async () => {
      if (pending) return;
      pending = true;
      dialog.setAttribute('aria-busy','true');
      report();
      try { await action(); } catch(error) { report(error); }
      finally { pending = false; dialog.removeAttribute('aria-busy'); }
    };
  }
  function details(title) {
    const d = node('details');
    d.append(node('summary',title));
    return d;
  }
  function progressBar(label, value) {
    const row = node('div',null,'ev-measure');
    row.append(node('span',label),node('strong',fmt(value)));
    if(value != null) {
      const bar = node('progress');
      bar.max = 100; bar.value = value; bar.setAttribute('aria-label',label);
      row.append(bar);
    }
    return row;
  }
  function showView(view) {
    const boardActive=view==='board';
    $('evolution-board-panel').hidden=!boardActive;
    $('evolution-trial-panel').hidden=boardActive;
    $('evolution-show-board').setAttribute('aria-pressed',boardActive);
    $('evolution-show-trial').setAttribute('aria-pressed',!boardActive);
    dialog.scrollTop=0;
  }
  function renderBoard(data) {
    window.renderStrategyEvolution(scoreboard,data,selectedVersion,version=>{
      selectedVersion=version;
      renderBoard(data);
      scoreboard.querySelector('.ev-version-picker select')?.focus();
    });
  }
  async function refresh() {
    const revision = ++boardRequestId, current = cohort;
    const data = await request('/api/teaching/strategy-trials'+(current==='simulation'?'/simulation':''));
    if(revision===boardRequestId) renderBoard(data);
  }
  function renderTrial() {
    trialNode.replaceChildren();
    const independent = ['pre','post','transfer'].includes(session?.stage);
    scoreboard.hidden = independent;
    $('ev-board-hidden').hidden = !independent;
    if(!session?.id) {
      trialNode.append(node('p','选择当前工作台的教学示例，完成前测、练习和两次独立检验。'));
      return;
    }
    trialNode.append(node('div',labels[session.stage], 'ev-trial-title'));
    if (session.cohort==='simulation') trialNode.append(node('p','模拟实验 · 记录不会进入真人策略库','ev-note'));
    if(session.stage==='complete') {
      const result = session.result;
      trialNode.append(node('p',result.mastered?'达到本任务的掌握门槛':'尚未达到本任务的掌握门槛'),
                       progressBar('前测四维独立分',session.pre.core_score),
                       progressBar('后测四维独立分',result.core_score),progressBar('含迁移的五维总分',result.total_score));
      for(const [key,mark] of Object.entries(result.scores)) {
        trialNode.append(node('p',dimensions[key]+'：'+fmt(mark.level)+' / 4 · '+mark.anchor));
      }
      const evidence = details('查看行为检查与评分证据');
      for(const stage of ['pre','practice','post','transfer']) {
        for(const row of session.evidence[stage]||[]) {
          evidence.append(node('p',labels[stage]+' · '+row.id,'ev-id'));
          for(const check of row.checks) evidence.append(node('p',JSON.stringify(check.input)+'：预期 '+JSON.stringify(check.expected)+'；实际 '+JSON.stringify(check.actual)));
        }
      }
      const showResults=node('button','查看策略进化');
      showResults.onclick=()=>showView('board');
      trialNode.append(showResults,evidence);return;
    }
    if(session.stage==='practice') {
      trialNode.append(node('p',session.decision.learning_goal+' · '+session.decision.reason));
      const first=session.events[0];
      if(first) trialNode.append(node('p','v'+first.strategy_version+' · '+first.strategy_reason,'ev-note'));
      const latestChecks = session.practice_checks?.at(-1) || [];
      if(latestChecks.length) {
        const checks = details('查看刚才运行的规则与实际结果');
        for(const check of latestChecks) checks.append(node('p',JSON.stringify(check.input)+'：预期 '+JSON.stringify(check.expected)+'；实际 '+JSON.stringify(check.actual)));
        trialNode.append(checks);
      }
      for (const e of session.events) trialNode.append(node('p',e.stage+' · H'+e.hint_level+'　'+e.prompt,'ev-instruction'));
    } else {
      trialNode.append(node('p','独立完成：提交前不会显示答案、教学提示或运行结果。','ev-note'));
    }
    const form = node('form',null,'ev-form'), shape = session.form;
    form.append(node('p','情境：'+shape.subject+'，正常输入示例「'+shape.normal_input+'」。'));
    const controls = [];
    function pick(label, options) {
      const wrapper = node('label',label);
      const select = node('select');select.append(new Option('请选择',''));
      const offset = label.startsWith('提交') ? 0 : (shape.stage==='pre'?0:shape.stage==='practice'?1:shape.stage==='post'?2:3);
      options.forEach((_,i)=>{const pos=(i+offset)%options.length;select.append(new Option(options[pos],String(pos)));});
      wrapper.append(select);form.append(wrapper);controls.push(select);return select;
    }
    const answers = shape.questions.map(q=>[q.id,pick(q.label,q.options)]);
    const predictions = shape.cases.map(c=>pick('提交'+c+'时，是否应新增记录？',['不新增','新增']));
    if(session.stage==='pre') controls.slice(0,-1).forEach(x=>x.required=true);
    const btn = node('button',session.stage==='practice'?'提交练习':'提交'+labels[session.stage],'primary');form.append(btn);
    form.onsubmit = event => {
      event.preventDefault();
      guard(async()=>{
        btn.disabled = true;
        try {
          session = await request(trialPath+'/submit',{stage:session.stage,revision:session.revision,
            answers:Object.fromEntries(answers.filter(([,x])=>x.value!=='').map(([k,x])=>[k,Number(x.value)])),
            predictions:predictions.map(x=>x.value===''?null:x.value==='1')});
          renderTrial(); await refresh();
        } finally { btn.disabled = false; }
        if(initialSource==='simulation') $('evolution-open').click();
})();
    };
    trialNode.append(form);
  }
  async function restore() {
    const revision = ++requestId;
    const active = localStorage.getItem('control-workbench-task');
    trialPath = active?'/api/tasks/'+encodeURIComponent(active)+'/teaching/experiment':null;
    const value = trialPath ? await request(trialPath) : null;
    if(revision===requestId){session=value;renderTrial();}
  }
  $('evolution-open').onclick = guard(async()=>{
    dialog.showModal();
    await restore();
    if(session?.id && session.stage!=='complete') showView('trial');
    await Promise.all([refresh(),renderProfiles(),showSimulationControl()]);
  });
  $('evolution-show-board').onclick=()=>showView('board');
  $('evolution-show-trial').onclick=()=>showView('trial');
  $('evolution-close').onclick = ()=>{if(!pending) dialog.close();};
  dialog.addEventListener('cancel', event=>{if(pending) event.preventDefault();});
  $('evolution-cohort').onchange = event => {cohort=event.target.value;selectedVersion=null;refresh().catch(report);};

  async function renderProfiles() {
    const roster = await request('/api/students');
    const active = localStorage.getItem('control-strategy-trial-student');
    const select = $('evolution-profile-select');
    select.replaceChildren(new Option('选择参与者',''));
    roster.forEach(student=>select.append(new Option(student.name,student.id)));
    select.value=active || '';
  }
  $('evolution-profile-select').onchange = event => {
    localStorage.setItem('control-strategy-trial-student',event.target.value);
  };
  async function showSimulationControl() {
    const health=await request('/api/health');
    $('evolution-simulate').hidden=!health.manual_simulation_enabled;
  }
  async function startTrial(source) {
    if(!window.canSwitchControlProject()) throw Error('请先保存修改，或等当前操作完成。');
    const profile=$('evolution-profile-select').value;
    if(!profile) throw Error('请先选择本机学生，或新建学生档案。');
    const task = await request('/api/tasks',{scenario:'strategy-trial'});
    trialPath='/api/tasks/'+encodeURIComponent(task.id)+'/teaching/experiment';
    session=await request(trialPath,{profile_id:profile,arm:$('evolution-arm').value,cohort:source});
    window.dispatchEvent(new CustomEvent('control:open-teaching-example',{detail:task}));
    cohort=source;
    selectedVersion=null;
    showView('trial');
    $('evolution-cohort').value=cohort;
    renderTrial();
    await refresh();
  }
  $('evolution-new').onclick=guard(()=>startTrial('human'));
  $('evolution-simulate').onclick=guard(()=>startTrial('simulation'));
  $('evolution-profile').onclick = guard(async()=>{
    const input=$('evolution-profile-name');
    const name=input.value.trim();
    if(!name) { input.focus(); throw Error('请输入本机学生的名称或代号。'); }
    const record = await request('/api/students',{name});
    input.value='';
    localStorage.setItem('control-strategy-trial-student',record.id);
    await renderProfiles();
    $('evolution-status').textContent='已创建并选中本机学生档案。';
  });
  if(initialSource==='simulation') $('evolution-open').click();
})();
