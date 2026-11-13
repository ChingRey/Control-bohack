"""Version-bound source references, not semantic correctness certification."""
import hashlib,re
PATTERN=re.compile(r'([A-Za-z0-9_./-]+\.(?:html|css|js|ts|tsx|jsx|json|py|md))[:：](\d+)(?:[-–](\d+))?')
def digest(source):return hashlib.sha256(source.encode('utf-8')).hexdigest()
def collect(text,files):
 result=[]
 for m in PATTERN.finditer(text):
  name,start,end=m[1],int(m[2]),int(m[3] or m[2]);source=files.get(name)
  valid=isinstance(source,str) and 1<=start<=end<=len(source.split('\n'))
  result.append({'file':name,'start':start,'end':end,'valid':valid,'hash':digest(source) if valid else None})
 return result
