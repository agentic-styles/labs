"""Reject generated artifacts and secrets files in all reachable Git trees."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {'output', 'outputs', 'reports', 'dist', 'build', '.generated', '.venv', '__pycache__', '.pytest_cache', '.langgraph_api'}
FORBIDDEN_SUFFIXES = {'.html', '.htm', '.pdf', '.png', '.jpg', '.jpeg', '.bundle', '.pckl', '.pyc', '.pyo'}


def historical_artifacts(repository: Path) -> list[str]:
    trees = set(subprocess.check_output(['git', 'log', '--all', '--format=%T'], cwd=repository, text=True).splitlines())
    forbidden = set()
    for tree in trees:
        paths = subprocess.check_output(['git', 'ls-tree', '-rz', '--name-only', tree], cwd=repository).decode().split('\0')
        for name in filter(None, paths):
            path = Path(name)
            env_secret = path.name.startswith('.env') and path.name not in {'.env.example', '.env.sample'}
            if path.suffix.lower() in FORBIDDEN_SUFFIXES or set(path.parts) & FORBIDDEN_PARTS or env_secret or name.endswith('.pdf.tmp'):
                forbidden.add(name)
    return sorted(forbidden)


if __name__ == '__main__':
    violations = historical_artifacts(ROOT)
    if violations:
        raise SystemExit('Generated artifacts or secrets files in Git history:\n' + '\n'.join(violations))
    print('PASS: all reachable Git history contains source and frozen fixtures only')
