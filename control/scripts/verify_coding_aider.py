"""Isolated Aider edit smoke test. No credentials, model call or student data."""
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    report = {'scope': 'offline framework plumbing, not model performance', 'status': 'failed'}
    try:
        report['aider_version'] = importlib.metadata.version('aider-chat')
        with tempfile.TemporaryDirectory(prefix='control-coding-') as folder:
            project = Path(folder)
            source = project / 'counter.py'
            source.write_text('def increment(n):\n    return n\n', encoding='utf-8')
            edits = project / 'response.txt'
            edits.write_text('counter.py\n<<<<<<< SEARCH\n    return n\n=======\n    return n + 1\n>>>>>>> REPLACE\n', encoding='utf-8')
            # This is an explicitly synthetic edit-format fixture, never an agent failure sample.
            cmd = [sys.executable, '-m', 'aider', '--no-git', '--no-auto-lint',
                   '--no-auto-test', '--no-check-update', '--analytics-disable',
                   '--no-show-release-notes', '--no-suggest-shell-commands',
                   '--model', 'gpt-4.1-mini-2025-04-14', '--edit-format', 'diff',
                   '--apply', str(edits), '--yes-always', str(source)]
            result = subprocess.run(cmd, cwd=project, capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=90)
            report.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr,
                          before='def increment(n):\n    return n\n', after=source.read_text())
            check = subprocess.run([sys.executable, '-c',
                'from counter import increment; assert increment(3)==4; assert increment(-1)==0'],
                cwd=project, capture_output=True, text=True, timeout=5)
            report['behavior_exit_code'] = check.returncode
            report['status'] = 'passed' if result.returncode == check.returncode == 0 else 'failed'
    except Exception as exc:
        report['error_type'] = type(exc).__name__
    out = ROOT / 'docs/experiments/coding-aider-offline.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'passed' else 1

if __name__ == '__main__':
    raise SystemExit(main())
