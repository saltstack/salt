# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import time

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.helpers import destructiveTest
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.gpg as gpg
import salt.utils.path


try:
    import gnupg  # pylint: disable=import-error,unused-import
    HAS_GPG = True
except ImportError:
    HAS_GPG = False


@skipIf(not salt.utils.path.which('gpg'), 'GPG not installed. Skipping')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class GpgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.gpg
    '''
    def setup_loader_modules(self):
        return {gpg: {'__salt__': {}}}

    @skipIf(not HAS_GPG, 'GPG Module Unavailable')
    def test_list_keys(self):
        '''
        Test gpg.list_keys
        '''

        _user_mock = {u'shell': u'/bin/bash',
                      u'workphone': u'',
                      u'uid': 0,
                      u'passwd': u'x',
                      u'roomnumber': u'',
                      u'gid': 0,
                      u'groups': [
                        u'root'
                      ],
                      u'home': u'/root',
                      u'fullname': u'root',
                      u'homephone': u'',
                      u'name': u'root'}

        _list_result = [{u'dummy': u'',
                         u'keyid': u'xxxxxxxxxxxxxxxx',
                         u'expires': u'2011188692',
                         u'sigs': [],
                         u'subkeys': [[u'xxxxxxxxxxxxxxxx', u'e', u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx']],
                         u'length': u'4096',
                         u'ownertrust': u'-',
                         u'sig': u'',
                         u'algo': u'1',
                         u'fingerprint': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                         u'date': u'1506612692',
                         u'trust': u'-',
                         u'type': u'pub',
                         u'uids': [u'GPG Person <person@example.com>']}]

        _expected_result = [{u'keyid': u'xxxxxxxxxxxxxxxx',
                             u'uids': [u'GPG Person <person@example.com>'],
                             u'created': '2017-09-28',
                             u'expires': '2033-09-24',
                             u'keyLength': u'4096',
                             u'ownerTrust': u'Unknown',
                             u'fingerprint': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                             u'trust': u'Unknown'}]

        mock_opt = MagicMock(return_value='root')
        with patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=_user_mock)}):
            with patch.dict(gpg.__salt__, {'config.option': mock_opt}):
                with patch.object(gpg, '_list_keys', return_value=_list_result):
                    self.assertEqual(gpg.list_keys(), _expected_result)

    @skipIf(not HAS_GPG, 'GPG Module Unavailable')
    def test_get_key(self):
        '''
        Test gpg.get_key
        '''

        _user_mock = {u'shell': u'/bin/bash',
                      u'workphone': u'',
                      u'uid': 0,
                      u'passwd': u'x',
                      u'roomnumber': u'',
                      u'gid': 0,
                      u'groups': [
                        u'root'
                      ],
                      u'home': u'/root',
                      u'fullname': u'root',
                      u'homephone': u'',
                      u'name': u'root'}

        _list_result = [{u'dummy': u'',
                         u'keyid': u'xxxxxxxxxxxxxxxx',
                         u'expires': u'2011188692',
                         u'sigs': [],
                         u'subkeys': [[u'xxxxxxxxxxxxxxxx', u'e', u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx']],
                         u'length': u'4096',
                         u'ownertrust': u'-',
                         u'sig': u'',
                         u'algo': u'1',
                         u'fingerprint': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                         u'date': u'1506612692',
                         u'trust': u'-',
                         u'type': u'pub',
                         u'uids': [u'GPG Person <person@example.com>']}]

        _expected_result = {u'fingerprint': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                            u'keyid': u'xxxxxxxxxxxxxxxx',
                            u'uids': [u'GPG Person <person@example.com>'],
                            u'created': u'2017-09-28',
                            u'trust': u'Unknown',
                            u'ownerTrust': u'Unknown',
                            u'expires': u'2033-09-24',
                            u'keyLength': u'4096'}

        mock_opt = MagicMock(return_value='root')
        with patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=_user_mock)}):
            with patch.dict(gpg.__salt__, {'config.option': mock_opt}):
                with patch.object(gpg, '_list_keys', return_value=_list_result):
                    ret = gpg.get_key('xxxxxxxxxxxxxxxx')
                    self.assertEqual(ret, _expected_result)


    @skipIf(True, 'WAR ROOM TEMPORARY SKIP')
    @destructiveTest  # Need to run as root!?
    @skipIf(not HAS_GPG, 'GPG Module Unavailable')
    def test_delete_key(self):
        '''
        Test gpg.delete_key
        '''

        _user_mock = {u'shell': u'/bin/bash',
                      u'workphone': u'',
                      u'uid': 0,
                      u'passwd': u'x',
                      u'roomnumber': u'',
                      u'gid': 0,
                      u'groups': [
                        u'root'
                      ],
                      u'home': u'/root',
                      u'fullname': u'root',
                      u'homephone': u'',
                      u'name': u'root'}

        _list_result = [{'dummy': u'',
                         'keyid': u'xxxxxxxxxxxxxxxx',
                         'expires': u'2011188692',
                         'sigs': [],
                         'subkeys': [[u'xxxxxxxxxxxxxxxx', u'e', u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx']],
                         'length': u'4096',
                         'ownertrust': u'-',
                         'sig': u'',
                         'algo': u'1',
                         'fingerprint': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                         'date': u'1506612692',
                         'trust': u'-',
                         'type': u'pub',
                         'uids': [u'GPG Person <person@example.com>']}]

        _expected_result = {u'res': True,
                            u'message': u'Secret key for xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx deleted\nPublic key for xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx deleted'}

        mock_opt = MagicMock(return_value='root')
        with patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=_user_mock)}):
            with patch.dict(gpg.__salt__, {'config.option': mock_opt}):
                with patch.object(gpg, '_list_keys', return_value=_list_result):
                    with patch('salt.modules.gpg.gnupg.GPG.delete_keys', MagicMock(return_value='ok')):
                        ret = gpg.delete_key('xxxxxxxxxxxxxxxx', delete_secret=True)
                        self.assertEqual(ret, _expected_result)

    @skipIf(not HAS_GPG, 'GPG Module Unavailable')
    def test_search_keys(self):
        '''
        Test gpg.search_keys
        '''

        _user_mock = {'shell': '/bin/bash',
                      'workphone': '',
                      'uid': 0,
                      'passwd': 'x',
                      'roomnumber': '',
                      'gid': 0,
                      'groups': [
                        'root'
                      ],
                      'home': '/root',
                      'fullname': 'root',
                      'homephone': '',
                      'name': 'root'}

        _search_result = [{u'keyid': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                           u'uids': [u'GPG Person <person@example.com>'],
                           u'expires': u'',
                           u'sigs': [],
                           u'length': u'1024',
                           u'algo': u'17',
                           u'date': int(time.mktime(datetime.datetime(2004, 11, 13).timetuple())),
                           u'type': u'pub'}]

        _expected_result = [{u'uids': [u'GPG Person <person@example.com>'],
                             'created': '2004-11-13',
                             u'keyLength': u'1024',
                             u'keyid': u'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}]

        mock_opt = MagicMock(return_value='root')
        with patch.dict(gpg.__salt__, {'user.info': MagicMock(return_value=_user_mock)}):
            with patch.dict(gpg.__salt__, {'config.option': mock_opt}):
                with patch.object(gpg, '_search_keys', return_value=_search_result):
                    ret = gpg.search_keys('person@example.com')
                    self.assertEqual(ret, _expected_result)
