"""Project-relative files without extension restrictions; text and binary transport."""
import base64
import hashlib
import json
import os
from pathlib import Path


def allowed(name):
    if not isinstance(name, str) or not name or '\x00' in name:
        return False
    normalized = name.replace('\\', '/')
    p = Path(name)
    return not p.is_absolute() and not p.drive and not normalized.startswith('/') and ':' not in normalized and all(
        part not in ('', '.', '..') for part in normalized.split('/'))


def target(root, name):
    if not allowed(name):
        raise ValueError('项目文件路径不允许')
    root = Path(root)
    p = root / name
    if any(x.is_symlink() for x in (p, *p.parents) if x != root and root in x.parents):
        raise ValueError('不允许符号链接')
    p.resolve().relative_to(root.resolve())
    return p


def scan(root):
    text, binary = {}, {}
    def failed(error):raise error
    for folder, dirs, names in os.walk(root, followlinks=False, onerror=failed):
        dirs[:] = [name for name in dirs if not (Path(folder) / name).is_symlink()]
        for filename in names:
            name = (Path(folder) / filename).relative_to(root).as_posix()
            raw = target(root, name).read_bytes()
            try:
                content = raw.decode('utf-8')
                if '\x00' in content:raise UnicodeError('binary content')
            except UnicodeError:
                binary[name] = base64.b64encode(raw).decode('ascii')
            else:
                text[name] = content
    return text, binary


def read(root):return scan(root)[0]
def read_assets(root):return scan(root)[1]
def decode(value):return base64.b64decode(value, validate=True)


def asset_metadata(assets):
    result = {}
    for name, value in assets.items():
        raw = decode(value)
        result[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
    return result


def asset_hash(assets):
    return metadata_hash(asset_metadata(assets))


def metadata_hash(metadata):
    return hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
