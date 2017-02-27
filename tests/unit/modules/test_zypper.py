# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    MagicMock,
    call,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
from salt.exceptions import CommandExecutionError
from salt.ext.six.moves import configparser
import salt.ext.six as six


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
zypper.__grains__ = dict()
zypper.__context__ = dict()
zypper.rpm = None


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZypperTestCase(TestCase):

    '''
    Test cases for salt.modules.zypper
    '''

    def setUp(self):
        self.new_repo_config = dict(
            name='mock-repo-name',
            url='http://repo.url/some/path'
        )
        side_effect = [
            Mock(**{'sections.return_value': []}),
            Mock(**{'sections.return_value': [self.new_repo_config['name']]})
        ]
        self.zypper_patcher_config = {
            '_get_configured_repos': Mock(side_effect=side_effect),
            '__zypper__': Mock(),
            '_get_repo_info': Mock(
                return_value={
                    'keeppackages': False,
                    'autorefresh': True,
                    'enabled': False,
                    'baseurl': self.new_repo_config['url'],
                    'alias': self.new_repo_config['name'],
                    'priority': 1,
                    'type': 'rpm-md'
                }
            ),
            'del_repo': Mock(),
            'mod_repo': Mock(wraps=zypper.mod_repo)
        }

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
                'productline': [None, None, None, None, None, None, 'sles'],
                'eol_t': [None, 0, 1509408000, 1522454400, 1522454400, 1730332800, 1730332800],
                'isbase': [False, False, False, False, False, False, True],
                'installed': [False, False, False, False, False, False, True],
                'registerrelease': [None, None, None, None, None, None, '123'],
            },
            'zypper-products-sle11sp3.xml': {
                'name': ['SUSE-Manager-Server', 'SUSE-Manager-Server', 'SUSE-Manager-Server-Broken-EOL',
                         'SUSE_SLES', 'SUSE_SLES', 'SUSE_SLES', 'SUSE_SLES-SP4-migration'],
                'vendor': 'SUSE LINUX Products GmbH, Nuernberg, Germany',
                'release': ['1.138', '1.2', '1.2', '1.2', '1.201', '1.201', '1.4'],
                'productline': [None, None, None, None, None, 'manager', 'manager'],
                'eol_t': [None, 0, 0, 0, 0, 0, 0],
                'isbase': [False, False, False, False, False, True, True],
                'installed': [False, False, False, False, False, True, True],
                'registerrelease': [None, None, None, None, None, None, "42"],
            }}.items():

            ref_out = {
                    'retcode': 0,
                    'stdout': get_test_data(filename)
            }

            with patch.dict(zypper.__salt__, {'cmd.run_all': MagicMock(return_value=ref_out)}):
                products = zypper.list_products()
                self.assertEqual(len(products), 7)
                self.assertIn(test_data['vendor'], [product['vendor'] for product in products])
                for kwd in ['name', 'isbase', 'installed', 'release', 'productline', 'eol_t', 'registerrelease']:
                    if six.PY3:
                        self.assertCountEqual(test_data[kwd], [prod.get(kwd) for prod in products])
                    else:
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

    def test_info_installed_with_non_ascii_char(self):
        '''
        Test the return information of the named package(s), installed on the system whith non-ascii chars

        :return:
        '''
        run_out = {'vīrgô': {'description': 'vīrgô d€šçripţiǫñ'}}
        with patch.dict(zypper.__salt__, {'lowpkg.info': MagicMock(return_value=run_out)}):
            installed = zypper.info_installed()
            self.assertEqual(installed['vīrgô']['description'], 'vīrgô d€šçripţiǫñ')

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
    @patch('salt.modules.zypper._systemd_scope', MagicMock(return_value=False))
    @patch.dict('salt.modules.zypper.__grains__', {'osrelease_info': [12, 1]})
    def test_upgrade_success(self):
        '''
        Test system upgrade and dist-upgrade success.

        :return:
        '''
        with patch('salt.modules.zypper.__zypper__.noraise.call', MagicMock()) as zypper_mock:
            with patch('salt.modules.zypper.list_pkgs', MagicMock(side_effect=[{"vim": "1.1"}, {"vim": "1.2"}])):
                ret = zypper.upgrade()
                self.assertDictEqual(ret, {"vim": {"old": "1.1", "new": "1.2"}})
                zypper_mock.assert_any_call('update', '--auto-agree-with-licenses')

            with patch('salt.modules.zypper.list_pkgs', MagicMock(side_effect=[{"vim": "1.1"}, {"vim": "1.2"}])):
                ret = zypper.upgrade(dist_upgrade=True)
                self.assertDictEqual(ret, {"vim": {"old": "1.1", "new": "1.2"}})
                zypper_mock.assert_any_call('dist-upgrade', '--auto-agree-with-licenses')

            with patch('salt.modules.zypper.list_pkgs', MagicMock(side_effect=[{"vim": "1.1"}, {"vim": "1.1"}])):
                ret = zypper.upgrade(dist_upgrade=True, dryrun=True)
                zypper_mock.assert_any_call('dist-upgrade', '--auto-agree-with-licenses', '--dry-run')
                zypper_mock.assert_any_call('dist-upgrade', '--auto-agree-with-licenses', '--dry-run', '--debug-solver')

            with patch('salt.modules.zypper.list_pkgs', MagicMock(side_effect=[{"vim": "1.1"}, {"vim": "1.1"}])):
                ret = zypper.upgrade(dist_upgrade=True, dryrun=True, fromrepo=["Dummy", "Dummy2"], novendorchange=True)
                zypper_mock.assert_any_call('dist-upgrade', '--auto-agree-with-licenses', '--dry-run', '--from', "Dummy", '--from', 'Dummy2', '--no-allow-vendor-change')
                zypper_mock.assert_any_call('dist-upgrade', '--auto-agree-with-licenses', '--dry-run', '--from', "Dummy", '--from', 'Dummy2', '--no-allow-vendor-change', '--debug-solver')

            with patch('salt.modules.zypper.list_pkgs', MagicMock(side_effect=[{"vim": "1.1"}, {"vim": "1.2"}])):
                ret = zypper.upgrade(dist_upgrade=True, fromrepo=["Dummy", "Dummy2"], novendorchange=True)
                self.assertDictEqual(ret, {"vim": {"old": "1.1", "new": "1.2"}})
                zypper_mock.assert_any_call('dist-upgrade', '--auto-agree-with-licenses', '--from', "Dummy", '--from', 'Dummy2', '--no-allow-vendor-change')

    @patch('salt.modules.zypper.refresh_db', MagicMock(return_value=True))
    @patch('salt.modules.zypper._systemd_scope', MagicMock(return_value=False))
    @patch.dict('salt.modules.zypper.__grains__', {'osrelease_info': [12, 1]})
    def test_upgrade_failure(self):
        '''
        Test system upgrade failure.

        :return:
        '''
        zypper_out = '''
Loading repository data...
Reading installed packages...
Computing distribution upgrade...
Use 'zypper repos' to get the list of defined repositories.
Repository 'DUMMY' not found by its alias, number, or URI.
'''

        class FailingZypperDummy(object):
            def __init__(self):
                self.stdout = zypper_out
                self.stderr = ""
                self.pid = 1234
                self.exit_code = 555
                self.noraise = MagicMock()
                self.SUCCESS_EXIT_CODES = [0]

            def __call__(self, *args, **kwargs):
                return self

        with patch('salt.modules.zypper.__zypper__', FailingZypperDummy()) as zypper_mock:
            zypper_mock.noraise.call = MagicMock()
            with patch('salt.modules.zypper.list_pkgs', MagicMock(side_effect=[{"vim": "1.1"}, {"vim": "1.1"}])):
                with self.assertRaises(CommandExecutionError) as cmd_exc:
                    ret = zypper.upgrade(dist_upgrade=True, fromrepo=["DUMMY"])
                self.assertEqual(cmd_exc.exception.info['changes'], {})
                self.assertEqual(cmd_exc.exception.info['result']['stdout'], zypper_out)
                zypper_mock.noraise.call.assert_called_with('dist-upgrade', '--auto-agree-with-licenses', '--from', 'DUMMY')

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

    def test_download(self):
        '''
        Test package download
        :return:
        '''
        download_out = {
            'stdout': get_test_data('zypper-download.xml'),
            'stderr': None,
            'retcode': 0
        }

        test_out = {
            'nmap': {
                'path': u'/var/cache/zypp/packages/SLE-12-x86_64-Pool/x86_64/nmap-6.46-1.72.x86_64.rpm',
                'repository-alias': u'SLE-12-x86_64-Pool',
                'repository-name': u'SLE-12-x86_64-Pool'
            }
        }

        with patch.dict(zypper.__salt__, {'cmd.run_all': MagicMock(return_value=download_out)}):
            with patch.dict(zypper.__salt__, {'lowpkg.checksum': MagicMock(return_value=True)}):
                self.assertEqual(zypper.download("nmap"), test_out)
                test_out['_error'] = "The following package(s) failed to download: foo"
                self.assertEqual(zypper.download("nmap", "foo"), test_out)

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

        # If config.get starts being used elsewhere, we'll need to write a
        # side_effect function.
        patches = {
            'cmd.run_all': MagicMock(return_value=cmd_out),
            'pkg_resource.parse_targets': MagicMock(return_value=parsed_targets),
            'pkg_resource.stringify': MagicMock(),
            'config.get': MagicMock(return_value=True)
        }

        with patch.dict(zypper.__salt__, patches):
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
            repos_cfg.readfp(six.moves.StringIO(get_test_data(cfg)))

        for alias in repos_cfg.sections():
            r_info = zypper._get_repo_info(alias, repos_cfg=repos_cfg)
            self.assertEqual(type(r_info['type']), type(None))
            self.assertEqual(type(r_info['enabled']), bool)
            self.assertEqual(type(r_info['autorefresh']), bool)
            self.assertEqual(type(r_info['baseurl']), str)
            self.assertEqual(r_info['type'], None)
            self.assertEqual(r_info['enabled'], alias == 'SLE12-SP1-x86_64-Update')
            self.assertEqual(r_info['autorefresh'], alias == 'SLE12-SP1-x86_64-Update')

    def test_repo_add_nomod_noref(self):
        '''
        Test mod_repo adds the new repo and nothing else

        :return:
        '''
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        with zypper_patcher:
            zypper.mod_repo(name, **{'url': url})
            self.assertEqual(
                zypper.__zypper__.xml.call.call_args_list,
                [call('ar', url, name)]
            )
            self.assertTrue(zypper.__zypper__.refreshable.xml.call.call_count == 0)

    def test_repo_noadd_nomod_noref(self):
        '''
        Test mod_repo detects the repo already exists,
        no modification was requested and no refresh requested either

        :return:
        '''
        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        self.zypper_patcher_config['_get_configured_repos'] = Mock(
            **{'return_value.sections.return_value': [name]}
        )
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        with zypper_patcher:
            out = zypper.mod_repo(name, alias='new-alias')
            self.assertEqual(
                out['comment'],
                'Specified arguments did not result in modification of repo')
            self.assertTrue(zypper.__zypper__.xml.call.call_count == 0)
            self.assertTrue(zypper.__zypper__.refreshable.xml.call.call_count == 0)

    def test_repo_noadd_modbaseurl_ref(self):
        '''
        Test mod_repo detects the repo already exists,
        no modification was requested and no refresh requested either

        :return:
        '''
        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        self.zypper_patcher_config['_get_configured_repos'] = Mock(
            **{'return_value.sections.side_effect': [[name], [], [], [name]]}
        )
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        with zypper_patcher:
            params = {'baseurl': url + "-changed", 'enabled': False}
            zypper.mod_repo(name, **params)
            expected_params = {
                'alias': 'mock-repo-name',
                'autorefresh': True,
                'baseurl': 'http://repo.url/some/path-changed',
                'enabled': False,
                'priority': 1,
                'cache': False,
                'keeppackages': False,
                'type': 'rpm-md'}
            self.assertTrue(zypper.mod_repo.call_count == 2)
            self.assertTrue(zypper.mod_repo.mock_calls[1] == call(name, **expected_params))

    def test_repo_add_mod_noref(self):
        '''
        Test mod_repo adds the new repo and call modify to update autorefresh

        :return:
        '''
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        with zypper_patcher:
            zypper.mod_repo(name, **{'url': url, 'refresh': True})
            self.assertEqual(
                zypper.__zypper__.xml.call.call_args_list,
                [call('ar', url, name)]
            )
            zypper.__zypper__.refreshable.xml.call.assert_called_once_with(
                'mr', '--refresh', name
            )

    def test_repo_noadd_mod_noref(self):
        '''
        Test mod_repo detects the repository exists,
        calls modify to update 'autorefresh' but does not call refresh

        :return:
        '''
        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        self.zypper_patcher_config['_get_configured_repos'] = Mock(
            **{'return_value.sections.return_value': [name]})
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)
        with zypper_patcher:
            zypper.mod_repo(name, **{'url': url, 'refresh': True})
            self.assertTrue(zypper.__zypper__.xml.call.call_count == 0)
            zypper.__zypper__.refreshable.xml.call.assert_called_once_with(
                'mr', '--refresh', name
            )

    def test_repo_add_nomod_ref(self):
        '''
        Test mod_repo adds the new repo and refreshes the repo with
            `zypper --gpg-auto-import-keys refresh <repo-name>`

        :return:
        '''
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        with zypper_patcher:
            zypper.mod_repo(name, **{'url': url, 'gpgautoimport': True})
            self.assertEqual(
                zypper.__zypper__.xml.call.call_args_list,
                [
                    call('ar', url, name),
                    call('--gpg-auto-import-keys', 'refresh', name)
                ]
            )
            self.assertTrue(zypper.__zypper__.refreshable.xml.call.call_count == 0)

    def test_repo_noadd_nomod_ref(self):
        '''
        Test mod_repo detects the repo already exists,
        has nothing to modify and refreshes the repo with
            `zypper --gpg-auto-import-keys refresh <repo-name>`

        :return:
        '''
        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        self.zypper_patcher_config['_get_configured_repos'] = Mock(
            **{'return_value.sections.return_value': [name]}
        )
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        with zypper_patcher:
            zypper.mod_repo(name, **{'url': url, 'gpgautoimport': True})
            self.assertEqual(
                zypper.__zypper__.xml.call.call_args_list,
                [call('--gpg-auto-import-keys', 'refresh', name)]
            )
            self.assertTrue(zypper.__zypper__.refreshable.xml.call.call_count == 0)

    def test_repo_add_mod_ref(self):
        '''
        Test mod_repo adds the new repo,
        calls modify to update 'autorefresh' and refreshes the repo with
            `zypper --gpg-auto-import-keys refresh <repo-name>`

        :return:
        '''
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        with zypper_patcher:
            zypper.mod_repo(
                name,
                **{'url': url, 'refresh': True, 'gpgautoimport': True}
            )
            self.assertEqual(
                zypper.__zypper__.xml.call.call_args_list,
                [
                    call('ar', url, name),
                    call('--gpg-auto-import-keys', 'refresh', name)
                ]
            )
            zypper.__zypper__.refreshable.xml.call.assert_called_once_with(
                '--gpg-auto-import-keys', 'mr', '--refresh', name
            )

    def test_repo_noadd_mod_ref(self):
        '''
        Test mod_repo detects the repo already exists,
        calls modify to update 'autorefresh' and refreshes the repo with
            `zypper --gpg-auto-import-keys refresh <repo-name>`

        :return:
        '''
        url = self.new_repo_config['url']
        name = self.new_repo_config['name']
        self.zypper_patcher_config['_get_configured_repos'] = Mock(
            **{'return_value.sections.return_value': [name]}
        )
        zypper_patcher = patch.multiple(
            'salt.modules.zypper', **self.zypper_patcher_config)

        with zypper_patcher:
            zypper.mod_repo(
                name,
                **{'url': url, 'refresh': True, 'gpgautoimport': True}
            )
            self.assertEqual(
                zypper.__zypper__.xml.call.call_args_list,
                [call('--gpg-auto-import-keys', 'refresh', name)]
            )
            zypper.__zypper__.refreshable.xml.call.assert_called_once_with(
                '--gpg-auto-import-keys', 'mr', '--refresh', name
            )
