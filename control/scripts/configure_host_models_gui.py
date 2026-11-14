"""Host-only model setup window. Never served to student browsers."""
import json,os,sys,tkinter as tk
from tkinter import ttk,messagebox
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents import providers,opencode_executor
root=Path(__file__).resolve().parents[1]
path=root/'data/workbench/host-models.json'
app=tk.Tk();app.title('Control · 主机模型配置');app.geometry('550x600');app.resizable(False,False)
style=ttk.Style();style.theme_use('clam');style.configure('TLabel',font=('Microsoft YaHei UI',10));style.configure('TButton',font=('Microsoft YaHei UI',10),padding=7)
frame=ttk.Frame(app,padding=24);frame.pack(fill='both',expand=True);frame.columnconfigure(1,weight=1)
ttk.Label(frame,text='主机统一配置，学生直接使用',font=('Microsoft YaHei UI',15,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,16))
values={}
def field(row,key,label,value='',secret=False,options=None):
 ttk.Label(frame,text=label).grid(row=row,column=0,sticky='w',padx=(0,12),pady=7)
 var=tk.StringVar(value=value);values[key]=var
 widget=ttk.Combobox(frame,textvariable=var,values=options,state='readonly') if options else ttk.Entry(frame,textvariable=var,show='●' if secret else '')
 widget.grid(row=row,column=1,sticky='ew',pady=7);return widget
field(1,'teacher_provider','Teaching服务商','siliconflow',options=['siliconflow','deepseek','openai'])
field(2,'teacher_model','Teaching模型','zai-org/GLM-5.3-Flash')
field(3,'teacher_key','Teaching API Key',secret=True)
field(4,'coding_provider','Coding服务商','siliconflow',options=['siliconflow','bailian'])
field(5,'coding_model','Coding模型','Qwen/Qwen3-Coder-30B-A3B-Instruct')
field(6,'coding_key','Coding API Key',secret=True)
ttk.Label(frame,text='两边都用硅基流动时，Coding Key 留空可共用上面的 Key。',wraplength=490).grid(row=7,column=0,columnspan=2,sticky='w',pady=(12,4))
ttk.Label(frame,text='密钥仅保存在这台主机，不显示在学生网页。\n保存后下一条聊天自动生效；实际连接需发消息验证。',wraplength=490).grid(row=8,column=0,columnspan=2,sticky='w',pady=4)
old={}
try:
 old=json.loads(path.read_text(encoding='utf8'))
 for prefix,section in [('teacher','teaching'),('coding','coding')]:
  item=old.get(section,{})
  if item:
   values[prefix+'_provider'].set(item['provider']);values[prefix+'_model'].set(item['model'])
except (OSError,ValueError,KeyError):pass
status=tk.StringVar(value='已存在配置：留空密钥可沿用原配置。' if old else '首次配置：请填写 API Key。')
ttk.Label(frame,textvariable=status,wraplength=490).grid(row=9,column=0,columnspan=2,sticky='w',pady=8)
def save():
 try:
  tp=values['teacher_provider'].get();cp=values['coding_provider'].get()
  tk_=values['teacher_key'].get().strip();ck=values['coding_key'].get().strip()
  if not tk_ and old.get('teaching',{}).get('provider')==tp:tk_=old['teaching']['api_key']
  if not ck and tp==cp=='siliconflow':ck=tk_
  if not ck and old.get('coding',{}).get('provider')==cp:ck=old['coding']['api_key']
  tm=values['teacher_model'].get().strip();cm=values['coding_model'].get().strip()
  providers.configure(tp,tk_,tm);opencode_executor.configure(ck,cm,provider=cp)
  config={'teaching':{'provider':tp,'model':tm,'api_key':tk_},'coding':{'provider':cp,'model':cm,'api_key':ck,'region':'cn'}}
  path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(config,ensure_ascii=False),encoding='utf8');os.chmod(tmp,0o600);tmp.replace(path)
  old.clear();old.update(config);values['teacher_key'].set('');values['coding_key'].set('');status.set('已保存，下次聊天生效。')
  messagebox.showinfo('已保存','主机配置已保存。回到网页发一条消息即可验证，无需学生配置。')
 except (ValueError,KeyError):messagebox.showerror('无法保存','请检查服务商、模型名称和 API Key 是否填写正确。')
 except OSError:messagebox.showerror('无法保存','本机配置文件写入失败，请确认目录可写。')
ttk.Button(frame,text='保存配置',command=save).grid(row=10,column=0,columnspan=2,sticky='ew',pady=8)
app.mainloop()
