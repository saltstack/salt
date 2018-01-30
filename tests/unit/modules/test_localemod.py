# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

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
try:
    import pytest
except ImportError as import_error:
    pytest = None

# Import Salt Libs
import salt.modules.localemod as localemod
from salt.exceptions import CommandExecutionError
from salt.ext import six

@skipIf(not pytest, False)
@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalemodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.localemod
    '''
    def setup_loader_modules(self):
        return {localemod: {}}

    def test_list_avail(self):
        '''
        Test for Lists available (compiled) locales
        '''
        with patch.dict(localemod.__salt__,
                        {'cmd.run': MagicMock(return_value='A\nB')}):
            self.assertEqual(localemod.list_avail(), ['A', 'B'])

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Ubuntu', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.HAS_DBUS', False)
    @patch('salt.modules.localemod._parse_dbus_locale', MagicMock(return_value={'LANG': 'en_US.utf8'}))
    @patch('salt.modules.localemod._localectl_status', MagicMock(return_value={'system_locale': {'LANG': 'de_DE.utf8'}}))
    @patch('salt.utils.systemd.booted', MagicMock(return_value=True))
    def test_get_locale_with_systemd_nodbus(self):
        '''
        Test getting current system locale with systemd but no dbus available.
        :return:
        '''
        assert localemod.get_locale() == 'de_DE.utf8'

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Ubuntu', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.HAS_DBUS', True)
    @patch('salt.modules.localemod._parse_dbus_locale', MagicMock(return_value={'LANG': 'en_US.utf8'}))
    @patch('salt.modules.localemod._localectl_status', MagicMock(return_value={'system_locale': {'LANG': 'de_DE.utf8'}}))
    @patch('salt.utils.systemd.booted', MagicMock(return_value=True))
    def test_get_locale_with_systemd_and_dbus(self):
        '''
        Test getting current system locale with systemd and dbus available.
        :return:
        '''
        assert localemod.get_locale() == 'en_US.utf8'

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Suse', 'osmajorrelease': 12})
    @patch('salt.modules.localemod.HAS_DBUS', True)
    @patch('salt.modules.localemod._parse_dbus_locale', MagicMock(return_value={'LANG': 'en_US.utf8'}))
    @patch('salt.modules.localemod._localectl_status', MagicMock(return_value={'system_locale': {'LANG': 'de_DE.utf8'}}))
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock()})
    @patch('salt.utils.systemd.booted', MagicMock(return_value=True))
    def test_get_locale_with_systemd_and_dbus_sle12(self):
        '''
        Test getting current system locale with systemd and dbus available on SLE12.
        :return:
        '''
        localemod.get_locale()
        assert localemod.__salt__['cmd.run'].call_args[0][0] == 'grep "^RC_LANG" /etc/sysconfig/language'

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'RedHat', 'osmajorrelease': 12})
    @patch('salt.modules.localemod.HAS_DBUS', False)
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock()})
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_redhat(self):
        '''
        Test getting current system locale with systemd and dbus available on RedHat.
        :return:
        '''
        localemod.get_locale()
        assert localemod.__salt__['cmd.run'].call_args[0][0] == 'grep "^LANG=" /etc/sysconfig/i18n'

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Debian', 'osmajorrelease': 12})
    @patch('salt.modules.localemod.HAS_DBUS', False)
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock()})
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_debian(self):
        '''
        Test getting current system locale with systemd and dbus available on Debian.
        :return:
        '''
        localemod.get_locale()
        assert localemod.__salt__['cmd.run'].call_args[0][0] == 'grep "^LANG=" /etc/default/locale'

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Gentoo', 'osmajorrelease': 12})
    @patch('salt.modules.localemod.HAS_DBUS', False)
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock()})
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_gentoo(self):
        '''
        Test getting current system locale with systemd and dbus available on Gentoo.
        :return:
        '''
        localemod.get_locale()
        assert localemod.__salt__['cmd.run'].call_args[0][0] == 'eselect --brief locale show'

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Solaris', 'osmajorrelease': 12})
    @patch('salt.modules.localemod.HAS_DBUS', False)
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock()})
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_slowlaris(self):
        '''
        Test getting current system locale with systemd and dbus available on Solaris.
        :return:
        '''
        localemod.get_locale()
        assert localemod.__salt__['cmd.run'].call_args[0][0] == 'grep "^LANG=" /etc/default/init'

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'BSD', 'osmajorrelease': 8, 'oscodename': 'DrunkDragon'})
    @patch('salt.modules.localemod.HAS_DBUS', False)
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock()})
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_unknown(self):
        '''
        Test getting current system locale with systemd and dbus available on Gentoo.
        :return:
        '''
        with pytest.raises(CommandExecutionError) as err:
            localemod.get_locale()
        assert '"DrunkDragon" is unsupported' in six.text_type(err)

    def test_set_locale(self):
        '''
        Test for Sets the current system locale
        '''
        with patch.dict(localemod.__context__, {'salt.utils.systemd.booted': True}):
            with patch.dict(localemod.__grains__, {'os_family': ['Unknown']}):
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

    def test_gen_locale_not_valid(self):
        '''
        Tests the return of gen_locale when the provided locale is not found
        '''
        with patch.dict(localemod.__grains__, {'os': 'Debian'}), \
                 patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                 patch.dict(localemod.__salt__,
                            {'file.search': MagicMock(return_value=False)}):
            self.assertFalse(localemod.gen_locale('foo'))

    def test_gen_locale_debian(self):
        '''
        Tests the return of successful gen_locale on Debian system
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__grains__, {'os': 'Debian'}), \
                patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                patch.dict(localemod.__salt__,
                           {'file.search': MagicMock(return_value=True),
                            'file.replace': MagicMock(return_value=True),
                            'cmd.run_all': MagicMock(return_value=ret)}):
            self.assertTrue(localemod.gen_locale('en_US.UTF-8 UTF-8'))

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
        with patch.dict(localemod.__grains__, {'os': 'Debian'}), \
                patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                patch.dict(localemod.__salt__,
                           {'file.search': file_search,
                            'file.replace': MagicMock(return_value=True),
                            'cmd.run_all': MagicMock(return_value=ret)}):
            self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    def test_gen_locale_ubuntu(self):
        '''
        Test the return of successful gen_locale on Ubuntu system
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__salt__,
                        {'file.replace': MagicMock(return_value=True),
                         'file.touch': MagicMock(return_value=None),
                         'file.append': MagicMock(return_value=None),
                         'cmd.run_all': MagicMock(return_value=ret)}), \
                patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                patch('os.listdir', MagicMock(return_value=['en_US'])), \
                patch.dict(localemod.__grains__, {'os': 'Ubuntu'}):
            self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    def test_gen_locale_gentoo(self):
        '''
        Tests the return of successful gen_locale on Gentoo system
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__grains__, {'os_family': 'Gentoo'}), \
                patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                patch('os.listdir', MagicMock(return_value=['en_US.UTF-8'])), \
                patch.dict(localemod.__salt__,
                           {'file.search': MagicMock(return_value=True),
                            'file.replace': MagicMock(return_value=True),
                            'cmd.run_all': MagicMock(return_value=ret)}):
            self.assertTrue(localemod.gen_locale('en_US.UTF-8 UTF-8'))

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
        with patch.dict(localemod.__grains__, {'os_family': 'Gentoo'}), \
                patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                patch('os.listdir', MagicMock(return_value=['en_US.UTF-8'])), \
                patch.dict(localemod.__salt__,
                           {'file.search': file_search,
                            'file.replace': MagicMock(return_value=True),
                            'cmd.run_all': MagicMock(return_value=ret)}):
            self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    def test_gen_locale(self):
        '''
        Tests the return of successful gen_locale
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__salt__,
                        {'cmd.run_all': MagicMock(return_value=ret),
                         'file.replace': MagicMock()}), \
                patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                patch('os.listdir', MagicMock(return_value=['en_US'])):
            self.assertTrue(localemod.gen_locale('en_US.UTF-8'))

    def test_gen_locale_verbose(self):
        '''
        Tests the return of successful gen_locale
        '''
        ret = {'stdout': 'saltines', 'stderr': 'biscuits', 'retcode': 0, 'pid': 1337}
        with patch.dict(localemod.__salt__,
                        {'cmd.run_all': MagicMock(return_value=ret),
                         'file.replace': MagicMock()}), \
                patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path')), \
                patch('os.listdir', MagicMock(return_value=['en_US'])):
            self.assertEqual(localemod.gen_locale('en_US.UTF-8', verbose=True), ret)

    def test_parse_localectl(self):
        localectl_out = ('   System Locale: LANG=en_US.UTF-8\n'
                         '                  LANGUAGE=en_US:en\n'
                         '       VC Keymap: n/a')
        mock_cmd = Mock(return_value=localectl_out)
        with patch.dict(localemod.__salt__, {'cmd.run': mock_cmd}):
            ret = localemod._localectl_status()['system_locale']
            self.assertEqual({'LANG': 'en_US.UTF-8', 'LANGUAGE': 'en_US:en'}, ret)
