"""Build a source-only handoff archive; never include local student data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = ['backend.py', 'README.md', 'AGENTS.md', '.gitignore', '启动工作台.cmd']
DIRECTORIES = ['agents', 'frontend', 'tests', 'docs', 'scripts']

def build():
    output = ROOT / 'dist' / 'Control-source.zip'
    output.parent.mkdir(exist_ok=True)
    sources = [ROOT / name for name in FILES]
    for name in DIRECTORIES:
        sources.extend(p for p in (ROOT / name).rglob('*')
                       if p.is_file() and not p.is_symlink()
                       and '__pycache__' not in p.parts and not p.name.startswith('.env')
                       and p.suffix not in ('.pyc', '.pyo'))
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(sources):
            archive.write(path, 'control/' + path.relative_to(ROOT).as_posix())
    print(f'{output} ({len(sources)} files)')
    return output

if __name__ == '__main__':
    build()
