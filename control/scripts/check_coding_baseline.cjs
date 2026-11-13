const fs=require('fs'),vm=require('vm'),assert=require('assert');const p='docs/experiments/coding-baseline/raw.json';const raw=JSON.parse(fs.readFileSync(p,'utf8'));const results=[];
for(const t of raw.trials){let scope={};vm.runInNewContext(t.files['core.js']||'',scope,{timeout:1000});const checks=[];function test(name,fn){try{fn();checks.push({name,pass:true})}catch(e){checks.push({name,pass:false,error:e.message})}}
if(t.name==='money'){
 test('empty',()=>assert.equal(scope.total([]),0));test('decimal precision',()=>assert.equal(scope.total([{price:'0.10',quantity:3}]),30));test('mixed total',()=>assert.equal(scope.total([{price:'19.99',quantity:3},{price:'0',quantity:0}]),5997));
 for(const price of ['-1','1.234','abc'])test('reject '+price,()=>assert.throws(()=>scope.total([{price,quantity:1}])));
 test('fractional quantity',()=>assert.throws(()=>scope.total([{price:'1',quantity:1.5}])));test('no mutation',()=>{let a=[{price:'2.00',quantity:2}],before=JSON.stringify(a);scope.total(a);assert.equal(JSON.stringify(a),before)})
}else{test('trim',()=>{let s=scope.createStore();s.add(' x ');assert.equal(s.list()[0].title,'x')});test('blank reject',()=>assert.throws(()=>scope.createStore().add('  ')));test('stable IDs',()=>{let s=scope.createStore(),a=s.add('a');s.remove(a);assert(s.add('b')>a)});test('list isolation',()=>{let s=scope.createStore();s.add('a');s.list()[0].title='bad';assert.equal(s.list()[0].title,'a')});test('independent instances',()=>{let a=scope.createStore(),b=scope.createStore();a.add('a');assert.equal(b.list().length,0)})}
results.push({task:t.name,checks});}
fs.writeFileSync('docs/experiments/coding-baseline/checks.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results));
