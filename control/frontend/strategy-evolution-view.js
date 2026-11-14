(() => {
  const labels = {
    baseline:'基线', candidate:'等待试用', testing:'收集中', validated:'已通过试点门槛',
    rejected:'未通过', retired:'已被替换'
  };
  const dimensions = {
    knowledge:'知识理解', judgment:'工程判断', ai_collaboration:'AI 协作指导',
    verification:'验证与纠错', transfer:'独立迁移'
  };
  const caseName = ['普通文本','空字符串','纯空格','制表符与换行','两端有空白的正常文本'];
  const versionName = version => 'v'+version;
  const format = value => new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2}).format(value);
  const mean = values => values.reduce((sum,value)=>sum+value,0)/values.length;
  const sign = value => (value>0?'+':'')+format(value);
  const readout = value => value==null?'证据不足':format(value);

  function node(tag, content, className) {
    const el=document.createElement(tag);
    if(content!=null) el.textContent=content;
    if(className) el.className=className;
    return el;
  }
  function details(title) {
    const el=node('details',null,'ev-disclosure');
    el.append(node('summary',title));
    return el;
  }
  function dataRow(title, value) {
    const dl=node('dl',null,'ev-data-row');
    dl.append(node('dt',title),node('dd',value));
    return dl;
  }
  function step(list, heading) {
    const item=node('li');
    item.append(node('h4',heading));
    list.append(item);
    return item;
  }
  function stats(values) {
    const row=node('div',null,'ev-stats');
    for(const [title,value] of values) {
      const metric=node('div');
      metric.append(node('strong',value),node('span',title));
      row.append(metric);
    }
    return row;
  }
  function comparisons(version, parent) {
    const parentResults=new Map((parent?.results||[]).map(row=>[row.trial_id,row]));
    const candidateResults=new Map(version.results.map(row=>[row.trial_id,row]));
    return (version.history.findLast(row=>row.pairs)?.pairs||[]).flatMap(pair=>{
      const before=parentResults.get(pair.baseline_trial_id);
      const after=candidateResults.get(pair.candidate_trial_id);
      return before && after ? [{before,after,delta:pair}] : [];
    });
  }

  function diagnosis(source, version) {
    if(!source) return version.observation;
    const weak=source.weaknesses.map(key=>dimensions[key]||key);
    const failed=source.observed?.post?.failed_cases.map(i=>caseName[i]).filter(Boolean)||[];
    const evidence=[];
    if(failed.length) evidence.push('独立后测没通过这些用例：'+failed.join('、'));
    if(!failed.length&&weak.length) evidence.push('独立后测薄弱项：'+weak.join('、'));
    if(source.transfer_passed===false) evidence.push('迁移 '+source.transfer_level+'/4，未通过');
    return evidence.length?evidence.join('。')+'。':version.observation;
  }
  function validationTable(rows, version, parent) {
    const before=rows.map(pair=>pair.before);
    const after=rows.map(pair=>pair.after);
    const count=rows.length;
    const average = (results,key) => format(mean(results.map(row=>row[key])));
    const fraction = (results,key) => results.filter(row=>row[key]).length+'/'+count;
    const summary=[
      ['平均前测 → 后测',
       average(before,'pre_score')+' → '+average(before,'post_score'),
       average(after,'pre_score')+' → '+average(after,'post_score')],
      ['平均学习增益',sign(mean(before.map(r=>r.gain)))+' 分',sign(mean(after.map(r=>r.gain)))+' 分'],
      ['独立迁移通过',fraction(before,'transfer_passed'),fraction(after,'transfer_passed')]
    ];
    const table=node('table',null,'ev-results-table');
    const head=table.createTHead().insertRow();
    for(const heading of ['只比较验证使用的配对',versionName(parent.version)+' 基线',versionName(version.version)+' 试用']) {
      const cell=node('th',heading);
      cell.scope='col';
      head.append(cell);
    }
    const body=table.createTBody();
    for(const [label,baseline,candidate] of summary) {
      const row=body.insertRow();
      const cell=node('th',label);
      cell.scope='row';
      row.append(cell,node('td',baseline),node('td',candidate));
    }
    return table;
  }
  function comparisonDetails(rows, version) {
    const detail=details('查看 '+rows.length+' 组对照及验证规则');
    const plan=version.validation_plan;
    detail.append(node('p','同一测评、难度和起点范围。至少 '+plan.min_pairs+
      ' 组配对，每组前测差不超过 '+plan.max_pre_gap+' 分。平均增益须至少多 '+plan.min_gain_delta+
      ' 分，后测和迁移等级须改善，迁移通过、行为检查和提示负担不得变差。提示负担按提示级别 × 次数计算。','ev-note'));
    const passCount = side => rows.filter(row=>row[side].test_passed).length;
    const hints = side => format(mean(rows.map(row=>row[side].hint_burden)));
    detail.append(dataRow('行为检查通过',passCount('before')+'/'+rows.length+' → '+passCount('after')+'/'+rows.length),
      dataRow('平均提示负担',hints('before')+' → '+hints('after')));
    for(const [index,{before,after,delta}] of rows.entries()) {
      const evidence=details('第 '+(index+1)+' 组 · 增益差 '+sign(delta.gain_delta)+' 分');
      for(const [label,result] of [['基线',before],['候选试用',after]]) {
        evidence.append(dataRow(label,readout(result.pre_score)+' → '+readout(result.post_score)+
          '，迁移 '+readout(result.transfer_level)+'/4，提示负担 '+result.hint_burden),
          node('p','试验 '+result.trial_id+' · 评价 '+result.evaluation_id,'ev-id'));
      }
      detail.append(evidence);
    }
    return detail;
  }
  function rejectionReasons(rows, plan) {
    const fail=[];
    const change = key => mean(rows.map(row=>row.delta[key]));
    if(change('gain_delta')<plan.min_gain_delta) fail.push('增益差未达门槛');
    if(change('post_delta')<=0) fail.push('后测均分未提高');
    if(change('transfer_level_delta')<=0) fail.push('迁移等级未提高');
    if(change('transfer_delta')<0) fail.push('迁移通过变少');
    if(change('test_delta')<0) fail.push('行为检查通过变少');
    if(change('hint_burden_delta')>0) fail.push('提示负担增加');
    return fail.length?'未达条件：'+fail.join('、')+'。':'按本次保存的判定，版本未通过。';
  }
  function trialDetails(results) {
    const list=details('查看本版本 '+results.length+' 条完成记录');
    if(!results.length) return null;
    list.addEventListener('toggle',()=>{
      if(!list.open || list.childElementCount>1) return;
      for(const row of results) {
        const item=details('试验 '+row.trial_id.slice(0,8)+' · 后测 '+readout(row.post_score));
        item.append(dataRow('前测 → 后测',readout(row.pre_score)+' → '+readout(row.post_score)),
          dataRow('迁移',readout(row.transfer_level)+'/4'),
          dataRow('样本',row.eligible?'可纳入对照':'保留记录，未纳入对照'),
          dataRow('决策回读',row.experience_ref||'未引用已验证策略'),
          node('p','检查点 '+row.checkpoint_id+' · 评价 '+row.evaluation_id,'ev-id'),
          node('p','证据 '+row.evidence_ids.join(' / '),'ev-id'));
        for(const action of row.executed_steps) {
          item.append(node('p',action.prompt+(action.feedback_id?' · 依据 '+action.feedback_id:''),'ev-id'));
        }
        list.append(item);
      }
    });
    return list;
  }

  function showVersion(host, data, version) {
    host.replaceChildren();
    const parent=data.versions.find(row=>row.version===version.parent_version);
    const source=parent?.results.find(row=>row.trial_id===version.source_trial_id);
    const pairs=comparisons(version,parent);
    const simulation=data.cohort==='simulation';
    const adopted=version.results.filter(row=>row.strategy_status_at_teach==='validated');
    const recalled=adopted.filter(row=>row.experience_ref==='input-boundary:'+versionName(version.version));
    const headline=node('div',null,'ev-version-heading');
    headline.append(node('h3',versionName(version.parent_version)+' → '+versionName(version.version)),
      node('span',version.status==='validated'&&simulation?'通过模拟门槛':labels[version.status],
        'ev-state ev-state-'+version.status));
    host.append(headline);
    if(recalled.length) headline.append(node('span',recalled.length+' 次后续教学使用并引用新策略','ev-note'));

    const steps=node('ol',null,'ev-story');
    const issue=step(steps,'学生卡在哪里');
    issue.append(node('p',diagnosis(source,version)));
    const sourceDetails=details('查看候选由哪条评价提出');
    sourceDetails.append(node('p',version.reflection),
      node('p','来源试验 '+version.source_trial_id+' · 评价 '+version.source_evaluation_id,'ev-id'),
      node('p','证据 '+version.evidence_ids.join(' / '),'ev-id'));
    issue.append(sourceDetails);

    const change=step(steps,'下一版怎么教');
    const diff=node('div',null,'ev-change');
    for(const [label,text,style] of [
      [versionName(version.parent_version)+' 原教法',version.previous_step,'ev-before'],
      [versionName(version.version)+' 新教法',version.proposed_adjustment,'ev-after']
    ]) {
      const col=node('div',null,style);
      col.append(node('strong',label),node('p',text));
      diff.append(col);
    }
    change.append(diff);

    const judgment=step(steps,'试用结果怎样');
    if(pairs.length) {
      const gain=mean(pairs.map(pair=>pair.delta.gain_delta));
      judgment.append(node('p',pairs.length+' 组配对 · 后测减去前测后，新教法平均增益差 '+sign(gain)+' 分。','ev-comparison-line'),
        validationTable(pairs,version,parent));
      if(version.status==='rejected') judgment.append(node('p',rejectionReasons(pairs,version.validation_plan)));
      judgment.append(comparisonDetails(pairs,version));
    } else {
      const count=version.results.filter(row=>row.strategy_status_at_teach==='testing').length;
      judgment.append(node('p',count
        ? '已完成 '+count+' 次候选试用，等待足够的可比记录后判定。'
        : '还未完成候选试用。达到 '+version.validation_plan.min_pairs+' 组可比配对后才会作出判定。'));
    }

    const reuse=step(steps,'后续有没有用上');
    if(version.history.some(row=>row.status==='validated')) {
      reuse.append(stats([['通过后完成的教学',String(adopted.length)],['Decide 也引用该版本经验',String(recalled.length)]]));
      const example=recalled[0]||adopted[0];
      if(example) {
        const proof=details('查看一条后续教学记录');
        const practice=example.executed_steps.find(action=>action.step==='practice'&&action.phase==='lesson');
        if(practice) proof.append(dataRow('Teach 实际执行',practice.prompt));
        proof.append(dataRow('Decide 经验引用',example.experience_ref||'本轮未引用'),
          node('p','决策 '+example.decision_id+' · 评价 '+example.evaluation_id,'ev-id'));
        reuse.append(proof);
      } else {
        reuse.append(node('p','已通过门槛，等待符合条件的后续试验。','ev-note'));
      }
    } else {
      reuse.append(node('p',version.status==='rejected'
        ? '试用记录已保存。后续默认教学继续沿用原策略。'
        : '当前只供显式试用。验证通过后，匹配的后续教学才会默认使用。'));
    }
    host.append(steps);
    const records=trialDetails(version.results);
    if(records) host.append(records);
  }

  window.renderStrategyEvolution = function renderStrategyEvolution(board,data,selected,onSelect) {
    const versions=data.versions.filter(version=>version.parent_version!=null);
    const headline=versions.find(v=>v.version===selected)
      || versions.findLast(v=>v.history.some(row=>row.status==='validated'))
      || versions.at(-1);
    const simulation=data.cohort==='simulation';
    board.replaceChildren();
    const overview=node('div',null,'ev-overview');
    overview.append(stats([
      [simulation?'已完成模拟试验（含回访）':'已完成真人试验',String(data.trial_count)],
      [simulation?'通过模拟门槛的策略':'通过试点门槛的策略',String(data.validated_count)]
    ]));
    if(simulation) overview.append(node('p','答卷由脚本或手工演练产生，用来检验策略更新流程。','ev-note'));
    board.append(overview);
    if(!headline) {
      const baseline=trialDetails(data.versions[0]?.results||[]);
      board.append(node('p',data.versions.length
        ? '当前使用 v1。后测发现可改进的薄弱项后，这里会出现候选教法。'
        : '还没有试验记录。点击「进行试验」开始前测，或在数据来源中切换到模拟实验。','ev-empty'));
      if(baseline) board.append(baseline);
      return;
    }
    if(versions.length>1) {
      const picker=node('label','查看版本','ev-version-picker');
      const select=node('select');
      for(const version of versions) {
        select.add(new Option(versionName(version.parent_version)+' → '+versionName(version.version)+' · '+(simulation&&version.status==='validated'?'通过模拟门槛':labels[version.status]),version.version));
      }
      select.value=headline.version;
      select.onchange=()=>onSelect(Number(select.value));
      picker.append(select);
      board.append(picker);
    }
    const focus=node('section',null,'ev-focus');
    showVersion(focus,data,headline);
    board.append(focus);
  };
})();
