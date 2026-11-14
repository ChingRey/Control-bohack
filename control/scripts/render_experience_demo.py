"""Render real demo outputs as an inspectable local HTML report (all text escaped)."""
import html,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=Path(sys.argv[1]) if len(sys.argv)>1 else max((ROOT/'data/demos').glob('experience-live-*'),key=lambda p:p.stat().st_mtime)
r=json.loads((folder/'result.json').read_text(encoding='utf-8'))
p=folder/'comparison.json';c=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
esc=lambda v:html.escape(str(v))
def pre(v):return '<pre>'+esc(json.dumps(v,ensure_ascii=False,indent=2) if not isinstance(v,str) else v)+'</pre>'
def section(title,body):return '<section><h2>'+esc(title)+'</h2>'+body+'</section>'
body='<header><span>CONTROL · 真实模型链路演示</span><h1>经验是否改变了教学？</h1><p>真实模型：'+esc(r['provider']['model'])+'。学生及前置教师对话为人工编写的模拟脚本；隔离数据库，不污染课程。结果仅说明本次调用，不证明学生学会或策略因果有效。</p><p>本轮状态：'+esc(r.get('status','running'))+' · '+esc(r.get('failure',''))+'；实验推理预算：'+esc(r.get('experiment_thinking_budget','未记录'))+'</p></header>'
body+='<nav>'+''.join('<a href="#'+key+'">'+title+'</a>' for key,title in [('evidence','原始证据'),('scores','逐项评分'),('changes','经验变化'),('comparison','有／无经验对照'),('undo','撤销验证')])+'</nav>'
messages=''
for i,m in enumerate(r['input_messages']):messages+='<article><b>消息 '+str(i)+' · '+esc('模拟学生' if m['role']=='user' else '输入脚本中的教师／Coding')+'</b><p>'+esc(m['content'])+'</p></article>'
body+='<div id="evidence">'+section('1. 原始证据（模拟脚本）',messages)+'</div>'
scores=r.get('scores') or next((p['scores'] for p in r.get('progress',[]) if p.get('scores')),[])
scorehtml='<p>分数由真实评价模型按固定条目判定、程序校验并汇总。它不是客观测验分；缺证据记空。</p><div class="grid">'
for score in scores:
 scorehtml+='<article><h3>'+esc(score['name'])+' · '+esc('证据不足' if score['score'] is None else str(score['score'])+'分')+'</h3>'
 for item in score.get('items',[]):
  scorehtml+='<p><b>'+esc(item['id'])+'：'+esc(item['value'])+'</b> '+esc(item['reason'])+'</p>'
  for q in item.get('quotes',[]):scorehtml+='<blockquote>消息 '+str(q['message_id'])+'：'+esc(q['quote'])+'</blockquote>'
 scorehtml+='</article>'
scorehtml+='</div>'
if not scores:scorehtml+='<p>本轮尚未得到通过校验的评分。'+esc(r.get('failure',''))+'</p>'
body+='<div id="scores">'+section('2. 固定标准、原话引用与分数',scorehtml)+'</div>'
changes=''
if r.get('reflection'):changes+='<p>'+esc(r['reflection']['summary'])+'</p>'
for change in r.get('batch',{}).get('changes',[]):
 old,new=change.get('before'),change.get('after');kind='新增' if old is None else '停用' if new['status']=='inactive' else '修改'
 changes+='<article><h3>'+kind+' · '+esc(new['title'])+'</h3><div class="grid">'
 for label,entry in [('修改前',old),('修改后',new)]:
  changes+='<div><b>'+label+'</b>'
  if entry:
   for key,name in [('action','教法'),('when','场景'),('verify','观察'),('limits','边界'),('status','状态'),('revision','版本')]:changes+='<p>'+name+'：'+esc(entry.get(key,''))+'</p>'
  else:changes+='<p>原库没有此条。</p>'
  changes+='</div>'
 changes+='</div><p>依据：'+esc(new.get('reason',new.get('stop_reason','')))+'</p></article>'
if not r.get('batch',{}).get('changes'):changes+='<p>没有已提交的经验变化。可能是决定保留，也可能是评价／反思未通过；请对照运行状态。</p>'
body+='<div id="changes">'+section('3. 真实经验操作（不预设必须新增）',changes)+'</div>'
compare='<p>同一模拟学生问题与项目上下文；只切换经验参考。单次随机生成存在波动，输出不同不能单独证明经验的作用。</p>'
if c:
 compare+='<p>'+esc(c.get('notice',''))+'</p>'+pre(c.get('experiment_limits',{}))
 compare+='<div class="grid">'
 for key,label in [('without_experience','关闭经验参考'),('with_experience','开启经验参考')]:compare+='<article><h3>'+label+'</h3><p class="reply">'+esc(c.get(key,'尚未生成'))+'</p></article>'
 compare+='</div>'
 if c.get('judgment'):
  compare+='<p>独立模型检查可观察动作；下列引用已由程序核实为回复原文。加载记录不能代替采用证据。</p>'
  for item in c['judgment']['criteria']:
   compare+='<article><h3>'+esc(item['criterion'])+'</h3>'
   for key,label in [('A','关闭参考'),('B','开启参考')]:
    row=item[key];compare+='<p>'+label+'：'+esc(row['verdict'])+' · '+esc(row['reason'])+'</p><blockquote>'+esc(row.get('quote',''))+'</blockquote>'
   compare+='</article>'
  compare+='<p>'+esc(c['judgment']['summary'])+'</p>'
 if c.get('error'):compare+='<p>比较尚未完成：'+esc(c['error'])+'</p>'
else:compare+='<p>对照生成尚未完成。</p>'
body+='<div id="comparison">'+section('4. 接入和未接入的真实输出',compare)+'</div>'
body+='<div id="undo">'+section('5. 撤销后的输入检查',pre({'new_entry_ids':r.get('new_entry_ids',[]),'undo_excludes_new_entries':r.get('undo_excludes_new_entries'),'next_focus':r.get('next_project_context',{}).get('validation_focus'),'after_undo':r.get('context_after_undo')}))+'</div>'
body+=section('原始记录','<a href="result.json">真实运行JSON</a> · <a href="comparison.json">对照JSON</a><details><summary>调用耗时与失败记录</summary>'+pre(r.get('request_trace',[]))+'</details>')
css='body{margin:auto;max-width:1160px;padding:36px 22px;background:#111b24;color:#d7e3ea;font:16px/1.8 system-ui,sans-serif}header,section{padding:26px;background:#172632;border:1px solid #344c5b;border-radius:16px;margin-bottom:20px}h1{font-size:34px}h2{font-size:22px;color:#b1dfc7}h3{font-size:17px}a{color:#a9d9c1}nav{display:flex;gap:22px;flex-wrap:wrap;margin:24px 0}article{padding:18px;border:1px solid #3b5160;border-radius:12px;margin:12px 0;background:#1d2d39}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.grid article{margin:0}.grid>div{padding:12px;background:#14212b;border-radius:10px}blockquote{border-left:2px solid #88bca3;margin:10px 0;padding:8px 14px;background:#12222b}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.reply,p{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:750px){.grid{grid-template-columns:1fr}body{padding:14px}}'
(folder/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>经验库真实模型效果演示</title><style>'+css+'</style>'+body+'</html>',encoding='utf-8')
print(folder/'report.html')
