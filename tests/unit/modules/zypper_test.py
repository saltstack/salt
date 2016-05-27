# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salt.exceptions import CommandExecutionError

import os
from salt.ext.six.moves import configparser
import StringIO

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


class ZyppCallMock(object):
    def __init__(self, return_value=None):
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()


def get_test_data(filename):
    '''
    Return static test data
    '''
    return open(os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zypp'), filename)).read()


# Import Salt Libs
from salt.modules import zypper

# Globals
zypper.__salt__ = dict()
zypper.__context__ = dict()
zypper.rpm = None


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZypperTestCase(TestCase):
    '''
    Test cases for salt.modules.zypper
    '''

    def test_list_upgrades(self):
        '''
        List package upgrades
        :return:
        '''
        ref_out = {
            'stdout': get_test_data('zypper-updates.xml'),
            'stderr': None,
            'retcode': 0
        }
        with patch.dict(zypper.__salt__, {'cmd.run_all': MagicMock(return_value=ref_out)}):
            upgrades = zypper.list_upgrades(refresh=False)
            self.assertEqual(len(upgrades), 3)
            for pkg, version in {'SUSEConnect': '0.2.33-7.1',
                                 'bind-utils': '9.9.6P1-35.1',
                                 'bind-libs': '9.9.6P1-35.1'}.items():
                self.assertIn(pkg, upgrades)
                self.assertEqual(upgrades[pkg], version)

    def test_zypper_caller(self):
        '''
        Test Zypper caller.
        :return:
        '''
        class RunSniffer(object):
            def __init__(self, stdout=None, stderr=None, retcode=None):
                self.calls = list()
                self._stdout = stdout or ''
                self._stderr = stderr or ''
                self._retcode = retcode or 0

            def __call__(self, *args, **kwargs):
                self.calls.append({'args': args, 'kwargs': kwargs})
                return {'stdout': self._stdout,
                        'stderr': self._stderr,
                        'retcode': self._retcode}

        stdout_xml_snippet = '<?xml version="1.0"?><test foo="bar"/>'
        sniffer = RunSniffer(stdout=stdout_xml_snippet)
        with patch.dict('salt.modules.zypper.__salt__', {'cmd.run_all': sniffer}):
            self.assertEqual(zypper.__zypper__.call('foo'), stdout_xml_snippet)
            self.assertEqual(len(sniffer.calls), 1)

            zypper.__zypper__.call('bar')
            self.assertEqual(len(sniffer.calls), 2)
            self.assertEqual(sniffer.calls[0]['args'][0], ['zypper', '--non-interactive', '--no-refresh', 'foo'])
            self.assertEqual(sniffer.calls[1]['args'][0], ['zypper', '--non-interactive', '--no-refresh', 'bar'])

            dom = zypper.__zypper__.xml.call('xml-test')
            self.assertEqual(sniffer.calls[2]['args'][0], ['zypper', '--non-interactive', '--xmlout',
                                                           '--no-refresh', 'xml-test'])
            self.assertEqual(dom.getElementsByTagName('test')[0].getAttribute('foo'), 'bar')

            zypper.__zypper__.refreshable.call('refresh-test')
            self.assertEqual(sniffer.calls[3]['args'][0], ['zypper', '--non-interactive', 'refresh-test'])

            zypper.__zypper__.nolock.call('no-locking-test')
            self.assertEqual(sniffer.calls[4].get('kwargs', {}).get('env', {}).get('ZYPP_READONLY_HACK'), "1")
            self.assertEqual(sniffer.calls[4].get('kwargs', {}).get('env', {}).get('SALT_RUNNING'), "1")

            zypper.__zypper__.call('locking-test')
            self.assertEqual(sniffer.calls[5].get('kwargs', {}).get('env', {}).get('ZYPP_READONLY_HACK'), None)
            self.assertEqual(sniffer.calls[5].get('kwargs', {}).get('env', {}).get('SALT_RUNNING'), "1")

        # Test exceptions
        stdout_xml_snippet = '<?xml version="1.0"?><stream><message type="error">Booya!</message></stream>'
        sniffer = RunSniffer(stdout=stdout_xml_snippet, retcode=1)
        with patch.dict('salt.modules.zypper.__salt__', {'cmd.run_all': sniffer}):
            with self.assertRaisesRegexp(CommandExecutionError, '^Zypper command failure: Booya!$'):
                zypper.__zypper__.xml.call('crashme')

            with self.assertRaisesRegexp(CommandExecutionError, "^Zypper command failure: Check Zypper's logs.$"):
                zypper.__zypper__.call('crashme again')

            zypper.__zypper__.noraise.call('stay quiet')
            self.assertEqual(zypper.__zypper__.error_msg, "Check Zypper's logs.")

    def test_list_upgrades_error_handling(self):
        '''
        Test error handling in the list package upgrades.
        :return:
        '''
        # Test handled errors
        ref_out = {
            'stdout': '''<?xml version='1.0'?>
<stream>
 <message type="info">Refreshing service &apos;container-suseconnect&apos;.</message>
 <message type="error">Some handled zypper internal error</message>
 <message type="error">Another zypper internal error</message>
</stream>
            ''',
            'stderr': '',
            'retcode': 1,
        }
        with patch.dict('salt.modules.zypper.__salt__', {'cmd.run_all': MagicMock(return_value=ref_out)}):
            with self.assertRaisesRegexp(CommandExecutionError,
                    "^Zypper command failure: Some handled zypper internal error\nAnother zypper internal error$"):
                zypper.list_upgrades(refresh=False)

        # Test unhandled error
        ref_out = {
            'retcode': 1,
            'stdout': '',
            'stderr': ''
        }
        with patch.dict('salt.modules.zypper.__salt__', {'cmd.run_all': MagicMock(return_value=ref_out)}):
            with self.assertRaisesRegexp(CommandExecutionError, "^Zypper command failure: Check Zypper's logs.$"):
                zypper.list_upgrades(refresh=False)

    def test_list_products(self):
        '''
        List products test.
        '''
        for filename, test_data in {
            'zypper-products-sle12sp1.xml': {
                'name': ['SLES', 'SLES', 'SUSE-Manager-Proxy',
                         'SUSE-Manager-Server', 'sle-manager-tools-beta',
                         'sle-manager-tools-beta-broken-eol', 'sle-manager-tools-beta-no-eol'],
                'vendor': 'SUSE LLC <https://www.suse.com/>',
                'release': ['0', '0', '0', '0', '0', '0', '0'],
                'productline': [False, False, False, False, False, False, 'sles'],
                'eol_t': [None, 0, 1509408000, 1522454400, 1522454400, 1730332800, 1730332800],
                'isbase': [False, False, False, False, False, False, True],
                'installed': [False, False, False, False, False, False, True],
            },
            'zypper-products-sle11sp3.xml': {
                'name': ['SUSE-Manager-Server', 'SUSE-Manager-Server', 'SUSE-Manager-Server-Broken-EOL',
                         'SUSE_SLES', 'SUSE_SLES', 'SUSE_SLES', 'SUSE_SLES-SP4-migration'],
                'vendor': 'SUSE LINUX Products GmbH, Nuernberg, Germany',
                'release': ['1.138', '1.2', '1.2', '1.2', '1.201', '1.201', '1.4'],
                'productline': [False, False, False, False, False, 'manager', 'manager'],
                'eol_t': [None, 0, 0, 0, 0, 0, 0],
                'isbase': [False, False, False, False, False, True, True],
                'installed': [False, False, False, False, False, True, True],
            }}.items():

            ref_out = {
                    'retcode': 0,
                    'stdout': get_test_data(filename)
            }

            with patch.dict(zypper.__salt__, {'cmd.run_all': MagicMock(return_value=ref_out)}):
                products = zypper.list_products()
                self.assertEqual(len(products), 7)
                self.assertIn(test_data['vendor'], [product['vendor'] for product in products])
                for kwd in ['name', 'isbase', 'installed', 'release', 'productline', 'eol_t']:
                    self.assertEqual(test_data[kwd], sorted([prod.get(kwd) for prod in products]))

    def test_refresh_db(self):
        '''
        Test if refresh DB handled correctly
        '''
        ref_out = [
            "Repository 'openSUSE-Leap-42.1-LATEST' is up to date.",
            "Repository 'openSUSE-Leap-42.1-Update' is up to date.",
            "Retrieving repository 'openSUSE-Leap-42.1-Update-Non-Oss' metadata",
            "Forcing building of repository cache",
            "Building repository 'openSUSE-Leap-42.1-Update-Non-Oss' cache ..........[done]",
            "Building repository 'salt-dev' cache",
            "All repositories have been refreshed."
        ]

        run_out = {
            'stderr': '', 'stdout': '\n'.join(ref_out), 'retcode': 0
        }

        with patch.dict(zypper.__salt__, {'cmd.run_all': MagicMock(return_value=run_out)}):
            result = zypper.refresh_db()
            self.assertEqual(result.get("openSUSE-Leap-42.1-LATEST"), False)
            self.assertEqual(result.get("openSUSE-Leap-42.1-Update"), False)
            self.assertEqual(result.get("openSUSE-Leap-42.1-Update-Non-Oss"), True)

    def test_info_installed(self):
        '''
        Test the return information of the named package(s), installed on the system.

        :return:
        '''
        run_out = {
            'virgo-dummy':
                {'build_date': '2015-07-09T10:55:19Z',
                 'vendor': 'openSUSE Build Service',
                 'description': 'This is the Virgo dummy package used for testing SUSE Manager',
                 'license': 'GPL-2.0', 'build_host': 'sheep05', 'url': 'http://www.suse.com',
                 'build_date_time_t': 1436432119, 'relocations': '(not relocatable)',
                 'source_rpm': 'virgo-dummy-1.0-1.1.src.rpm', 'install_date': '2016-02-23T16:31:57Z',
                 'install_date_time_t': 1456241517, 'summary': 'Virgo dummy package', 'version': '1.0',
                 'signature': 'DSA/SHA1, Thu Jul  9 08:55:33 2015, Key ID 27fa41bd8a7c64f9',
                 'release': '1.1', 'group': 'Applications/System', 'arch': 'noarch', 'size': '17992'},

            'libopenssl1_0_0':
                {'build_date': '2015-11-04T23:20:34Z', 'vendor': 'SUSE LLC <https://www.suse.com/>',
                 'description': 'The OpenSSL Project is a collaborative effort.',
                 'license': 'OpenSSL', 'build_host': 'sheep11', 'url': 'https://www.openssl.org/',
                 'build_date_time_t': 1446675634, 'relocations': '(not relocatable)',
                 'source_rpm': 'openssl-1.0.1i-34.1.src.rpm', 'install_date': '2016-02-23T16:31:35Z',
                 'install_date_time_t': 1456241495, 'summary': 'Secure Sockets and Transport Layer Security',
                 'version': '1.0.1i', 'signature': 'RSA/SHA256, Wed Nov  4 22:21:34 2015, Key ID 70af9e8139db7c82',
                 'release': '34.1', 'group': 'Productivity/Networking/Security', 'packager': 'https://www.suse.com/',
                 'arch': 'x86_64', 'size': '2576912'},
        }
        with patch.dict(zypper.__salt__, {'lowpkg.info': MagicMock(return_value=run_out)}):
            installed = zypper.info_installed()
            # Test overall products length
            self.assertEqual(len(installed), 2)

            # Test translated fields
            for pkg_name, pkg_info in installed.items():
                self.assertEqual(installed[pkg_name].get('source'), run_out[pkg_name]['source_rpm'])

            # Test keys transition from the lowpkg.info
            for pn_key, pn_val in run_out['virgo-dummy'].items():
                if pn_key == 'source_rpm':
                    continue
                self.assertEqual(installed['virgo-dummy'][pn_key], pn_val)

    def test_info_available(self):
        '''
        Test return the information of the named package available for the system.

        :return:
        '''
        test_pkgs = ['vim', 'emacs', 'python']
        with patch('salt.modules.zypper.__zypper__', ZyppCallMock(return_value=get_test_data('zypper-available.txt'))):
            available = zypper.info_available(*test_pkgs, refresh=False)
            self.assertEqual(len(available), 3)
            for pkg_name, pkg_info in available.items():
                self.assertIn(pkg_name, test_pkgs)

            self.assertEqual(available['emacs']['status'], 'up-to-date')
            self.assertTrue(available['emacs']['installed'])
            self.assertEqual(available['emacs']['support level'], 'Level 3')
            self.assertEqual(available['emacs']['vendor'], 'SUSE LLC <https://www.suse.com/>')
            self.assertEqual(available['emacs']['summary'], 'GNU Emacs Base Package')

            self.assertEqual(available['vim']['status'], 'not installed')
            self.assertFalse(available['vim']['installed'])
            self.assertEqual(available['vim']['support level'], 'Level 3')
            self.assertEqual(available['vim']['vendor'], 'SUSE LLC <https://www.suse.com/>')
            self.assertEqual(available['vim']['summary'], 'Vi IMproved')

    @patch('salt.modules.zypper.refresh_db', MagicMock(return_value=True))
    def test_latest_version(self):
        '''
        Test the latest version of the named package available for upgrade or installation.

        :return:
        '''
        with patch('salt.modules.zypper.__zypper__', ZyppCallMock(return_value=get_test_data('zypper-available.txt'))):
            self.assertEqual(zypper.latest_version('vim'), '7.4.326-2.62')

    @patch('salt.modules.zypper.refresh_db', MagicMock(return_value=True))
    def test_upgrade_available(self):
        '''
        Test whether or not an upgrade is available for a given package.

        :return:
        '''
        ref_out = get_test_data('zypper-available.txt')
        with patch('salt.modules.zypper.__zypper__', ZyppCallMock(return_value=get_test_data('zypper-available.txt'))):
            for pkg_name in ['emacs', 'python']:
                self.assertFalse(zypper.upgrade_available(pkg_name))
            self.assertTrue(zypper.upgrade_available('vim'))

    def test_list_pkgs(self):
        '''
        Test packages listing.

        :return:
        '''
        def _add_data(data, key, value):
            data[key] = value

        rpm_out = [
            'protobuf-java_|-2.6.1_|-3.1.develHead_|-',
            'yast2-ftp-server_|-3.1.8_|-8.1_|-',
            'jose4j_|-0.4.4_|-2.1.develHead_|-',
            'apache-commons-cli_|-1.2_|-1.233_|-',
            'jakarta-commons-discovery_|-0.4_|-129.686_|-',
            'susemanager-build-keys-web_|-12.0_|-5.1.develHead_|-',
        ]
        with patch.dict(zypper.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(rpm_out))}):
            with patch.dict(zypper.__salt__, {'pkg_resource.add_pkg': _add_data}):
                with patch.dict(zypper.__salt__, {'pkg_resource.sort_pkglist': MagicMock()}):
                    with patch.dict(zypper.__salt__, {'pkg_resource.stringify': MagicMock()}):
                        pkgs = zypper.list_pkgs()
                        for pkg_name, pkg_version in {
                            'jakarta-commons-discovery': '0.4-129.686',
                            'yast2-ftp-server': '3.1.8-8.1',
                            'protobuf-java': '2.6.1-3.1.develHead',
                            'susemanager-build-keys-web': '12.0-5.1.develHead',
                            'apache-commons-cli': '1.2-1.233',
                            'jose4j': '0.4.4-2.1.develHead'}.items():
                            self.assertTrue(pkgs.get(pkg_name))
                            self.assertEqual(pkgs[pkg_name], pkg_version)

    def test_remove_purge(self):
        '''
        Test package removal
        :return:
        '''
        class ListPackages(object):
            def __init__(self):
                self._packages = ['vim', 'pico']
                self._pkgs = {
                    'vim': '0.18.0',
                    'emacs': '24.0.1',
                    'pico': '0.1.1',
                }

            def __call__(self):
                pkgs = self._pkgs.copy()
                for target in self._packages:
                    if self._pkgs.get(target):
                        del self._pkgs[target]

                return pkgs

        parsed_targets = [{'vim': None, 'pico': None}, None]
        cmd_out = {
                'retcode': 0,
                'stdout': '',
                'stderr': ''
        }

        with patch.dict(zypper.__salt__, {'cmd.run_all': MagicMock(return_value=cmd_out)}):
            with patch.dict(zypper.__salt__, {'pkg_resource.parse_targets': MagicMock(return_value=parsed_targets)}):
                with patch.dict(zypper.__salt__, {'pkg_resource.stringify': MagicMock()}):
                    with patch('salt.modules.zypper.list_pkgs', ListPackages()):
                        diff = zypper.remove(name='vim,pico')
                        for pkg_name in ['vim', 'pico']:
                            self.assertTrue(diff.get(pkg_name))
                            self.assertTrue(diff[pkg_name]['old'])
                            self.assertFalse(diff[pkg_name]['new'])

    def test_repo_value_info(self):
        '''
        Tests if repo info is properly parsed.

        :return:
        '''
        repos_cfg = configparser.ConfigParser()
        for cfg in ['zypper-repo-1.cfg', 'zypper-repo-2.cfg']:
            repos_cfg.readfp(StringIO.StringIO(get_test_data(cfg)))

        for alias in repos_cfg.sections():
            r_info = zypper._get_repo_info(alias, repos_cfg=repos_cfg)
            self.assertEqual(type(r_info['type']), type(None))
            self.assertEqual(type(r_info['enabled']), bool)
            self.assertEqual(type(r_info['autorefresh']), bool)
            self.assertEqual(type(r_info['baseurl']), str)
            self.assertEqual(r_info['type'], None)
            self.assertEqual(r_info['enabled'], alias == 'SLE12-SP1-x86_64-Update')
            self.assertEqual(r_info['autorefresh'], alias == 'SLE12-SP1-x86_64-Update')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ZypperTestCase, needs_daemon=False)
