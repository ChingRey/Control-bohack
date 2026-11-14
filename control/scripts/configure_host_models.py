"""Run only on the demo host; never prints or sends keys to a browser."""
import getpass,json,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents import providers,opencode_executor
root=Path(__file__).resolve().parents[1]
print('主机统一模型配置。密钥仅写入本机 data/workbench/host-models.json，不放入交付包。')
teacher_provider=input('Teaching服务商 [siliconflow]: ').strip() or 'siliconflow'
teacher_model=input('Teaching模型 [zai-org/GLM-5.3-Flash]: ').strip() or 'zai-org/GLM-5.3-Flash'
teacher_key=getpass.getpass('Teaching API Key（不显示）: ')
providers.configure(teacher_provider,teacher_key,teacher_model)
coding_provider=input('Coding服务商 [siliconflow]: ').strip() or 'siliconflow'
coding_model=input('Coding模型 [Qwen/Qwen3-Coder-30B-A3B-Instruct]: ').strip() or 'Qwen/Qwen3-Coder-30B-A3B-Instruct'
coding_key=getpass.getpass('Coding API Key（不显示）: ')
opencode_executor.configure(coding_key,coding_model,provider=coding_provider)
config={'teaching':{'provider':teacher_provider,'model':teacher_model,'api_key':teacher_key},'coding':{'provider':coding_provider,'model':coding_model,'api_key':coding_key,'region':'cn'}}
path=root/'data/workbench/host-models.json';path.parent.mkdir(parents=True,exist_ok=True)
temp=path.with_suffix('.tmp');temp.write_text(json.dumps(config,ensure_ascii=False),encoding='utf8');os.chmod(temp,0o600);temp.replace(path)
print('已保存。服务启动或下一次聊天请求时读取；实际可用性需发起真实请求验证。')
