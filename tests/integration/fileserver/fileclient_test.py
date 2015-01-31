# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.unit import skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
ensure_in_syspath('../..')

# Import salt libs
import integration
from salt import fileclient


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FileClientTest(integration.ModuleCase):

    def setUp(self):
        self.file_client = fileclient.Client(self.master_opts)

    def test_file_list_emptydirs(self):
        '''
        Ensure that the fileclient class won't allow a direct call to file_list_emptydirs()
        '''
        with self.assertRaises(NotImplementedError):
            self.file_client.file_list_emptydirs()

    def test_get_file(self):
        '''
        Ensure that the fileclient class won't allow a direct call to get_file()
        '''
        with self.assertRaises(NotImplementedError):
            self.file_client.get_file(None)

    def test_get_file_client(self):
        with patch.dict(self.get_config('minion', from_scratch=True), {'file_client': 'remote'}):
            with patch('salt.fileclient.RemoteClient', MagicMock(return_value='remote_client')):
                ret = fileclient.get_file_client(self.minion_opts)
                self.assertEqual('remote_client', ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileClientTest)
