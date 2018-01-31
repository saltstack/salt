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
    locale_ctl_out = '''
   System Locale: LANG=de_DE.utf8
                  LANGUAGE=de_DE.utf8
       VC Keymap: n/a
      X11 Layout: us
       X11 Model: pc105
    '''
    locale_ctl_out_empty = ''
    locale_ctl_out_broken = '''
    System error:Recursive traversal of loopback mount points
    '''
    locale_ctl_out_structure = '''
       Main: printers=We're upgrading /dev/null
             racks=hardware stress fractures
             failure=Ionisation from the air-conditioning
    Cow say: errors=We're out of slots on the server
             hardware=high pressure system failure
     Reason: The vendor put the bug there.
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
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock(return_value=locale_ctl_out)})
    def test_localectl_status_parser(self):
        '''
        Test localectl status parser.
        :return:
        '''
        out = localemod._localectl_status()
        assert isinstance(out, dict)
        for key in ['system_locale', 'vc_keymap', 'x11_layout', 'x11_model']:
            assert key in out
        assert isinstance(out['system_locale'], dict)
        assert 'LANG' in out['system_locale']
        assert 'LANGUAGE' in out['system_locale']
        assert out['system_locale']['LANG'] == out['system_locale']['LANGUAGE'] == 'de_DE.utf8'
        assert out['vc_keymap'] == 'n/a'
        assert out['x11_layout'] == 'us'
        assert out['x11_model'] == 'pc105'

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.log', MagicMock())
    def test_localectl_status_parser_no_systemd(self):
        '''
        Test localectl status parser raises an exception if no systemd installed.
        :return:
        '''
        with pytest.raises(CommandExecutionError) as err:
            localemod._localectl_status()
        assert 'Unable to find "localectl"' in six.text_type(err)
        assert not localemod.log.debug.called

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock(return_value=locale_ctl_out_empty)})
    def test_localectl_status_parser_empty(self):
        with pytest.raises(CommandExecutionError) as err:
            localemod._localectl_status()
        assert 'Unable to parse result of "localectl"' in six.text_type(err)

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock(return_value=locale_ctl_out_broken)})
    def test_localectl_status_parser_broken(self):
        with pytest.raises(CommandExecutionError) as err:
            localemod._localectl_status()
        assert 'Unable to parse result of "localectl"' in six.text_type(err)

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__salt__', {'cmd.run': MagicMock(return_value=locale_ctl_out_structure)})
    def test_localectl_status_parser_structure(self):
        out = localemod._localectl_status()
        assert isinstance(out, dict)
        for key in ['main', 'cow_say']:
            assert isinstance(out[key], dict)
            for in_key in out[key]:
                assert isinstance(out[key][in_key], unicode)
        assert isinstance(out['reason'], unicode)

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Ubuntu', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
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
    @patch('salt.modules.localemod.dbus', True)
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
    @patch('salt.modules.localemod.dbus', True)
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
    @patch('salt.modules.localemod.dbus', None)
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
    @patch('salt.modules.localemod.dbus', None)
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
    @patch('salt.modules.localemod.dbus', None)
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
    @patch('salt.modules.localemod.dbus', None)
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
    @patch('salt.modules.localemod.dbus', None)
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

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Ubuntu', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
    @patch('salt.utils.systemd.booted', MagicMock(return_value=True))
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    def test_set_locale_with_systemd_nodbus(self):
        '''
        Test setting current system locale with systemd but no dbus available.
        :return:
        '''
        loc = 'de_DE.utf8'
        localemod.set_locale(loc)
        assert localemod._localectl_set.call_args[0][0] == 'de_DE.utf8'

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Ubuntu', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', True)
    @patch('salt.utils.systemd.booted', MagicMock(return_value=True))
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    def test_set_locale_with_systemd_and_dbus(self):
        '''
        Test setting current system locale with systemd and dbus available.
        :return:
        '''
        loc = 'de_DE.utf8'
        localemod.set_locale(loc)
        assert localemod._localectl_set.call_args[0][0] == 'de_DE.utf8'

    @patch('salt.utils.which', MagicMock(return_value="/usr/bin/localctl"))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Suse', 'osmajorrelease': 12})
    @patch('salt.modules.localemod.dbus', True)
    @patch('salt.modules.localemod.__salt__', MagicMock())
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    @patch('salt.utils.systemd.booted', MagicMock(return_value=True))
    def test_set_locale_with_systemd_and_dbus_sle12(self):
        '''
        Test setting current system locale with systemd and dbus available on SLE12.
        :return:
        '''
        loc = 'de_DE.utf8'
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__['file.replace'].called
        assert localemod.__salt__['file.replace'].call_args[0][0] == '/etc/sysconfig/language'
        assert localemod.__salt__['file.replace'].call_args[0][1] == '^RC_LANG=.*'
        assert localemod.__salt__['file.replace'].call_args[0][2] == 'RC_LANG="{}"'.format(loc)

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'RedHat', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
    @patch('salt.modules.localemod.__salt__', MagicMock())
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_redhat(self):
        '''
        Test setting current system locale with systemd and dbus available on RedHat.
        :return:
        '''
        loc = 'de_DE.utf8'
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__['file.replace'].called
        assert localemod.__salt__['file.replace'].call_args[0][0] == '/etc/sysconfig/i18n'
        assert localemod.__salt__['file.replace'].call_args[0][1] == '^LANG=.*'
        assert localemod.__salt__['file.replace'].call_args[0][2] == 'LANG="{}"'.format(loc)

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Debian', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
    @patch('salt.modules.localemod.__salt__', MagicMock())
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_debian(self):
        '''
        Test setting current system locale with systemd and dbus available on Debian.
        :return:
        '''
        loc = 'de_DE.utf8'
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__['file.replace'].called
        assert localemod.__salt__['file.replace'].call_args[0][0] == '/etc/default/locale'
        assert localemod.__salt__['file.replace'].call_args[0][1] == '^LANG=.*'
        assert localemod.__salt__['file.replace'].call_args[0][2] == 'LANG="{}"'.format(loc)

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Gentoo', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
    @patch('salt.modules.localemod.__salt__', MagicMock())
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_gentoo(self):
        '''
        Test setting current system locale with systemd and dbus available on Gentoo.
        :return:
        '''
        loc = 'de_DE.utf8'
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__['cmd.retcode'].call_args[0][0] == 'eselect --brief locale set de_DE.utf8'

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Solaris', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
    @patch('salt.modules.localemod.__salt__', {'locale.list_avail': MagicMock(return_value=['de_DE.utf8']),
                                               'file.replace': MagicMock()})
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_slowlaris_with_list_avail(self):
        '''
        Test setting current system locale with systemd and dbus available on Slowlaris.
        The list_avail returns the proper locale.
        :return:
        '''
        loc = 'de_DE.utf8'
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__['file.replace'].called
        assert localemod.__salt__['file.replace'].call_args[0][0] == '/etc/default/init'
        assert localemod.__salt__['file.replace'].call_args[0][1] == '^LANG=.*'
        assert localemod.__salt__['file.replace'].call_args[0][2] == 'LANG="{}"'.format(loc)

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'Solaris', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
    @patch('salt.modules.localemod.__salt__', {'locale.list_avail': MagicMock(return_value=['en_GB.utf8']),
                                               'file.replace': MagicMock()})
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_slowlaris_without_list_avail(self):
        '''
        Test setting current system locale with systemd and dbus is not available on Slowlaris.
        The list_avail does not return the proper locale.
        :return:
        '''
        loc = 'de_DE.utf8'
        assert not localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert not localemod.__salt__['file.replace'].called

    @patch('salt.utils.which', MagicMock(return_value=None))
    @patch('salt.modules.localemod.__grains__', {'os_family': 'BSD', 'osmajorrelease': 42})
    @patch('salt.modules.localemod.dbus', None)
    @patch('salt.modules.localemod.__salt__', {'locale.list_avail': MagicMock(return_value=['en_GB.utf8']),
                                               'file.replace': MagicMock()})
    @patch('salt.modules.localemod._localectl_set', MagicMock())
    @patch('salt.utils.systemd.booted', MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_unknown(self):
        '''
        Test setting current system locale without systemd on unknown system.
        :return:
        '''
        with pytest.raises(CommandExecutionError) as err:
            localemod.set_locale('de_DE.utf8')
        assert 'Unsupported platform' in six.text_type(err)

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

    @patch('salt.modules.localemod.log', MagicMock())
    @patch('salt.utils.path.which', MagicMock(return_value='/some/dir/path'))
    @patch('salt.modules.localemod.__grains__', {'os': 'Debian'})
    @patch('salt.modules.localemod.__salt__', {'file.search': MagicMock(return_value=False)})
    def test_gen_locale_not_valid(self):
        '''
        Tests the return of gen_locale when the provided locale is not found
        '''
        assert not localemod.gen_locale('foo')
        assert localemod.log.error.called
        msg = localemod.log.error.call_args[0][0] % (localemod.log.error.call_args[0][1],
                                                     localemod.log.error.call_args[0][2])
        assert msg == 'The provided locale "foo" is not found in /usr/share/i18n/SUPPORTED'

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
