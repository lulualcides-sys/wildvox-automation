"""Research-only live Commons licensing preflight; not merged to production."""
import subprocess
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class LiveCommonsLicensePreflight(unittest.TestCase):
    def test_current_forty_sources_exist_and_allow_commercial_reuse(self):
        result=subprocess.run([sys.executable,str(ROOT/"scripts/audit_commons_sources.py"),"--config",str(ROOT/"configs/daily.json")],cwd=ROOT,text=True,capture_output=True,timeout=160)
        self.assertEqual(result.returncode,0,(result.stdout+"\n"+result.stderr)[-4000:])
        self.assertIn("40 authentic assets",result.stdout)
if __name__=="__main__":
    unittest.main()
