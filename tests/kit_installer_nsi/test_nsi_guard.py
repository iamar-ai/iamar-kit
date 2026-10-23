"""Static check of tools/kit_installer.nsi: never starts makensis or the installer."""
from pathlib import Path
import unittest

NSI = (Path(__file__).resolve().parents[2] / "tools" / "kit_installer.nsi").read_text()
OWN = 'IfFileExists "$INSTDIR' + "\\" + 'iamar-kit.installed"'


class UninstallSafety(unittest.TestCase):
    def test_non_empty_foreign_folder_is_refused(self):
        self.assertIn("Function .onVerifyInstDir", NSI)
        body = NSI[NSI.index("Function .onVerifyInstDir"):NSI.index("FunctionEnd")]
        self.assertIn(OWN, body)
        self.assertIn("iamar-world.cmd", body)
        self.assertIn("FindFirst", body)
        self.assertIn("Abort", body)

    def test_recursive_delete_only_after_ownership_check(self):
        un = NSI[NSI.index('Section "Uninstall"'):]
        self.assertLess(un.index(OWN), un.index('RMDir /r "$INSTDIR"'))
        self.assertIn("iamar-world.cmd", un)

    def test_marker_written_by_install(self):
        inst = NSI[NSI.index('Section "Install"'):NSI.index('Section "Uninstall"')]
        self.assertIn("iamar-kit.installed", inst)


if __name__ == "__main__":
    unittest.main()
