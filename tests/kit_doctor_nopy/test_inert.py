#!/usr/bin/env python3
"""Static check (an internal task): on Windows without Python, doctor and assets search still work. No processes run."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CMD = (ROOT / 'kit/iamar-world.cmd').read_text()
PS1 = (ROOT / 'kit/doctor/doctor_nopy.ps1').read_text()
PY = (ROOT / 'kit/doctor/doctor.py').read_text()


class NoPythonDoctor(unittest.TestCase):
    def test_launcher_routes_before_python_exit(self):
        i_exit = CMD.index('if not defined PY (echo iamar-world %CMD%: needs Python 3')
        for route in ('if not defined PY if /i "%CMD%"=="doctor" goto doctor_nopy',
                      'if not defined PY if /i "%CMD%"=="assets" goto cmd_assets'):
            self.assertIn(route, CMD)
            self.assertLess(CMD.index(route), i_exit)

    def test_doctor_nopy_label_runs_powershell_script_with_fixed_args(self):
        block = CMD.split(':doctor_nopy', 1)[1].split('\n:', 1)[0]
        self.assertIn('doctor\\doctor_nopy.ps1', block)
        self.assertIn('-NoProfile', block)
        self.assertNotIn('%*', block)       # never expand caller args into a command line (kit-5)
        self.assertIn('exit /b %ERRORLEVEL%', block)

    def test_same_check_ids_as_doctor_py(self):
        ids_py = set(re.findall(r'add\("(\w+)"', PY)) | {'python_numpy', 'python_pillow'}
        ids_ps = set(re.findall(r"Add-Check '(\w+)'", PS1))
        self.assertEqual(ids_ps, ids_py - {'python_numpy', 'python_pillow'})

    def test_python_missing_gives_install_fix(self):
        self.assertIn('winget install Python.Python.3.12', PS1)


if __name__ == '__main__':
    unittest.main()
