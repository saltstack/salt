# -*- coding: utf-8 -*-
'''
    :codeauthor: :email: `Bo Maryniuk <bo@suse.de>`
'''

# Import Python libs
from __future__ import absolute_import
import errno
from mock import Mock

try:
    ERRIO = errno.EREMOTEIO
except:
    ERRIO = errno.EIO

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch
from salt.ext.six.moves import range

ensure_in_syspath('../')

from salt.fileclient import Client


class FileclientTestCase(TestCase):
    '''
    Fileclient test
    '''
    opts = {
        'extension_modules': '',
        'cachedir': '/__test__',
    }

    def _fake_makedir(self, num=errno.EEXIST):
        def _side_effect(*args, **kwargs):
            raise OSError(num, 'Errno {0}'.format(num))
        return Mock(side_effect=_side_effect)

    def test_cache_skips_makedirs_on_race_condition(self):
        '''
        If cache contains already a directory, do not raise an exception.
        '''
        with patch('os.path.isfile', lambda prm: False):
            for exists in range(2):
                with patch('os.makedirs', self._fake_makedir()):
                    with Client(self.opts)._cache_loc('testfile') as c_ref_itr:
                        assert c_ref_itr == '/__test__/files/base/testfile'

    def test_cache_raises_exception_on_non_eexist_ioerror(self):
        '''
        If makedirs raises other than EEXIST errno, an exception should be raised.
        '''
        with patch('os.path.isfile', lambda prm: False):
            with patch('os.makedirs', self._fake_makedir(num=ERRIO)):
                with self.assertRaises(OSError):
                    with Client(self.opts)._cache_loc('testfile') as c_ref_itr:
                        assert c_ref_itr == '/__test__/files/base/testfile'
