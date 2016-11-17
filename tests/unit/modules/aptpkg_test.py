# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Advanced Packaging Tool module 'module.aptpkg'
    :platform: Linux
    :maturity: develop
    versionadded:: nitrogen
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.exceptions import SaltInvocationError
from salt.modules import aptpkg

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

ensure_in_syspath('../../')

# Globals
aptpkg.__salt__ = {}

APT_KEY_LIST = r'''
pub:-:1024:17:46181433FBB75451:1104433784:::-:::scSC:
fpr:::::::::C5986B4F1257FFA86632CBA746181433FBB75451:
uid:-::::1104433784::B4D41942D4B35FF44182C7F9D00C99AF27B93AD0::Ubuntu CD Image Automatic Signing Key <cdimage@ubuntu.com>:
'''

REPO_KEYS = {
    '46181433FBB75451': {
        'algorithm': 17,
        'bits': 1024,
        'capability': 'scSC',
        'date_creation': 1104433784,
        'date_expiration': None,
        'fingerprint': 'C5986B4F1257FFA86632CBA746181433FBB75451',
        'keyid': '46181433FBB75451',
        'uid': 'Ubuntu CD Image Automatic Signing Key <cdimage@ubuntu.com>',
        'uid_hash': 'B4D41942D4B35FF44182C7F9D00C99AF27B93AD0',
        'validity': '-'
    }
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AptPkgTestCase(TestCase):
    '''
    Test cases for salt.modules.aptpkg
    '''

    @patch('salt.modules.aptpkg.get_repo_keys',
           MagicMock(return_value=REPO_KEYS))
    def test_add_repo_key(self):
        '''
        Test - Add a repo key.
        '''
        mock = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'OK'
        })
        with patch.dict(aptpkg.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(aptpkg.add_repo_key(keyserver='keyserver.ubuntu.com',
                                                keyid='FBB75451'))

    @patch('salt.modules.aptpkg.get_repo_keys',
           MagicMock(return_value=REPO_KEYS))
    def test_add_repo_key_failed(self):
        '''
        Test - Add a repo key using incomplete input data.
        '''
        kwargs = {'keyserver': 'keyserver.ubuntu.com'}
        mock = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'OK'
        })
        with patch.dict(aptpkg.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(SaltInvocationError, aptpkg.add_repo_key, **kwargs)

    def test_get_repo_keys(self):
        '''
        Test - List known repo key details.
        '''
        mock = MagicMock(return_value={
            'retcode': 0,
            'stdout': APT_KEY_LIST
        })
        with patch.dict(aptpkg.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(aptpkg.get_repo_keys(), REPO_KEYS)

if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(AptPkgTestCase, needs_daemon=False)
