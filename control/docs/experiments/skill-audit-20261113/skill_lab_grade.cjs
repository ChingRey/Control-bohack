// Only synthetic model artifacts: a fresh VM with string/WASM code generation disabled.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const folder = process.argv[2], kind = process.argv[3];
let source='', count=0, errors=[];
function run(code, prefix='') {
  const context=vm.createContext(Object.create(null), {codeGeneration:{strings:false,wasm:false}});
  new vm.Script(prefix+'\n'+code).runInContext(context,{timeout:1500});
  return context;
}
function test(c,code) {
  count++;
  try {new vm.Script(code).runInContext(c,{timeout:1500});} catch(e){errors.push(String(e.message).slice(0,250));}
}
try {
 if(kind==='money') {
  source=fs.readFileSync(path.join(folder,'core.js'),'utf8'); const c=run(source);
  test(c,`if(typeof total!=='function')throw Error('missing total');`);
  test(c,`if(globalThis.version!=='fixture-v1')throw Error('unrelated export changed');`);
  for(const [items,expected] of [[[],0],[[{price:'0',quantity:5}],0],[[{price:'0.29',quantity:3}],87],[[{price:'001.20',quantity:2},{price:'0.03',quantity:7}],261]]){
   test(c,`if(total(${JSON.stringify(items)})!==${expected})throw Error('valid amount mismatch');`);
  }
  for(const price of ['1e2','-1.00','+1','1.',' .5','0.123','Infinity','NaN','',1,null]){
   test(c,`{let threw=false;try{total([{price:${JSON.stringify(price)},quantity:1}])}catch(e){threw=true}if(!threw)throw Error('accepted invalid price ${String(price)}')}`);
  }
  for(const quantity of [-1,0.5,'2',null])test(c,`{let threw=false;try{total([{price:'1.00',quantity:${JSON.stringify(quantity)}}])}catch(e){threw=true}if(!threw)throw Error('accepted invalid quantity')}`);
  test(c,`{const items=[{price:'1.20',quantity:3}];const old=JSON.stringify(items);total(items);if(JSON.stringify(items)!==old)throw Error('input mutated')}`);
  test(c,`{let threw=false;try{total([{price:'90071992547409.92',quantity:1}])}catch(e){threw=true}if(!threw)throw Error('unsafe total accepted')}`);
  test(c,`{for(let i=0;i<80;i++){const p=String(i)+'.'+String((i*13)%100).padStart(2,'0');const q=i%7;const expected=(i*100+(i*13)%100)*q;if(total([{price:p,quantity:q}])!==expected)throw Error('exact cents mismatch')}}`);
 } else if(kind==='store') {
  source=fs.readFileSync(path.join(folder,'core.js'),'utf8');const c=run(source);
  test(c,`if(typeof createStore!=='function')throw Error('missing createStore');`);
  test(c,`{const s=createStore();const a=s.add('  a  '),b=s.add('b');if(!Number.isInteger(a)||a<=0||b<=a)throw Error('invalid ids');if(s.list()[0].title!=='a')throw Error('title not trimmed');s.remove(b);if(s.add('c')<=b)throw Error('id reused')}`);
  test(c,`{const s=createStore();for(const title of ['', '  ', null, 3]){let threw=false;try{s.add(title)}catch(e){threw=true}if(!threw)throw Error('invalid title accepted')}}`);
  test(c,`{const s=createStore();s.add('a');const rows=s.list();rows[0].title='changed';rows.push({id:9,title:'bad'});if(s.list().length!==1||s.list()[0].title!=='a')throw Error('list leaks internal state')}`);
  test(c,`{const a=createStore(),b=createStore();a.add('a');if(b.list().length)throw Error('stores share state');a.remove(999);if(a.list().length!==1)throw Error('unknown removal changed store')}`);
  test(c,`{const s=createStore();let last=0;for(let i=0;i<60;i++){let id=s.add('item');if(id<=last)throw Error('ids not monotonic');last=id;if(i%2===0)s.remove(id)}}`);
 } else if(kind==='counter') {
  const html=fs.readFileSync(path.join(folder,'index.html'),'utf8');
  const css=fs.readFileSync(path.join(folder,'style.css'),'utf8');
  source=fs.readFileSync(path.join(folder,'app.js'),'utf8');
  const staticChecks=[[/id=['"]counter['"]/,html,'counter element'],[/id=['"]increment['"]/,html,'increment element'],[/id=['"]reset['"]/,html,'reset element'],[/aria-live\s*=\s*['"]polite['"]/,html,'live region'],[/name=['"]viewport['"]/,html,'viewport'],[/@media|clamp\(|max-width|width:\s*(?:100%|min\()/,css,'responsive layout']];
  for(const [re,text,label] of staticChecks){count++;if(!re.test(text))errors.push('missing '+label)}
  const prefix=`
  class LabElement { constructor(){this.textContent='';this.events={};this.style={};} addEventListener(k,fn){(this.events[k]??=[]).push(fn)} setAttribute(){} get innerText(){return this.textContent} set innerText(v){this.textContent=String(v)} click(){for(const fn of this.events.click||[])fn({preventDefault(){},target:this});if(this.onclick)this.onclick({preventDefault(){}})} }
  const labNodes={counter:new LabElement(),increment:new LabElement(),reset:new LabElement()};
  const labEvents={};
  const document={readyState:'complete',getElementById(id){return labNodes[id]},querySelector(q){return labNodes[q.replace(/^#/, '')]},addEventListener(k,fn){(labEvents[k]??=[]).push(fn)}};
  const window=globalThis;window.addEventListener=(k,fn)=>(labEvents[k]??=[]).push(fn);
  const localStorage={data:{'coding-skill-counter-v1':'7'},getItem(k){return this.data[k]??null},setItem(k,v){this.data[k]=String(v)}};
  `;
  const c=run(source,prefix);
  test(c,`for(const fn of labEvents.DOMContentLoaded||[])fn();for(const fn of labEvents.load||[])fn();if(typeof window.onload==='function')window.onload();`);
  test(c,`if(String(labNodes.counter.textContent)!=='7')throw Error('stored count not restored');`);
  test(c,`labNodes.increment.click();if(String(labNodes.counter.textContent)!=='8')throw Error('increment failed');if(localStorage.getItem('coding-skill-counter-v1')!=='8')throw Error('increment not persisted');`);
  test(c,`labNodes.reset.click();if(String(labNodes.counter.textContent)!=='0')throw Error('reset failed');if(localStorage.getItem('coding-skill-counter-v1')!=='0')throw Error('reset not persisted');`);
 } else if(kind==='plan') {
  const p=JSON.parse(fs.readFileSync(path.join(folder,'plan.json'),'utf8'));
  count++;if(typeof p.goal!=='string'||!p.goal.trim())errors.push('missing goal');
  count++;if(!Array.isArray(p.steps)||p.steps.length<2||p.steps.length>8)errors.push('step count outside 2..8');
  for(let i=0;i<(p.steps||[]).length;i++){
   const s=p.steps[i];count++;
   if(typeof s.title!=='string'||!s.title.trim()||!Array.isArray(s.files)||!s.files.length||!Array.isArray(s.acceptance)||!s.acceptance.length||!Array.isArray(s.depends_on)||s.depends_on.some(n=>!Number.isInteger(n)||n<0||n>=i))errors.push('invalid step '+i);
  }
  const text=JSON.stringify(p.steps);for(const feature of ['商品','购物车','订单','支付']){count++;if(!text.includes(feature))errors.push('missing '+feature)}
  count++;if(!Array.isArray(p.deferred)||!p.deferred.length)errors.push('missing deferred scope');
  count++;if(/Kubernetes|微服务|直播服务器/.test(text))errors.push('unnecessary architecture in MVP');
 } else throw Error('unknown case');
}catch(e){errors.push(String(e.message).slice(0,300));count=Math.max(count,1)}
process.stdout.write(JSON.stringify({kind,checks:count,passed:Math.max(0,count-errors.length),success:errors.length===0,errors}));
