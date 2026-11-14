"""Import glue for unchanged public contract source; no global 'contracts' alias."""
import builtins
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).parent/'public'
def load(name):
    qualified=__name__+'.'+name
    spec=importlib.util.spec_from_file_location(qualified,ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    original=builtins.__import__
    def local_import(name,*args,**kwargs):
        if name=='contracts':return contracts
        return original(name,*args,**kwargs)
    module.__dict__['__builtins__']={**vars(builtins),'__import__':local_import}
    sys.modules[qualified]=module
    try:spec.loader.exec_module(module)
    except BaseException:sys.modules.pop(qualified,None);raise
    return module
contracts=load('contracts')
validator=load('validate_contract')
mock_service=load('mock_service')
service_interface=load('service_interface')
