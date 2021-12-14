import os
import shutil
import tempfile

import salt.runners.winrepo as winrepo
import salt.utils.files
import salt.utils.stringutils
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

# Can't use raw string with unicode_literals, since the \u in the uninstaller
# will be interpreted as a unicode code point and the interpreter will raise a
# SyntaxError.
_WINREPO_SLS = """
winscp_x86:
  5.7.5:
    full_name: 'WinSCP 5.7.5'
    installer: 'http://heanet.dl.sourceforge.net/project/winscp/WinSCP/5.7.5/winscp575setup.exe'
    install_flags: '/SP- /verysilent /norestart'
    uninstaller: '%PROGRAMFILES%\\WinSCP\\unins000.exe'
    uninstall_flags: '/verysilent'
    msiexec: False
    locale: en_US
    reboot: False
  5.7.4:
    full_name: 'WinSCP 5.7.4'
    installer: 'http://cznic.dl.sourceforge.net/project/winscp/WinSCP/5.7.4/winscp574setup.exe'
    install_flags: '/SP- /verysilent /norestart'
    uninstaller: '%PROGRAMFILES%\\WinSCP\\unins000.exe'
    uninstall_flags: '/verysilent'
    msiexec: False
    locale: en_US
    reboot: False
"""

_WINREPO_GENREPO_DATA = {
    "name_map": {"WinSCP 5.7.4": "winscp_x86", "WinSCP 5.7.5": "winscp_x86"},
    "repo": {
        "winscp_x86": {
            "5.7.5": {
                "full_name": "WinSCP 5.7.5",
                "installer": "http://heanet.dl.sourceforge.net/project/winscp/WinSCP/5.7.5/winscp575setup.exe",
                "install_flags": "/SP- /verysilent /norestart",
                "uninstaller": "%PROGRAMFILES%\\WinSCP\\unins000.exe",
                "uninstall_flags": "/verysilent",
                "msiexec": False,
                "locale": "en_US",
                "reboot": False,
            },
            "5.7.4": {
                "full_name": "WinSCP 5.7.4",
                "installer": "http://cznic.dl.sourceforge.net/project/winscp/WinSCP/5.7.4/winscp574setup.exe",
                "install_flags": "/SP- /verysilent /norestart",
                "uninstaller": "%PROGRAMFILES%\\WinSCP\\unins000.exe",
                "uninstall_flags": "/verysilent",
                "msiexec": False,
                "locale": "en_US",
                "reboot": False,
            },
        }
    },
}


class WinrepoTest(TestCase, LoaderModuleMockMixin):
    """
    Test the winrepo runner
    """

    def setup_loader_modules(self):
        self.winrepo_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.winrepo_dir, ignore_errors=True)
        self.extmods_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.extmods_dir, ignore_errors=True)
        self.winrepo_sls_dir = os.path.join(self.winrepo_dir, "repo_sls")
        os.mkdir(self.winrepo_sls_dir)
        return {
            winrepo: {
                "__opts__": {
                    "winrepo_cachefile": "winrepo.p",
                    "optimization_order": [0, 1, 2],
                    "renderer": "yaml",
                    "renderer_blacklist": [],
                    "renderer_whitelist": [],
                    "file_roots": {"base": [self.winrepo_dir]},
                    "winrepo_dir": self.winrepo_dir,
                    "extension_modules": self.extmods_dir,
                }
            }
        }

    def test_genrepo(self):
        """
        Test winrepo.genrepo runner
        """
        sls_file = os.path.join(self.winrepo_sls_dir, "wireshark.sls")
        # Add a winrepo SLS file
        with salt.utils.files.fopen(sls_file, "w") as fp_:
            fp_.write(salt.utils.stringutils.to_str(_WINREPO_SLS))
        self.assertEqual(winrepo.genrepo(), _WINREPO_GENREPO_DATA)
