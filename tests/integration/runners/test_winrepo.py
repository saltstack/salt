# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
import os
import shutil
import tempfile

# Import Salt Testing Libs
import tests.integration as integration
from salt.runners import winrepo
from tests.support.unit import skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

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

winrepo.__opts__ = {
    'winrepo_cachefile': 'winrepo.p',
    'renderer': 'yaml',
    'renderer_blacklist': [],
    'renderer_whitelist': []
}
winrepo.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinrepoTest(integration.ShellCase):
    '''
    Test the winrepo runner
    '''
    def setUp(self):
        super(WinrepoTest, self).setUp()
        self.winrepo_dir = tempfile.mkdtemp(dir=integration.TMP)
        self.addCleanup(shutil.rmtree, self.winrepo_dir, ignore_errors=True)
        self.extmods_dir = tempfile.mkdtemp(dir=integration.TMP)
        self.addCleanup(shutil.rmtree, self.extmods_dir, ignore_errors=True)
        self.winrepo_sls_dir = os.path.join(self.winrepo_dir, 'repo_sls')
        os.mkdir(self.winrepo_sls_dir)
        self.maxDiff = None

    def test_genrepo(self):
        '''
        Test winrepo.genrepo runner
        '''
        sls_file = os.path.join(self.winrepo_sls_dir, 'wireshark.sls')
        # Add a winrepo SLS file
        with open(sls_file, 'w') as fp_:
            fp_.write(_WINREPO_SLS)
        with patch.dict(
                winrepo.__opts__,
                {'file_roots': {'base': [self.winrepo_dir]},
                 'winrepo_dir': self.winrepo_dir,
                 'extension_modules': self.extmods_dir}):
            self.assertEqual(winrepo.genrepo(), _WINREPO_GENREPO_DATA)
