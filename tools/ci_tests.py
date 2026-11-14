"""Unittest sonucunu korur, başarısızlık ayrıntılarını GitHub annotation'a ekler."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
loader = unittest.TestLoader()
suite = loader.loadTestsFromNames(sys.argv[1:]) if sys.argv[1:] else loader.discover('tests', top_level_dir='.')
result = unittest.TextTestRunner(verbosity=2).run(suite)
if os.environ.get('GITHUB_ACTIONS') == 'true':
    for test, error in result.errors + result.failures:
        detail = (str(test) + '\n' + error).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print('::error title=Unittest failure::' + detail, flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
