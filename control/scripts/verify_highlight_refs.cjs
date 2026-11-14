const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../frontend/app.js'),'utf8');
const refCode=source.slice(source.indexOf('function fileReference('),source.indexOf('function linkedText('));
const task={files:{'script.js':'a\nb\nc\nd'},file_hashes:{'script.js':'current'}};
const document={createElement:()=>({})};let target;
const make=refs=>new Function('task','displayedCodeRefs','document','resolveCodeLocation','jumpToCode',refCode+';return fileReference;')
 (task,refs,document,()=>{throw Error('No guessed locations allowed');},(...args)=>target=args);
let button;const el={append:b=>button=b};
make([])(el,'script.js');button.onclick();assert.deepEqual(target,['script.js',undefined,undefined]);
make([{file:'script.js',start:4,end:4,valid:true,hash:'current'}])(el,'script.js','',4);button.onclick();assert.deepEqual(target,['script.js',4,4]);
make([{file:'script.js',start:4,end:4,valid:true,hash:'old'}])(el,'script.js','',4);button.onclick();assert.deepEqual(target,['script.js',undefined,undefined]);
const linkedCode=source.slice(source.indexOf('function linkedText('),source.indexOf('function formatMessage('));
const found=[];const linked=new Function('inlineText','fileReference',linkedCode+';return linkedText;')(()=>{},(...args)=>found.push(args));
linked({append:()=>{}},'script.js 第 4 行、script.js:2-3');
assert.equal(found[0][3],'4');assert.equal(found[1][3],'2');assert.equal(found[1][4],'3');
console.log('PASS: exact line, Chinese line, stale reference, filename-only without guessing');
