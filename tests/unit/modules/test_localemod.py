# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    Mock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.localemod as localemod
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalemodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.localemod
    '''
    loader_module = localemod

    def test_list_avail(self):
        '''
        Test for Lists available (compiled) locales
        '''
        with patch.dict(localemod.__salt__,
                        {'cmd.run': MagicMock(return_value='A\nB')}):
            self.assertEqual(localemod.list_avail(), ['A', 'B'])

    def test_get_locale(self):
        '''
        Test for Get the current system locale
        '''
        with patch.dict(localemod.__context__, {'salt.utils.systemd.booted': True}):
            localemod.HAS_DBUS = True
            with patch.object(localemod,
                              '_parse_dbus_locale',
                              return_value={'LANG': 'A'}):
                self.assertEqual('A', localemod.get_locale())
                localemod._parse_dbus_locale.assert_called_once_with()

            localemod.HAS_DBUS = False
            with patch.object(localemod,
                              '_parse_localectl',
                              return_value={'LANG': 'A'}):
                self.assertEqual('A', localemod.get_locale())
                localemod._parse_localectl.assert_called_once_with()

        with patch.dict(localemod.__context__, {'salt.utils.systemd.booted': False}):
            with patch.dict(localemod.__grains__, {'os_family': ['Gentoo']}):
                with patch.dict(localemod.__salt__, {'cmd.run': MagicMock(return_value='A')}):
                    with patch.object(localemod,
                                      '_parse_localectl',
                                      return_value={'LANG': 'A'}):
                        self.assertEqual(localemod.get_locale(), 'A')

            with patch.dict(localemod.__grains__, {'os_family': ['RedHat']}):
                with patch.dict(localemod.__salt__, {'cmd.run': MagicMock(return_value='A=B')}):
                    with patch.object(localemod,
                                      '_parse_localectl',
                                      return_value={'LANG': 'B'}):
                        self.assertEqual(localemod.get_locale(), 'B')

            with patch.dict(localemod.__grains__, {'os_family': ['Unknown']}):
                with patch.dict(localemod.__salt__, {'cmd.run': MagicMock(return_value='A=B')}):
                    self.assertRaises(CommandExecutionError, localemod.get_locale)

    def test_set_locale(self):
        '''
        Test for Sets the current system locale
        '''
        with patch.dict(localemod.__context__, {'salt.utils.systemd.booted': True}):
            with patch.object(localemod, '_localectl_set', return_value=True):
                self.assertTrue(localemod.set_locale('l'))

        with patch.dict(localemod.__context__, {'salt.utils.systemd.booted': False}):
            with patch.dict(localemod.__grains__, {'os_family': ['Gentoo']}):
                with patch.dict(localemod.__salt__, {'cmd.retcode': MagicMock(return_value='A')}):
                    with patch.object(localemod,
                                      '_parse_localectl',
                                      return_value={'LANG': 'B'}):
                        self.assertFalse(localemod.set_locale('l'))

            with patch.dict(localemod.__grains__, {'os_family': ['A']}):
                with patch.dict(localemod.__salt__, {'cmd.retcode': MagicMock(return_value=0)}):
                    with patch('salt.utils.systemd.booted', return_value=False):
                        self.assertRaises(CommandExecutionError, localemod.set_locale, 'A')

    def test_avail(self):
        '''
        Test for Check if a locale is available
        '''
        with patch('salt.utils.locales.normalize_locale',
                   MagicMock(return_value='en_US.UTF-8 UTF-8')):
            with patch.dict(localemod.__salt__,
                            {'locale.list_avail':
                             MagicMock(return_value=['A', 'B'])}):
                self.assertTrue(localemod.avail('locale'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    def test_gen_locale_not_valid(self):
        '''
        Tests the return of gen_locale when the provided locale is not found
        '''
        with patch.dict(localemod.__grains__, {'os': 'Debian'}):
            with patch.dict(localemod.__salt__,
                            {'file.search': MagicMock(return_value=False)}):
                self.assertFalse(localemod.gen_locale('foo'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    def test_gen_locale_debian(self):
        '''
        Tests the return of successful gen_locale on Debian system
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__grains__, {'os': 'Debian'}):
            with patch.dict(localemod.__salt__,
                            {'file.search': MagicMock(return_value=True),
                             'file.replace': MagicMock(return_value=True),
                             'cmd.run_all': MagicMock(return_value=ret)}):
                self.assertTrue(localemod.gen_locale('en_US.UTF-8 UTF-8'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    def test_gen_locale_debian_no_charmap(self):
        '''
        Tests the return of successful gen_locale on Debian system without a charmap
        '''
        def file_search(search, pattern, flags):
            '''
            mock file.search
            '''
            if len(pattern.split()) == 1:
                return False
            else:  # charmap was supplied
                return True

        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__grains__, {'os': 'Debian'}):
            with patch.dict(localemod.__salt__,
                            {'file.search': file_search,
                             'file.replace': MagicMock(return_value=True),
                             'cmd.run_all': MagicMock(return_value=ret)}):
                self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    @patch('os.listdir', MagicMock(return_value=['en_US']))
    def test_gen_locale_ubuntu(self):
        '''
        Test the return of successful gen_locale on Ubuntu system
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__salt__,
                        {'file.replace': MagicMock(return_value=True),
                         'file.touch': MagicMock(return_value=None),
                         'file.append': MagicMock(return_value=None),
                         'cmd.run_all': MagicMock(return_value=ret)}):
            with patch.dict(localemod.__grains__, {'os': 'Ubuntu'}):
                self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    @patch('os.listdir', MagicMock(return_value=['en_US.UTF-8']))
    def test_gen_locale_gentoo(self):
        '''
        Tests the return of successful gen_locale on Gentoo system
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__grains__, {'os_family': 'Gentoo'}):
            with patch.dict(localemod.__salt__,
                            {'file.search': MagicMock(return_value=True),
                             'file.replace': MagicMock(return_value=True),
                             'cmd.run_all': MagicMock(return_value=ret)}):
                self.assertTrue(localemod.gen_locale('en_US.UTF-8 UTF-8'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    @patch('os.listdir', MagicMock(return_value=['en_US.UTF-8']))
    def test_gen_locale_gentoo_no_charmap(self):
        '''
        Tests the return of successful gen_locale on Gentoo system without a charmap
        '''
        def file_search(search, pattern, flags):
            '''
            mock file.search
            '''
            if len(pattern.split()) == 1:
                return False
            else:  # charmap was supplied
                return True

        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__grains__, {'os_family': 'Gentoo'}):
            with patch.dict(localemod.__salt__,
                            {'file.search': file_search,
                             'file.replace': MagicMock(return_value=True),
                             'cmd.run_all': MagicMock(return_value=ret)}):
                self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    @patch('os.listdir', MagicMock(return_value=['en_US']))
    def test_gen_locale(self):
        '''
        Tests the return of successful gen_locale
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__salt__,
                        {'cmd.run_all': MagicMock(return_value=ret),
                         'file.replace': MagicMock()}):
            self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    @patch('salt.utils.which', MagicMock(return_value='/some/dir/path'))
    @patch('os.listdir', MagicMock(return_value=['en_US']))
    def test_gen_locale_verbose(self):
        '''
        Tests the return of successful gen_locale
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__salt__,
                        {'cmd.run_all': MagicMock(return_value=ret),
                         'file.replace': MagicMock()}):
            self.assertEqual(localemod.gen_locale('en_US.UTF-8', verbose=True), ret)

    def test_parse_localectl(self):
        localectl_out = ('   System Locale: LANG=en_US.UTF-8\n'
                         '                  LANGUAGE=en_US:en\n'
                         '       VC Keymap: n/a')
        mock_cmd = Mock(return_value=localectl_out)
        with patch.dict(localemod.__salt__, {'cmd.run': mock_cmd}):
            ret = localemod._parse_localectl()
            self.assertEqual({'LANG': 'en_US.UTF-8', 'LANGUAGE': 'en_US:en'}, ret)
