# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
import os
import shutil
import tempfile

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import salt libs
import salt.utils
import salt.runners.winrepo as winrepo

_WINREPO_SLS = r'''
winscp_x86:
  5.7.5:
    full_name: 'WinSCP 5.7.5'
    installer: 'http://heanet.dl.sourceforge.net/project/winscp/WinSCP/5.7.5/winscp575setup.exe'
    install_flags: '/SP- /verysilent /norestart'
    uninstaller: '%PROGRAMFILES%\WinSCP\unins000.exe'
    uninstall_flags: '/verysilent'
    msiexec: False
    locale: en_US
    reboot: False
  5.7.4:
    full_name: 'WinSCP 5.7.4'
    installer: 'http://cznic.dl.sourceforge.net/project/winscp/WinSCP/5.7.4/winscp574setup.exe'
    install_flags: '/SP- /verysilent /norestart'
    uninstaller: '%PROGRAMFILES%\WinSCP\unins000.exe'
    uninstall_flags: '/verysilent'
    msiexec: False
    locale: en_US
    reboot: False
'''

_WINREPO_GENREPO_DATA = {
    'name_map': {
        'WinSCP 5.7.4': 'winscp_x86',
        'WinSCP 5.7.5': 'winscp_x86'
    },
    'repo': {
        'winscp_x86': {
            '5.7.5': {
                'full_name': 'WinSCP 5.7.5',
                'installer': 'http://heanet.dl.sourceforge.net/project/winscp/WinSCP/5.7.5/winscp575setup.exe',
                'install_flags': '/SP- /verysilent /norestart',
                'uninstaller': '%PROGRAMFILES%\\WinSCP\\unins000.exe',
                'uninstall_flags': '/verysilent',
                'msiexec': False,
                'locale': 'en_US',
                'reboot': False
            },
            '5.7.4': {
                'full_name': 'WinSCP 5.7.4',
                'installer': 'http://cznic.dl.sourceforge.net/project/winscp/WinSCP/5.7.4/winscp574setup.exe',
                'install_flags': '/SP- /verysilent /norestart',
                'uninstaller': '%PROGRAMFILES%\\WinSCP\\unins000.exe',
                'uninstall_flags': '/verysilent',
                'msiexec': False,
                'locale': 'en_US',
                'reboot': False
            }
        }
    }
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinrepoTest(TestCase, LoaderModuleMockMixin):
    '''
    Test the winrepo runner
    '''
    def setup_loader_modules(self):
        self.winrepo_dir = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, self.winrepo_dir, ignore_errors=True)
        self.extmods_dir = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, self.extmods_dir, ignore_errors=True)
        self.winrepo_sls_dir = os.path.join(self.winrepo_dir, 'repo_sls')
        os.mkdir(self.winrepo_sls_dir)
        return {
            winrepo: {
                '__opts__': {
                    'winrepo_cachefile': 'winrepo.p',
                    'renderer': 'yaml',
                    'renderer_blacklist': [],
                    'renderer_whitelist': [],
                    'file_roots': {'base': [self.winrepo_dir]},
                    'winrepo_dir': self.winrepo_dir,
                    'extension_modules': self.extmods_dir
                }
            }
        }

    def test_genrepo(self):
        '''
        Test winrepo.genrepo runner
        '''
        sls_file = os.path.join(self.winrepo_sls_dir, 'wireshark.sls')
        # Add a winrepo SLS file
        with salt.utils.fopen(sls_file, 'w') as fp_:
            fp_.write(_WINREPO_SLS)
        self.assertEqual(winrepo.genrepo(), _WINREPO_GENREPO_DATA)
