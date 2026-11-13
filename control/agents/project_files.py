from pathlib import Path
TEXT_EXTENSIONS={'.html','.css','.js','.json','.md','.ts','.jsx','.tsx','.py','.txt','.yaml','.yml','.toml','.svg'}
def allowed(name):
 p=Path(name)
 return not p.is_absolute() and bool(p.parts) and all(part not in ('.','..','node_modules','__pycache__') and not part.startswith('.') for part in p.parts) and p.suffix.lower() in TEXT_EXTENSIONS
def target(root,name):
 if not allowed(name):raise ValueError('项目文件路径不允许')
 p=root/name
 if any(x.is_symlink() for x in (p,*p.parents) if x!=root and root in x.parents):raise ValueError('不允许符号链接')
 p.resolve().relative_to(root.resolve())
 return p
def read(root):
 result={}
 for p in root.rglob('*'):
  name=p.relative_to(root).as_posix()
  if p.is_file() and allowed(name):result[name]=target(root,name).read_text(encoding='utf-8')
 return result
