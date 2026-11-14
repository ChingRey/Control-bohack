"""New repositories are named at creation; legacy auto titles remain compatible."""
import re
GENERIC={'','新项目','未命名项目','待办事项 · 示例教程','OpenCode · 分阶段开发（待连接模型）','OpenCode · 分阶段开发'}

def chinese_number(number):
 if number>=10000:return str(number)
 digits='零一二三四五六七八九';result='';zero=False
 for unit,label in ((1000,'千'),(100,'百'),(10,'十'),(1,'')):
  value,number=divmod(number,unit)
  if value:
   if zero:result+='零'
   result+=digits[value]+label;zero=False
  elif result and number:zero=True
 return result[1:] if result.startswith('一十') else result

def initialize(c,task,value=''):
 """Allocate blank names transactionally; never reuse a number after a rename."""
 if not isinstance(value,str):raise ValueError('仓库名称必须是文字')
 if value.strip():
  rename(task,value);return
 c.execute('CREATE TABLE IF NOT EXISTS project_name_counters (name TEXT PRIMARY KEY,value INTEGER NOT NULL)')
 row=c.execute("SELECT value FROM project_name_counters WHERE name='unnamed'").fetchone()
 number=row[0] if row else 0
 import json
 used={json.loads(raw).get('title') for raw, in c.execute('SELECT body FROM tasks')}
 while True:
  number+=1;name='未命名仓库'+chinese_number(number)
  if name not in used:break
 c.execute("INSERT OR REPLACE INTO project_name_counters VALUES ('unnamed',?)",(number,))
 task.update(title=name,title_mode='manual',unnamed_repository_number=number)
def extract(text):
 if not isinstance(text,str):return None
 text=text.strip()
 if text.startswith(('✓','✕','请结合以下建议','本轮')):return None
 match=re.search(r'(?:我(?:们)?(?:想要|想|要|准备|打算)(?:去|来)?|帮我|请你|请)?(?:开发|制作|创建|搭建|编写|设计|做)(?:一下|一个|个|一款|款|一套|套|一份|份)?\s*[“「"]?([^，。！？；：\n"”」]{2,60})',text)
 if not match:return None
 name=match.group(1).strip().strip('“”「」" ')
 name=re.sub(r'(?:可以吗|行吗|好吗|吧|谢谢|给我)$','',name).strip()
 if name in ('什么','什么东西','一下','一些修改','修改','这个','这个项目') or len(name)>40:return None
 return name

def update(task):
 if task.get('title_mode')=='manual':return False
 if task.get('title') not in GENERIC and task.get('title_mode')!='auto':return False
 for i,row in enumerate(task.get('messages',[])):
  if row.get('channel')!='coding' or row.get('role')!='user':continue
  name=extract(row.get('content',''))
  if not name:continue
  if task.get('title')==name and task.get('title_source_message_id')==i:return False
  task.update(title=name,title_mode='auto',title_source_message_id=i);return True
 if task.get('mode')=='opencode' and task.get('title') in GENERIC and task.get('title')!='未命名项目':
  task.update(title='未命名项目',title_mode='auto');return True
 return False

def rename(task,value):
 if not isinstance(value,str) or not 1<=len(value.strip())<=60 or any(ord(c)<32 for c in value):raise ValueError('仓库名称需为1至60个字符，不能包含换行')
 task.update(title=value.strip(),title_mode='manual')
