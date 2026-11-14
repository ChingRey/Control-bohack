"""Version-bound source references, not semantic correctness certification."""
import hashlib,re
PATTERN=re.compile(r'([A-Za-z0-9_./-]+\.(?:html|css|js|ts|tsx|jsx|json|py|md))(?:[:：](\d+)(?:[-–](\d+))?|`?\s*第\s*(\d+)(?:\s*[-–至]\s*(\d+))?\s*行)')
def digest(source):return hashlib.sha256(source.encode('utf-8')).hexdigest()
def collect(text,files):
 result=[]
 for m in PATTERN.finditer(text):
  name=m[1];start=int(m[2] or m[4]);end=int(m[3] or m[5] or start);source=files.get(name)
  valid=isinstance(source,str) and 1<=start<=end<=len(source.split('\n'))
  result.append({'file':name,'start':start,'end':end,'valid':valid,'hash':digest(source) if valid else None})
 return result
