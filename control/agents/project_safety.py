"""Conservative static signals, never an assertion that a project is secure."""
import re
SECRET=re.compile(r'(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|authorization)\s*[:=]\s*[\x22\x27](?:Bearer\s+)?([A-Za-z0-9_./+\-]{20,})[\x22\x27]|\b(sk-[A-Za-z0-9_.\-]{24,})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
def scan(files):
 findings=[];network_present=False
 for path,text in files.items():
  for number,line in enumerate(text.splitlines(),1):
   if SECRET.search(line):findings.append({'path':path,'line':number,'severity':'critical','rule':'possible_embedded_secret','message':'疑似硬编码凭据；内容已隐藏，请核对并改用环境变量。'})
  if re.search(r'\bfetch\s*\(|\baxios\b|XMLHttpRequest',text):
   network_present=True
   for rule,pattern,note in [('network_timeout',r'AbortController|AbortSignal|timeout','未识别到网络超时处理，请人工核对。'),('network_error',r'catch|onerror|response\.ok|\.status','未识别到网络失败处理，请人工核对。')]:
    if not re.search(pattern,text):findings.append({'path':path,'severity':'review','rule':rule,'message':note})
 return {'kind':'static_signals_not_security_test','findings':findings,'network_present':network_present,'publication_blocked':any(r['severity']=='critical' for r in findings)}
def scrub(value):
 if isinstance(value,dict):return {k:scrub(v) for k,v in value.items()}
 if isinstance(value,list):return [scrub(v) for v in value]
 if isinstance(value,str):
  import json
  try:
   parsed=json.loads(value) if value.lstrip().startswith(('{','[')) else None
   if isinstance(parsed,(dict,list)):
    masked=scrub(parsed)
    return value if masked==parsed else json.dumps(masked,ensure_ascii=False)
  except (ValueError,RecursionError):pass
  return redact(value)
 return value

def redact(text):
 return SECRET.sub('[REDACTED_POSSIBLE_SECRET]',text)
