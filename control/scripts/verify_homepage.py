"""Real Chromium + isolated HTTP/SQLite. Model fixture; no account requests."""
import sys,json,uuid,tempfile,os,time,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import backend as b
from agents import browser_runner as br,teaching_evolution as e
import test_shared_experience as fixture
out=b.ROOT/'tmp/homepage-verification';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as temp,patch.object(b,'DATA',Path(temp)),patch.object(b,'DB',Path(temp)/'records.sqlite3'),patch.dict(os.environ,{'TEACHING_MODE':'model'}):
 ids=[]
 for title in ('计分项目','第二个计分项目'):
  tid=str(uuid.uuid4());ids.append(tid);sample=fixture.old.task()
  t={**sample,'id':tid,'title':title,'plan':['实现计分'],'plan_draft':[],'step':0,'changes':[],'checks':[],'checkpoint_delivery':'manual','files':{}}
  t.pop('teaching_evolution',None);b.teaching.state(t);b.save(t)
 class Handler(b.Handler):
  def log_message(self,*args):pass
  def do_GET(self):
   if self.path in ('/','/index.html'):
    html=(b.ROOT/'frontend/index.html').read_text(encoding='utf8')
    return self.reply(200,html.encode(),'text/html; charset=utf-8')
   return super().do_GET()
 probe=out/'homepage-browser';(probe/'scripts').mkdir(parents=True,exist_ok=True)
 source=(b.ROOT/'scripts/browser_cases.cjs').read_text(encoding='utf8')
 checks='''
 const assert=async(name,expression)=>{const ok=await evaluate(expression);results.push({name,passed:!!ok});if(!ok)throw Error(name)};
 const wait=ms=>new Promise(r=>setTimeout(r,ms));
 await evaluate(`enterProject(FIRST_ID)`);await wait(400);
 await evaluate(`document.querySelector('#evolution-open').click()`);await wait(450);
 await assert('opens all fifteen experiences as collapsed matrix cards',`document.querySelector('#experience-dialog').open&&document.querySelectorAll('.library-entry').length===15&&document.querySelectorAll('.library-entry[open]').length===0`);
 await assert('only current changes toggle and close remain in header',`document.querySelectorAll('.library-header button').length===2&&document.querySelector('.library-highlight-toggle').textContent==='本轮经验变更'&&!document.querySelector('.library-toolbar')`);
 await assert('dialog is compact and matrix has three columns',`document.querySelector('#experience-dialog').getBoundingClientRect().width<=760&&getComputedStyle(document.querySelector('.library-matrix')).gridTemplateColumns.split(' ').length===3`);
 await assert('collapsed cards contain title and repository source only in summary',`[...document.querySelectorAll('.library-entry')].every(c=>c.querySelector('summary strong')&&c.querySelector('summary small').textContent.includes('加入')&&getComputedStyle(c.querySelector('summary')).minHeight==='104px')`);
 await evaluate(`document.querySelector('.library-highlight-toggle').click()`);
 await assert('toggle removes all red highlights',`document.querySelectorAll('.is-current-change').length===0&&document.querySelector('.library-highlight-toggle').getAttribute('aria-pressed')==='false'`);
 await evaluate(`document.querySelector('.library-highlight-toggle').click()`);
 await assert('toggle restores latest batch highlights',`document.querySelectorAll('.is-current-change').length>0`);
 await evaluate(`api('/tasks/'+task.id+'/teaching/experience-review',{}).then(t=>{task=t;render();pollChat()})`);await wait(2300);
 await assert('new reflection appears first and is the only highlighted card',`document.querySelector('.library-entry').dataset.entryId.startsWith('exp-')&&document.querySelectorAll('.is-current-change').length===1`);
 await assert('latest versions are ordered above older versions',`[...document.querySelectorAll('.library-entry')].every((c,i,arr)=>!i||Number(arr[i-1].dataset.version)>=Number(c.dataset.version))`);
 await evaluate(`document.querySelector('.library-entry>summary').click()`);await wait(100);
 await assert('opening a card reveals strategy evidence and undo',`document.querySelector('.library-entry').open&&document.querySelector('.library-entry').textContent.includes('75分')&&document.querySelector('.library-entry .library-undo-entry')`);
 await wait(1900);
 await assert('polling preserves expanded card',`document.querySelector('.library-entry').open`);
 await evaluate(`document.querySelector('.library-entry>summary').click()`);await wait(100);
 await assert('folding returns to a small matrix card',`document.querySelectorAll('.library-entry[open]').length===0&&document.querySelector('.library-entry').getBoundingClientRect().width<300`);
 await evaluate(`document.querySelector('#experience-dialog').close();enterProject(SECOND_ID)`);await wait(450);
 await evaluate(`api('/tasks/'+task.id+'/teaching/review',{}).then(t=>{task=t;render();pollChat()})`);await wait(1000);
 await assert('next project Teacher sees matching shared trial',`task.messages.some(m=>m.content==='检测到跨项目试用经验')`);
 await evaluate(`document.querySelector('#evolution-open').click()`);await wait(350);
 await assert('reopening resets to all folded experiences',`document.querySelectorAll('.library-entry[open]').length===0&&document.querySelectorAll('.library-entry').length===16`);
 await evaluate(`const c=document.querySelector('.library-entry[data-entry-id^="exp-"]');c.querySelector('summary').click();c.querySelector('.library-entry-content>details').open=true;`);await wait(100);
 await assert('actual teaching reply remains available inside details',`document.querySelector('.library-entry[data-entry-id^="exp-"]').textContent.includes('检测到跨项目试用经验')`);
 await evaluate(`document.querySelector('.library-entry[data-entry-id^="exp-"] .library-undo-entry').click()`);await wait(700);
 await assert('undo still retains scores and marks experience inactive',`document.querySelector('.library-entry[data-entry-id^="exp-"]').textContent.includes('已停用')&&document.querySelector('.library-entry[data-entry-id^="exp-"]').textContent.includes('75分')`);
 await evaluate(`document.querySelectorAll('.library-entry[open]').forEach(c=>c.querySelector('summary').click())`);await wait(100);
 await assert('new experience names its source repository instead of a version',`document.querySelector('.library-entry[data-entry-id^="exp-"]>summary').textContent.includes('计分项目 · 加入')&&!document.querySelector('.library-entry[data-entry-id^="exp-"]>summary').textContent.includes('版')`);
 await evaluate(`api('/tasks/'+FIRST_ID+'/project/rename',{title:'计分新仓库'}).then(()=>window.renderTeachingEvolution())`);await wait(500);
 await assert('renaming repository refreshes experience source label',`document.querySelector('.library-entry[data-entry-id^="exp-"]>summary').textContent.includes('计分新仓库 · 加入')`);
 await evaluate(`document.querySelector('#coding-drag-handle').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));document.querySelector('#coding-minimize').click();document.querySelector('#experience-dialog').close();createHomeProject()`);await wait(100);
 await assert('new project first opens optional repository naming dialog',`document.querySelector('#create-repository-dialog').open&&document.querySelector('#new-repository-name')`);
 await evaluate(`document.querySelector('#new-repository-name').value='恐龙练习仓库';document.querySelector('#create-repository-dialog form').requestSubmit()`);await wait(500);
 await assert('new project resets moved and minimized Coding window',`JSON.parse(localStorage.getItem('control-floating-coding-v5')).following===true&&!document.querySelector('.floating-coding').classList.contains('is-minimized')&&Math.abs(document.querySelector('.floating-coding').getBoundingClientRect().left-document.querySelector('.center').getBoundingClientRect().left-16)<2`);
 await assert('named repository is created and opened',`task.title==='恐龙练习仓库'&&!document.querySelector('#create-repository-dialog')`);
 await evaluate(`createHomeProject();document.querySelector('#create-repository-dialog form').requestSubmit()`);await wait(500);
 await assert('blank repository receives first sequential default name',`task.title==='未命名仓库一'`);
 await evaluate(`createHomeProject();document.querySelector('#create-repository-dialog form').requestSubmit()`);await wait(500);
 await assert('second blank repository receives distinct sequential name',`task.title==='未命名仓库二'`);
 await evaluate(`document.querySelector('#evolution-open').click()`);await wait(350);


 await evaluate(`document.querySelector('#experience-dialog').close();showProjectHome()`);await wait(600);
 await assert('homepage includes adapted hero and project history',`document.querySelectorAll('.studio-project').length===5&&document.querySelector('.studio-headline-control').textContent==='Control'`);
 await evaluate(`document.querySelector('.studio-library-button').click()`);await wait(250);
 await assert('homepage library opens shared matrix',`document.querySelector('#experience-dialog').open&&document.querySelectorAll('.library-entry').length===16`);
 await evaluate(`document.querySelector('#experience-dialog').close();document.querySelector('.studio-search input').value='恐龙';document.querySelector('.studio-search input').dispatchEvent(new Event('input'))`);
 await assert('project search filters history',`document.querySelectorAll('.studio-project:not(.studio-new-project)').length===1`);
 await evaluate(`document.querySelector('.studio-more summary').click();[...document.querySelectorAll('.studio-menu button')].find(b=>b.textContent==='重命名').click()`);
 await evaluate(`const d=[...document.querySelectorAll('dialog[open]')].find(d=>d.querySelector('h2')?.textContent==='仓库名称');d.querySelector('input').value='首页验证改名';d.querySelector('form').requestSubmit()`);await wait(500);
 await assert('rename from card updates project history',`[...document.querySelectorAll('.studio-project-title')].some(b=>b.textContent==='首页验证改名')`);
 await evaluate(`document.querySelector('.studio-search input').value='首页验证改名';document.querySelector('.studio-search input').dispatchEvent(new Event('input'));document.querySelector('.studio-more summary').click();[...document.querySelectorAll('.studio-menu button')].find(b=>b.textContent==='查看教学记录').click()`);await wait(350);
 await assert('teaching record opens from history menu',`document.querySelector('.project-evidence[open] h2').textContent==='首页验证改名'`);
 await evaluate(`document.querySelector('.project-evidence').close();document.querySelector('.studio-search input').value='';document.querySelector('.studio-search input').dispatchEvent(new Event('input'));document.querySelector('#project-home').classList.add('intro-complete')`);await wait(1200);
 await assert('unplanned project has no completed progress segments',`document.querySelector('.studio-project:not(.studio-new-project) .studio-phase-segment.is-complete')===null&&getComputedStyle(document.querySelector('.studio-project:not(.studio-new-project) .studio-phase-segment')).backgroundColor==='rgb(39, 53, 64)'`);
 await assert('all desktop history ships have equal dimensions',`(()=>{const boxes=[...document.querySelectorAll('.studio-project')].map(n=>n.getBoundingClientRect());if(!boxes.every(b=>Math.abs(b.width-boxes[0].width)<1&&Math.abs(b.height-326)<1))throw Error(JSON.stringify(boxes.map(b=>({w:b.width,h:b.height}))));return true})()`);
 await assert('desktop project grid has three columns',`getComputedStyle(document.querySelector('.studio-grid')).gridTemplateColumns.split(' ').length===3`);
 await assert('top banner creates projects and history starts with recent project',`document.querySelector('.studio-resume h2').textContent==='开启新项目'&&!document.querySelector('.studio-new-project')&&document.querySelector('.studio-project').textContent.includes('最近打开')`);
 await evaluate(`document.querySelector('.studio-resume-button').click()`);await wait(100);
 await assert('top banner opens repository naming dialog',`document.querySelector('#create-repository-dialog').open`);
 await evaluate(`document.querySelector('#create-repository-dialog').close();document.querySelector('#project-home').scrollTop=250`);await wait(100);
 let shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(packet.screenshot.replace('.png','-desktop.png'),Buffer.from(shot.data,'base64'));
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await wait(500);
 await assert('narrow screen has one column and no horizontal overflow',`getComputedStyle(document.querySelector('.studio-grid')).gridTemplateColumns.split(' ').length===1&&document.querySelector('#project-home').scrollWidth<=document.querySelector('#project-home').clientWidth+1&&document.documentElement.scrollWidth<=innerWidth`);
 await assert('all narrow screen history ships have equal dimensions',`(()=>{const boxes=[...document.querySelectorAll('.studio-project')].map(n=>n.getBoundingClientRect());if(!boxes.every(b=>Math.abs(b.width-boxes[0].width)<1&&Math.abs(b.height-326)<1))throw Error(JSON.stringify(boxes.map(b=>({w:b.width,h:b.height}))));return true})()`);
 await evaluate(`document.querySelector('#project-home').scrollTop=650`);await wait(100);
 shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(packet.screenshot.replace('.png','-mobile.png'),Buffer.from(shot.data,'base64'));
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await evaluate(`document.querySelector('.studio-project:not(.studio-new-project) .studio-open-project').click()`);await wait(400);
 await assert('version rollback toolbar button removed',`!document.querySelector('#project-versions')`);
 await assert('continue learning restores workspace and floating coding',`!document.body.classList.contains('home-open')&&getComputedStyle(document.querySelector('.workspace')).display!=='none'&&getComputedStyle(document.querySelector('.floating-coding')).position==='fixed'`);

'''.replace('FIRST_ID',json.dumps(ids[0])).replace('SECOND_ID',json.dumps(ids[1]))
 source=source.replace('  if(packet.screenshot){',checks+'\n  if(packet.screenshot){',1);(probe/'scripts/browser_cases.cjs').write_text(source,encoding='utf8')
 calls=[];seen=[]
 def model(config,system,value):
  calls.append(system)
  return fixture.evaluation(value) if '独立教学证据评价器' in system else fixture.analyzed(value['episode'])['reflection']
 def chat(agent,ctx,progress):
  seen.append(ctx['experience_context']);return '检测到跨项目试用经验' if any(x['status']=='trial' for x in ctx['experience_context']['entries']) else '没有试用经验'
 # Keep later background passes from generating extra fixture reviews while UI is asserted.
 with patch.object(e,'call_model',side_effect=model),patch.object(e,'pending',return_value=False),patch.object(b.teaching,'project_chat',side_effect=chat),patch.object(b,'start_organizer'),patch.object(br,'ROOT',probe):
  result=br.run({}, {},[{'action':'wait','ms':900},{'action':'assert_exists','selector':'#evolution-open'}],handler=Handler,screenshot=out/'homepage-ui.png')
 result.update(model_calls=len(calls),teacher_saw_trial=any(any(x['status']=='trial' for x in p['entries']) for p in seen))
 (out/'homepage-ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
 if not result['passed']:raise SystemExit(1)
