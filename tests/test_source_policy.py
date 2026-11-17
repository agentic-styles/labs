from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_source_policy import historical_artifacts


class SourcePolicyTest(unittest.TestCase):
    def test_rejects_generated_alias_and_removed_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)
            git('init', '-b', 'main')
            git('config', 'user.name', 'Policy Test')
            git('config', 'user.email', 'test@example.invalid')
            (root / 'schema.json').write_text('{}')
            (root / '.env.example').write_text('LLM_API_KEY=')
            git('add', '.')
            git('commit', '-m', 'Allowed sources')
            self.assertEqual(historical_artifacts(root), [])
            (root / 'reports').mkdir()
            (root / 'reports' / 'summary.json').write_text('{}')
            (root / 'sample.pdf').write_text('synthetic artifact')
            (root / '.env').write_text('placeholder-test')
            git('add', '.')
            git('commit', '-m', 'Forbidden aliases and runtime files')
            git('rm', 'reports/summary.json', 'sample.pdf', '.env')
            git('commit', '-m', 'Removed from current tree')
            self.assertEqual(historical_artifacts(root), ['.env', 'reports/summary.json', 'sample.pdf'])


if __name__ == '__main__':
    unittest.main()
