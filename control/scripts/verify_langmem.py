"""SDK-only mechanics experiment. Fixed model output is not semantic evaluation."""
import json
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.messages.utils import count_tokens_approximately
from langmem.short_term import summarize_messages

MARKER='EARLY_CONSTRAINT_DO_NOT_USE_NETWORK'
messages=[HumanMessage(content=MARKER,id='m0')]
for i in range(1,80):
 cls=HumanMessage if i%2==0 else AIMessage
 messages.append(cls(content=f'message {i}: '+('discussion of coding and verification. '*18),id=f'm{i}'))
messages.append(HumanMessage(content='CURRENT_PROMPT: validate before creating nodes',id='current'))

def case(threshold,budget):
 captures=[]
 def fixture_model(items):
  captures.append(items)
  return AIMessage(content='Fixture summary: discussion only, no mastery claim.')
 result=summarize_messages(messages,running_summary=None,model=RunnableLambda(fixture_model),
  max_tokens=budget,max_tokens_before_summary=threshold,max_summary_tokens=100,token_counter=count_tokens_approximately)
 actual=' '.join(str(m.content) for batch in captures for m in batch)
 return {'summary_threshold':threshold,'output_budget':budget,'model_calls':len(captures),
  'early_message_marked_summarized':bool(result.running_summary and 'm0' in result.running_summary.summarized_message_ids),
  'early_message_actually_supplied_to_summarizer':MARKER in actual,
  'current_prompt_retained':any(m.id=='current' for m in result.messages),
  'output_approx_tokens':count_tokens_approximately(result.messages)}

def incremental():
 captures=[];summary=None;result=None
 def fixture(items):
  captures.extend(items);return AIMessage(content='Fixture summary: discussion only, no mastery claim.')
 for stop in range(8,len(messages)+8,8):
  result=summarize_messages(messages[:stop],running_summary=summary,model=RunnableLambda(fixture),
    max_tokens=4000,max_tokens_before_summary=1200,max_summary_tokens=100,token_counter=count_tokens_approximately)
  summary=result.running_summary
 return {'mode':'incremental_batches_of_8','early_message_actually_supplied_to_summarizer':MARKER in ' '.join(str(x.content) for x in captures),
         'current_prompt_retained':any(m.id=='current' for m in result.messages)}

result={'sdk':'langmem==0.0.30' ,'mode':'SDK mechanics with fixture model, not real LLM',
 'cases':[case(4000,1200),case(1200,4000)],'incremental':incremental(),
 'conclusion':'一次性输入大量积压历史时，本例最早消息可能在摘要前被裁掉；增量分批例保留了最早原文。不能仅凭已整理ID集认定所有原文都被读过。'}
assert all(x['current_prompt_retained'] for x in result['cases'])
assert result['incremental']['early_message_actually_supplied_to_summarizer']
path=Path(__file__).resolve().parents[1]/'docs/experiments/langmem-sdk.json'
path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
