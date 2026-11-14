(() => {
  const byId = id => document.getElementById(id);
  const dialog = byId('model-settings-dialog');
  const status = byId('model-settings-status');
  const hostHelp = byId('host-model-settings-help');
  const localForms = byId('local-model-forms');
  const teacher = byId('teacher-model-form');
  const coding = byId('coding-model-form');
  const region = coding.querySelector('[data-model-region]');
  let pending = false;
  let opening = 0;

  function modelSummary(health) {
    const teacherModel = health.teaching.mode === 'model' ? health.teaching.model : '待配置';
    const codingModel = health.coding.configured ? health.coding.model : '待配置';
    const cli = health.coding.installed ? '' : '。本机尚未检测到 OpenCode';
    return 'Teaching：'+teacherModel+' · Coding：'+codingModel+cli+'。';
  }

  function populate(form, metadata, configured) {
    const fields = form.elements;
    if (Array.from(fields.provider.options).some(option => option.value===metadata.provider)) {
      fields.provider.value=metadata.provider;
    }
    fields.model.value=configured ? metadata.model || '' : '';
    fields.api_key.value='';
  }

  async function open() {
    dialog.showModal();
    localForms.hidden=true;
    hostHelp.hidden=true;
    status.textContent='正在读取模型状态…';
    const current=++opening;
    try {
      const health=await api('/health');
      if (opening!==current || !dialog.open) return;
      status.textContent=modelSummary(health);
      if (!health.local_model_settings) {
        hostHelp.hidden=false;
        return;
      }
      populate(teacher,health.teaching,health.teaching.mode==='model');
      populate(coding,health.coding,health.coding.configured);
      region.hidden=coding.elements.provider.value!=='bailian';
      localForms.hidden=false;
    } catch (error) {
      if (opening===current && dialog.open) status.textContent='无法读取模型状态：'+error.message;
    }
  }

  for (const [form, role, label] of [[teacher,'teaching','Teaching'],[coding,'coding','Coding']]) {
    form.elements.provider.addEventListener('change',() => {
      form.elements.model.value='';
      form.elements.api_key.value='';
      region.hidden=coding.elements.provider.value!=='bailian';
    });
    form.addEventListener('submit',async event => {
      event.preventDefault();
      if (pending) return;
      pending=true;
      const body=Object.fromEntries(new FormData(form));
      body.api_key=body.api_key.trim();
      body.model=body.model.trim();
      const button=form.querySelector('button[type=submit]');
      button.disabled=true;
      status.textContent='正在保存 '+label+' 配置…';
      try {
        await api('/settings/'+role,body);
        form.elements.api_key.value='';
        status.textContent=label+' 配置已保存。发一条消息即可验证。';
        if (task && !busy) {
          try { const health=await api('/health'); task.teaching_provider=health.teaching;
            task.coding_provider={...task.coding_provider,...health.coding}; }
          catch { /* Saving succeeded; the next request will refresh the snapshot. */ }
        }
      } catch (error) {
        status.textContent='保存失败：'+error.message;
      } finally {
        pending=false;
        button.disabled=false;
      }
    });
  }

  byId('open-model-settings').addEventListener('click',open);
  byId('close-model-settings').addEventListener('click',()=>{if(!pending) dialog.close();});
  dialog.addEventListener('cancel',event=>{if(pending) event.preventDefault();});
  dialog.addEventListener('close',()=>{
    teacher.elements.api_key.value='';
    coding.elements.api_key.value='';
  });
})();
