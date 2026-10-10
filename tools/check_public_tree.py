"""Check tracked files for forbidden installation data and common credential formats.

Values are never printed. This is a focused publication guard, not exhaustive DLP.
"""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    re.compile(rb'sk-' + rb'[A-Za-z0-9_-]{24,}'),
    re.compile(rb'gh[pousr]_' + rb'[A-Za-z0-9]{30,}'),
    re.compile(rb'github_pat_' + rb'[A-Za-z0-9_]{30,}'),
    re.compile(rb'-----BEGIN ' + rb'(?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
)
RUNTIME = {'secrets', '.venv', '__pycache__', '.git', 'raster_cache'}
SYSTEM_RUNTIME = {'engines', 'reports', 'work'}

def blocked_path(relative):
    parts = relative.parts
    lower = relative.as_posix().lower()
    if any(p.lower() in RUNTIME for p in parts):
        return True
    if len(parts) > 1 and parts[0] == '_SYSTEM' and parts[1] in SYSTEM_RUNTIME:
        return True
    if lower.startswith('_system/assets/models/'):
        return True
    if parts[0] in {'INPUT', 'OUTPUT'} and relative.name != 'README.txt':
        return True
    return (relative.name.startswith('.env') or lower.endswith(('.dpapi', '.pem', '.key', '_api_key.txt',
        '.mp4', '.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg')) or relative.name == 'session.lock')

def findings(relative, data):
    reasons = []
    if blocked_path(relative): reasons.append('forbidden project/runtime/credential path')
    if len(data) > 15 * 1024 * 1024: reasons.append('file exceeds public-source size limit')
    if any(pattern.search(data) for pattern in PATTERNS): reasons.append('possible credential content')
    return reasons

def files(root):
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True)
    if result.returncode:
        raise ValueError('Initialize Git and stage the intended source tree before scanning.')
    return [Path(name) for name in result.stdout.decode('utf-8').split('\0') if name]

def main():
    issues = []
    paths = files(ROOT)
    if not paths: raise ValueError('No tracked/staged source files to check.')
    for relative in paths:
        path = ROOT / relative
        if path.is_symlink():
            issues.append((relative, ['symlinks are not supported in this source distribution']))
            continue
        for reason in findings(relative, path.read_bytes()):
            issues.append((relative, [reason]))
    for path, reasons in issues:
        print(f'{path.as_posix()}: {", ".join(reasons)}')
    if issues: raise SystemExit('Public-source checks failed. No credential values were printed.')
    print(f'Public-source checks passed: {len(paths)} tracked files; no forbidden paths or common credential matches.')

if __name__ == '__main__':
    main()
