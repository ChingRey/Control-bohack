from pathlib import Path
TEXT_EXTENSIONS={'.html','.css','.js','.mjs','.cjs','.json','.jsonc','.md','.ts','.mts','.cts','.jsx','.tsx','.py','.txt','.yaml','.yml','.toml','.svg','.sql','.vue','.svelte','.scss','.less','.go','.java','.rs','.sh','.ps1','.cmd','.bat','.ini','.cfg','.xml','.properties','.graphql','.prisma','.csv','.lock'}
TEXT_NAMES={'Dockerfile','Makefile','Procfile','LICENSE','.gitignore','.dockerignore','.npmrc','.nvmrc','.prettierrc','.eslintrc','.editorconfig','.env.example'}
EXCLUDED_DIRECTORIES={'node_modules','__pycache__','.git','.venv','venv','.next','coverage','.cache'}
def allowed(name):
 if not isinstance(name,str):return False
 p=Path(name)
 return isinstance(name,str) and not p.is_absolute() and bool(p.parts) and all(part not in ('.','..') and part not in EXCLUDED_DIRECTORIES and not part.startswith('.') for part in p.parts[:-1]) and p.name not in EXCLUDED_DIRECTORIES and (p.suffix.lower() in TEXT_EXTENSIONS or p.name in TEXT_NAMES) and p.name not in ('.env',)

def target(root,name):
 if not allowed(name):raise ValueError('项目文件路径不允许')
 p=root/name
 if any(x.is_symlink() for x in (p,*p.parents) if x!=root and root in x.parents):raise ValueError('不允许符号链接')
 p.resolve().relative_to(root.resolve())
 return p
def read(root):
 result={}
 import os
 for folder,dirs,names in os.walk(root,followlinks=False):
  dirs[:]=[name for name in dirs if name not in EXCLUDED_DIRECTORIES and not name.startswith('.') and not (Path(folder)/name).is_symlink()]
  for filename in names:
   p=Path(folder)/filename;name=p.relative_to(root).as_posix()
   if allowed(name):result[name]=target(root,name).read_text(encoding='utf-8')
 return result
