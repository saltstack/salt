# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.apache as apache
from salt.ext.six.moves.urllib.error import URLError  # pylint: disable=import-error,no-name-in-module


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ApacheTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.apache
    '''

    def setup_loader_modules(self):
        return {apache: {}}

    # 'version' function tests: 1
    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_version(self):
        '''
        Test if return server version (``apachectl -v``)
        '''
        mock = MagicMock(return_value="Server version: Apache/2.4.7")
        with patch.dict(apache.__salt__, {'cmd.run': mock}):
            self.assertEqual(apache.version(), 'Apache/2.4.7')

    # 'fullversion' function tests: 1

    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_fullversion(self):
        '''
        Test if return server version (``apachectl -V``)
        '''
        mock = MagicMock(return_value="Server version: Apache/2.4.7")
        with patch.dict(apache.__salt__, {'cmd.run': mock}):
            self.assertEqual(apache.fullversion(),
                             {'compiled_with': [],
                              'server_version': 'Apache/2.4.7'})

    # 'modules' function tests: 1

    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_modules(self):
        '''
        Test if return list of static and shared modules
        '''
        mock = MagicMock(return_value=
                         "unixd_module (static)\n \
                         access_compat_module (shared)")
        with patch.dict(apache.__salt__, {'cmd.run': mock}):
            self.assertEqual(apache.modules(),
                             {'shared': ['access_compat_module'],
                              'static': ['unixd_module']})

    # 'servermods' function tests: 1

    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_servermods(self):
        '''
        Test if return list of modules compiled into the server
        '''
        mock = MagicMock(return_value="core.c\nmod_so.c")
        with patch.dict(apache.__salt__, {'cmd.run': mock}):
            self.assertEqual(apache.servermods(), ['core.c', 'mod_so.c'])

    # 'directives' function tests: 1

    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_directives(self):
        '''
        Test if return list of directives
        '''
        mock = MagicMock(return_value="Salt")
        with patch.dict(apache.__salt__, {'cmd.run': mock}):
            self.assertEqual(apache.directives(), {'Salt': ''})

    # 'vhosts' function tests: 1

    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_vhosts(self):
        '''
        Test if it shows the virtualhost settings
        '''
        mock = MagicMock(return_value='')
        with patch.dict(apache.__salt__, {'cmd.run': mock}):
            self.assertEqual(apache.vhosts(), {})

    # 'signal' function tests: 2

    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_signal(self):
        '''
        Test if return no signal for httpd
        '''
        mock = MagicMock(return_value='')
        with patch.dict(apache.__salt__, {'cmd.run': mock}):
            self.assertEqual(apache.signal(None), None)

    @patch('salt.modules.apache._detect_os',
           MagicMock(return_value='apachectl'))
    def test_signal_args(self):
        '''
        Test if return httpd signal to start, restart, or stop.
        '''
        ret = 'Command: "apachectl -k start" completed successfully!'
        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': ''})
        with patch.dict(apache.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(apache.signal('start'), ret)

        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': 'Syntax OK',
                                       'stdout': ''})
        with patch.dict(apache.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(apache.signal('start'), 'Syntax OK')

        mock = MagicMock(return_value={'retcode': 0,
                                       'stderr': 'Syntax OK',
                                       'stdout': ''})
        with patch.dict(apache.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(apache.signal('start'), 'Syntax OK')

        mock = MagicMock(return_value={'retcode': 1,
                                       'stderr': '',
                                       'stdout': 'Salt'})
        with patch.dict(apache.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(apache.signal('start'), 'Salt')

    # 'useradd' function tests: 1

    def test_useradd(self):
        '''
        Test if it add HTTP user using the ``htpasswd`` command
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(apache.__salt__, {'webutil.useradd': mock}):
            self.assertTrue(apache.useradd('htpasswd', 'salt', 'badpassword'))

    # 'userdel' function tests: 1

    def test_userdel(self):
        '''
        Test if it delete HTTP user using the ``htpasswd`` file
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(apache.__salt__, {'webutil.userdel': mock}):
            self.assertTrue(apache.userdel('htpasswd', 'salt'))

    # 'server_status' function tests: 2

    @patch('salt.modules.apache.server_status', MagicMock(return_value={}))
    def test_server_status(self):
        '''
        Test if return get information from the Apache server-status
        '''
        mock = MagicMock(return_value='')
        with patch.dict(apache.__salt__, {'config.get': mock}):
            self.assertEqual(apache.server_status(), {})

    def test_server_status_error(self):
        '''
        Test if return get error from the Apache server-status
        '''
        mock = MagicMock(side_effect=URLError('error'))
        with patch.object(apache, '_urlopen', mock):
            mock = MagicMock(return_value='')
            with patch.dict(apache.__salt__, {'config.get': mock}):
                self.assertEqual(apache.server_status(), 'error')

    # 'config' function tests: 1

    @patch('salt.modules.apache._parse_config',
           MagicMock(return_value='Listen 22'))
    def test_config(self):
        '''
        Test if it create VirtualHost configuration files
        '''
        with patch('salt.utils.fopen', mock_open()):
            self.assertEqual(apache.config('/ports.conf',
                                           [{'Listen': '22'}]), 'Listen 22')
