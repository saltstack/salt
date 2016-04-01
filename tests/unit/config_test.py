# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.config_test
    ~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import logging
import os
import shutil
import tempfile
from contextlib import contextmanager

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.mock import MagicMock, patch
from salttesting.helpers import ensure_in_syspath, TestsLoggingHandler
from salt.exceptions import CommandExecutionError

ensure_in_syspath('../')

# Import salt libs
import salt.minion
import salt.utils
import salt.utils.network
import integration
from salt import config as sconfig
from salt.exceptions import SaltCloudConfigError

# Import Third-Party Libs
import yaml

log = logging.getLogger(__name__)

# mock hostname should be more complex than the systems FQDN
MOCK_HOSTNAME = 'very.long.complex.fqdn.that.is.crazy.extra.long.example.com'

MOCK_ETC_HOSTS = (
    '##\n'
    '# Host Database\n'
    '#\n'
    '# localhost is used to configure the loopback interface\n'
    '# when the system is booting.  Do not change this entry.\n'
    '##\n'
    '\n'  # This empty line MUST STAY HERE, it factors into the tests
    '127.0.0.1      localhost   ' + MOCK_HOSTNAME + '\n'
    '10.0.0.100     ' + MOCK_HOSTNAME + '\n'
    '200.200.200.2  other.host.alias.com\n'
    '::1            ip6-localhost ip6-loopback\n'
    'fe00::0        ip6-localnet\n'
    'ff00::0        ip6-mcastprefix\n'
)
MOCK_ETC_HOSTNAME = '{0}\n'.format(MOCK_HOSTNAME)
PATH = 'path/to/some/cloud/conf/file'
DEFAULT = {'default_include': PATH}


def _unhandled_mock_read(filename):
    '''
    Raise an error because we should not be calling salt.utils.fopen()
    '''
    raise CommandExecutionError('Unhandled mock read for {0}'.format(filename))


@contextmanager
def _fopen_side_effect_etc_hostname(filename):
    '''
    Mock reading from /etc/hostname
    '''
    log.debug('Mock-reading {0}'.format(filename))
    if filename == '/etc/hostname':
        mock_open = MagicMock()
        mock_open.read.return_value = MOCK_ETC_HOSTNAME
        yield mock_open
    elif filename == '/etc/hosts':
        raise IOError(2, "No such file or directory: '{0}'".format(filename))
    else:
        _unhandled_mock_read(filename)


@contextmanager
def _fopen_side_effect_etc_hosts(filename):
    '''
    Mock /etc/hostname not existing, and falling back to reading /etc/hosts
    '''
    log.debug('Mock-reading {0}'.format(filename))
    if filename == '/etc/hostname':
        raise IOError(2, "No such file or directory: '{0}'".format(filename))
    elif filename == '/etc/hosts':
        mock_open = MagicMock()
        mock_open.__iter__.return_value = MOCK_ETC_HOSTS.splitlines()
        yield mock_open
    else:
        _unhandled_mock_read(filename)


class ConfigTestCase(TestCase, integration.AdaptedConfigurationTestCaseMixIn):
    def test_proper_path_joining(self):
        fpath = tempfile.mktemp()
        try:
            salt.utils.fopen(fpath, 'w').write(
                "root_dir: /\n"
                "key_logfile: key\n"
            )
            config = sconfig.master_config(fpath)
            # os.path.join behavior
            self.assertEqual(config['key_logfile'], os.path.join('/', 'key'))
            # os.sep.join behavior
            self.assertNotEqual(config['key_logfile'], '//key')
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)

    def test_common_prefix_stripping(self):
        tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_load_master_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_MASTER_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file.
            config = sconfig.master_config('/etc/salt/master')
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, i.e., the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_MASTER_CONFIG'] = env_fpath
            config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
            os.environ.clear()
            os.environ.update(original_environ)

        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_load_minion_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_MINION_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file
            config = sconfig.minion_config('/etc/salt/minion')
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, i.e., the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_MINION_CONFIG'] = env_fpath
            config = sconfig.minion_config(fpath)
            self.assertEqual(config['log_file'], fpath)
            os.environ.clear()
            os.environ.update(original_environ)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_load_client_config_from_environ_var(self):
        original_environ = os.environ.copy()
        try:
            tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)

            # Let's populate a master configuration file which should not get
            # picked up since the client configuration tries to load the master
            # configuration settings using the provided client configuration
            # file
            master_config = os.path.join(env_root_dir, 'master')
            salt.utils.fopen(master_config, 'w').write(
                'blah: true\n'
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, master_config)
            )
            os.environ['SALT_MASTER_CONFIG'] = master_config

            # Now the client configuration file
            env_fpath = os.path.join(env_root_dir, 'config-env')
            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_CLIENT_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file
            config = sconfig.client_config(os.path.expanduser('~/.salt'))
            self.assertEqual(config['log_file'], env_fpath)
            self.assertTrue('blah' not in config)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, i.e., the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_MASTER_CONFIG'] = env_fpath
            config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
            os.environ.clear()
            os.environ.update(original_environ)

        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_issue_5970_minion_confd_inclusion(self):
        try:
            tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
            minion_config = os.path.join(tempdir, 'minion')
            minion_confd = os.path.join(tempdir, 'minion.d')
            os.makedirs(minion_confd)

            # Let's populate a minion configuration file with some basic
            # settings
            salt.utils.fopen(minion_config, 'w').write(
                'blah: false\n'
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(tempdir, minion_config)
            )

            # Now, let's populate an extra configuration file under minion.d
            # Notice that above we've set blah as False and below as True.
            # Since the minion.d files are loaded after the main configuration
            # file so overrides can happen, the final value of blah should be
            # True.
            extra_config = os.path.join(minion_confd, 'extra.conf')
            salt.utils.fopen(extra_config, 'w').write(
                'blah: true\n'
            )

            # Let's load the configuration
            config = sconfig.minion_config(minion_config)

            self.assertEqual(config['log_file'], minion_config)
            # As proven by the assertion below, blah is True
            self.assertTrue(config['blah'])
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_master_confd_inclusion(self):
        try:
            tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
            master_config = os.path.join(tempdir, 'master')
            master_confd = os.path.join(tempdir, 'master.d')
            os.makedirs(master_confd)

            # Let's populate a master configuration file with some basic
            # settings
            salt.utils.fopen(master_config, 'w').write(
                'blah: false\n'
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(tempdir, master_config)
            )

            # Now, let's populate an extra configuration file under master.d
            # Notice that above we've set blah as False and below as True.
            # Since the master.d files are loaded after the main configuration
            # file so overrides can happen, the final value of blah should be
            # True.
            extra_config = os.path.join(master_confd, 'extra.conf')
            salt.utils.fopen(extra_config, 'w').write(
                'blah: true\n'
            )

            # Let's load the configuration
            config = sconfig.master_config(master_config)

            self.assertEqual(config['log_file'], master_config)
            # As proven by the assertion below, blah is True
            self.assertTrue(config['blah'])
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_syndic_config(self):
        syndic_conf_path = self.get_config_file_path('syndic')
        minion_conf_path = self.get_config_file_path('minion')
        syndic_opts = sconfig.syndic_config(
            syndic_conf_path, minion_conf_path
        )
        syndic_opts.update(salt.minion.resolve_dns(syndic_opts))
        root_dir = syndic_opts['root_dir']
        # id & pki dir are shared & so configured on the minion side
        self.assertEqual(syndic_opts['id'], 'minion')
        self.assertEqual(syndic_opts['pki_dir'], os.path.join(root_dir, 'pki'))
        # the rest is configured master side
        self.assertEqual(syndic_opts['master_uri'], 'tcp://127.0.0.1:54506')
        self.assertEqual(syndic_opts['master_port'], 54506)
        self.assertEqual(syndic_opts['master_ip'], '127.0.0.1')
        self.assertEqual(syndic_opts['master'], 'localhost')
        self.assertEqual(syndic_opts['sock_dir'], os.path.join(root_dir, 'minion_sock'))
        self.assertEqual(syndic_opts['cachedir'], os.path.join(root_dir, 'cache'))
        self.assertEqual(syndic_opts['log_file'], os.path.join(root_dir, 'var/log/salt/syndic'))
        self.assertEqual(syndic_opts['pidfile'], os.path.join(root_dir, 'var/run/salt-syndic.pid'))
        # Show that the options of localclient that repub to local master
        # are not merged with syndic ones
        self.assertEqual(syndic_opts['_master_conf_file'], minion_conf_path)
        self.assertEqual(syndic_opts['_minion_conf_file'], syndic_conf_path)

    def test_issue_6714_parsing_errors_logged(self):
        try:
            tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
            test_config = os.path.join(tempdir, 'config')

            # Let's populate a master configuration file with some basic
            # settings
            salt.utils.fopen(test_config, 'w').write(
                'root_dir: {0}\n'
                'log_file: {0}/foo.log\n'.format(tempdir) +
                '\n\n\n'
                'blah:false\n'
            )

            with TestsLoggingHandler() as handler:
                # Let's load the configuration
                config = sconfig.master_config(test_config)
                for message in handler.messages:
                    if message.startswith('ERROR:Error parsing configuration'):
                        break
                else:
                    raise AssertionError(
                        'No parsing error message was logged'
                    )
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    @patch('salt.utils.network.get_fqhostname', MagicMock(return_value='localhost'))
    def test_get_id_etc_hostname(self):
        '''
        Test calling salt.config.get_id() and falling back to looking at
        /etc/hostname.
        '''
        with patch('salt.utils.fopen', _fopen_side_effect_etc_hostname):
            self.assertEqual(
                    sconfig.get_id({'root_dir': None, 'minion_id_caching': False}), (MOCK_HOSTNAME, False)
            )

    @patch('salt.utils.network.get_fqhostname', MagicMock(return_value='localhost'))
    def test_get_id_etc_hosts(self):
        '''
        Test calling salt.config.get_id() and falling back all the way to
        looking up data from /etc/hosts.
        '''
        with patch('salt.utils.fopen', _fopen_side_effect_etc_hosts):
            self.assertEqual(
                    sconfig.get_id({'root_dir': None, 'minion_id_caching': False}), (MOCK_HOSTNAME, False)
            )

# <---- Salt Cloud Configuration Tests ---------------------------------------------

    # cloud_config tests

    @patch('salt.config.load_config', MagicMock(return_value={}))
    def test_cloud_config_double_master_path(self):
        '''
        Tests passing in master_config_path and master_config kwargs.
        '''
        self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                          master_config_path='foo', master_config='bar')

    @patch('salt.config.load_config', MagicMock(return_value={}))
    def test_cloud_config_double_providers_path(self):
        '''
        Tests passing in providers_config_path and providers_config kwargs.
        '''
        self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                          providers_config_path='foo', providers_config='bar')

    @patch('salt.config.load_config', MagicMock(return_value={}))
    def test_cloud_config_double_profiles_path(self):
        '''
        Tests passing in profiles_config_path and profiles_config kwargs.
        '''
        self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                          profiles_config_path='foo', profiles_config='bar')

    @patch('salt.config.load_config', MagicMock(return_value={}))
    @patch('salt.config.apply_cloud_config',
           MagicMock(return_value={'providers': 'foo'}))
    def test_cloud_config_providers_in_opts(self):
        '''
        Tests mixing old cloud providers with pre-configured providers configurations
        using the providers_config kwarg
        '''
        self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                          providers_config='bar')

    @patch('salt.config.load_config', MagicMock(return_value={}))
    @patch('salt.config.apply_cloud_config',
           MagicMock(return_value={'providers': 'foo'}))
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_cloud_config_providers_in_opts_path(self):
        '''
        Tests mixing old cloud providers with pre-configured providers configurations
        using the providers_config_path kwarg
        '''
        self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                          providers_config_path='bar')

    @patch('os.path.isdir', MagicMock(return_value=True))
    def test_cloud_config_deploy_scripts_search_path(self):
        '''
        Tests the contents of the 'deploy_scripts_search_path' tuple to ensure that
        the correct deploy search paths are present.

        There should be two search paths reported in the tuple: ``/etc/salt/cloud.deploy.d``
        and ``<path-to-salt-install>/salt/cloud/deploy``. The first element is usually
        ``/etc/salt/cloud.deploy.d``, but sometimes is can be something like
        ``/etc/local/salt/cloud.deploy.d``, so we'll only test against the last part of
        the path.
        '''
        search_paths = sconfig.cloud_config('/etc/salt/cloud').get('deploy_scripts_search_path')
        etc_deploy_path = '/salt/cloud.deploy.d'
        deploy_path = '/salt/cloud/deploy'

        # Check cloud.deploy.d path is the first element in the search_paths tuple
        self.assertTrue(search_paths[0].endswith(etc_deploy_path))

        # Check the second element in the search_paths tuple
        self.assertTrue(search_paths[1].endswith(deploy_path))

    # apply_cloud_config tests

    def test_apply_cloud_config_no_provider_detail_list(self):
        '''
        Tests when the provider is not contained in a list of details
        '''
        overrides = {'providers': {'foo': [{'bar': 'baz'}]}}
        self.assertRaises(SaltCloudConfigError, sconfig.apply_cloud_config,
                          overrides, defaults=DEFAULT)

    def test_apply_cloud_config_no_provider_detail_dict(self):
        '''
        Tests when the provider is not contained in the details dictionary
        '''
        overrides = {'providers': {'foo': {'bar': 'baz'}}}
        self.assertRaises(SaltCloudConfigError, sconfig.apply_cloud_config,
                          overrides, defaults=DEFAULT)

    @patch('salt.config.old_to_new',
           MagicMock(return_value={'default_include': 'path/to/some/cloud/conf/file',
                                   'providers': {'foo': {'bar': {
                                       'driver': 'foo:bar'}}}}))
    def test_apply_cloud_config_success_list(self):
        '''
        Tests success when valid data is passed into the function as a list
        '''
        overrides = {'providers': {'foo': [{'driver': 'bar'}]}}
        ret = {'default_include': 'path/to/some/cloud/conf/file',
               'providers': {'foo': {'bar': {'driver': 'foo:bar'}}}}
        self.assertEqual(sconfig.apply_cloud_config(overrides, defaults=DEFAULT), ret)

    @patch('salt.config.old_to_new',
           MagicMock(return_value={'default_include': 'path/to/some/cloud/conf/file',
                                   'providers': {'foo': {'bar': {
                                       'driver': 'foo:bar'}}}}))
    def test_apply_cloud_config_success_dict(self):
        '''
        Tests success when valid data is passed into function as a dictionary
        '''
        overrides = {'providers': {'foo': {'driver': 'bar'}}}
        ret = {'default_include': 'path/to/some/cloud/conf/file',
               'providers': {'foo': {'bar': {'driver': 'foo:bar'}}}}
        self.assertEqual(sconfig.apply_cloud_config(overrides, defaults=DEFAULT), ret)

    # apply_vm_profiles_config tests

    def test_apply_vm_profiles_config_bad_profile_format(self):
        '''
        Tests passing in a bad profile format in overrides
        '''
        overrides = {'foo': 'bar', 'conf_file': PATH}
        self.assertRaises(SaltCloudConfigError, sconfig.apply_vm_profiles_config,
                          PATH, overrides, defaults=DEFAULT)

    def test_apply_vm_profiles_config_success(self):
        '''
        Tests passing in valid provider and profile config files successfully
        '''
        providers = {'test-provider':
                         {'digital_ocean':
                              {'driver': 'digital_ocean', 'profiles': {}}}}
        overrides = {'test-profile':
                         {'provider': 'test-provider',
                          'image': 'Ubuntu 12.10 x64',
                          'size': '512MB'},
                     'conf_file': PATH}
        ret = {'test-profile':
                   {'profile': 'test-profile',
                    'provider': 'test-provider:digital_ocean',
                    'image': 'Ubuntu 12.10 x64',
                    'size': '512MB'}}
        self.assertEqual(sconfig.apply_vm_profiles_config(providers,
                                                          overrides,
                                                          defaults=DEFAULT), ret)

    def test_apply_vm_profiles_config_extend_success(self):
        '''
        Tests profile extends functionality with valid provider and profile configs
        '''
        providers = {'test-config': {'ec2': {'profiles': {}, 'driver': 'ec2'}}}
        overrides = {'Amazon': {'image': 'test-image-1',
                                'extends': 'dev-instances'},
                     'Fedora': {'image': 'test-image-2',
                                'extends': 'dev-instances'},
                     'conf_file': PATH,
                     'dev-instances': {'ssh_username': 'test_user',
                                       'provider': 'test-config'}}
        ret = {'Amazon': {'profile': 'Amazon',
                          'ssh_username': 'test_user',
                          'image': 'test-image-1',
                          'provider': 'test-config:ec2'},
               'Fedora': {'profile': 'Fedora',
                          'ssh_username': 'test_user',
                          'image': 'test-image-2',
                          'provider': 'test-config:ec2'},
               'dev-instances': {'profile': 'dev-instances',
                                 'ssh_username': 'test_user',
                                 'provider': 'test-config:ec2'}}
        self.assertEqual(sconfig.apply_vm_profiles_config(providers,
                                                          overrides,
                                                          defaults=DEFAULT), ret)

    # apply_cloud_providers_config tests

    def test_apply_cloud_providers_config_same_providers(self):
        '''
        Tests when two providers are given with the same provider name
        '''
        overrides = {'my-dev-envs':
                         [{'id': 'ABCDEFGHIJKLMNOP',
                           'key': 'supersecretkeysupersecretkey',
                           'driver': 'ec2'},
                          {'apikey': 'abcdefghijklmnopqrstuvwxyz',
                           'password': 'supersecret',
                           'driver': 'ec2'}],
                     'conf_file': PATH}
        self.assertRaises(SaltCloudConfigError,
                          sconfig.apply_cloud_providers_config,
                          overrides,
                          DEFAULT)

    def test_apply_cloud_providers_config_extend(self):
        '''
        Tests the successful extension of a cloud provider
        '''
        overrides = {'my-production-envs':
                         [{'extends': 'my-dev-envs:ec2',
                           'location': 'us-east-1',
                           'user': 'ec2-user@mycorp.com'
                          }],
                     'my-dev-envs':
                         [{'id': 'ABCDEFGHIJKLMNOP',
                           'user': 'user@mycorp.com',
                           'location': 'ap-southeast-1',
                           'key': 'supersecretkeysupersecretkey',
                           'driver': 'ec2'
                          },
                          {'apikey': 'abcdefghijklmnopqrstuvwxyz',
                           'password': 'supersecret',
                           'driver': 'linode'
                          }],
                     'conf_file': PATH}
        ret = {'my-production-envs':
                   {'ec2':
                        {'profiles': {},
                         'location': 'us-east-1',
                         'key': 'supersecretkeysupersecretkey',
                         'driver': 'ec2',
                         'id': 'ABCDEFGHIJKLMNOP',
                         'user': 'ec2-user@mycorp.com'}},
               'my-dev-envs':
                   {'linode':
                        {'apikey': 'abcdefghijklmnopqrstuvwxyz',
                         'password': 'supersecret',
                         'profiles': {},
                         'driver': 'linode'},
                    'ec2':
                        {'profiles': {},
                         'location': 'ap-southeast-1',
                         'key': 'supersecretkeysupersecretkey',
                         'driver': 'ec2',
                         'id': 'ABCDEFGHIJKLMNOP',
                         'user': 'user@mycorp.com'}}}
        self.assertEqual(ret,
                         sconfig.apply_cloud_providers_config(
                             overrides,
                             defaults=DEFAULT))

    def test_apply_cloud_providers_config_extend_multiple(self):
        '''
        Tests the successful extension of two cloud providers
        '''
        overrides = {'my-production-envs':
                         [{'extends': 'my-dev-envs:ec2',
                           'location': 'us-east-1',
                           'user': 'ec2-user@mycorp.com'},
                          {'password': 'new-password',
                           'extends': 'my-dev-envs:linode',
                           'location': 'Salt Lake City'
                          }],
                     'my-dev-envs':
                         [{'id': 'ABCDEFGHIJKLMNOP',
                           'user': 'user@mycorp.com',
                           'location': 'ap-southeast-1',
                           'key': 'supersecretkeysupersecretkey',
                           'driver': 'ec2'},
                          {'apikey': 'abcdefghijklmnopqrstuvwxyz',
                           'password': 'supersecret',
                           'driver': 'linode'}],
                     'conf_file': PATH}
        ret = {'my-production-envs':
                   {'linode':
                        {'apikey': 'abcdefghijklmnopqrstuvwxyz',
                         'profiles': {},
                         'location': 'Salt Lake City',
                         'driver': 'linode',
                         'password': 'new-password'},
                    'ec2':
                        {'user': 'ec2-user@mycorp.com',
                         'key': 'supersecretkeysupersecretkey',
                         'driver': 'ec2',
                         'id': 'ABCDEFGHIJKLMNOP',
                         'profiles': {},
                         'location': 'us-east-1'}},
               'my-dev-envs':
                   {'linode':
                        {'apikey': 'abcdefghijklmnopqrstuvwxyz',
                         'password': 'supersecret',
                         'profiles': {},
                         'driver': 'linode'},
                    'ec2':
                        {'profiles': {},
                         'user': 'user@mycorp.com',
                         'key': 'supersecretkeysupersecretkey',
                         'driver': 'ec2',
                         'id': 'ABCDEFGHIJKLMNOP',
                         'location': 'ap-southeast-1'}}}
        self.assertEqual(ret, sconfig.apply_cloud_providers_config(
            overrides,
            defaults=DEFAULT))

    def test_apply_cloud_providers_config_extends_bad_alias(self):
        '''
        Tests when the extension contains an alias not found in providers list
        '''
        overrides = {'my-production-envs':
                         [{'extends': 'test-alias:ec2',
                           'location': 'us-east-1',
                           'user': 'ec2-user@mycorp.com'}],
                     'my-dev-envs':
                         [{'id': 'ABCDEFGHIJKLMNOP',
                           'user': 'user@mycorp.com',
                           'location': 'ap-southeast-1',
                           'key': 'supersecretkeysupersecretkey',
                           'driver': 'ec2'}],
                     'conf_file': PATH}
        self.assertRaises(SaltCloudConfigError,
                          sconfig.apply_cloud_providers_config,
                          overrides,
                          DEFAULT)

    def test_apply_cloud_providers_config_extends_bad_provider(self):
        '''
        Tests when the extension contains a provider not found in providers list
        '''
        overrides = {'my-production-envs':
                         [{'extends': 'my-dev-envs:linode',
                           'location': 'us-east-1',
                           'user': 'ec2-user@mycorp.com'}],
                     'my-dev-envs':
                         [{'id': 'ABCDEFGHIJKLMNOP',
                           'user': 'user@mycorp.com',
                           'location': 'ap-southeast-1',
                           'key': 'supersecretkeysupersecretkey',
                           'driver': 'ec2'}],
                     'conf_file': PATH}
        self.assertRaises(SaltCloudConfigError,
                          sconfig.apply_cloud_providers_config,
                          overrides,
                          DEFAULT)

    def test_apply_cloud_providers_config_extends_no_provider(self):
        '''
        Tests when no provider is supplied in the extends statement
        '''
        overrides = {'my-production-envs':
                         [{'extends': 'my-dev-envs',
                           'location': 'us-east-1',
                           'user': 'ec2-user@mycorp.com'}],
                     'my-dev-envs':
                         [{'id': 'ABCDEFGHIJKLMNOP',
                           'user': 'user@mycorp.com',
                           'location': 'ap-southeast-1',
                           'key': 'supersecretkeysupersecretkey',
                           'driver': 'linode'}],
                     'conf_file': PATH}
        self.assertRaises(SaltCloudConfigError,
                          sconfig.apply_cloud_providers_config,
                          overrides,
                          DEFAULT)

    def test_apply_cloud_providers_extends_not_in_providers(self):
        '''
        Tests when extends is not in the list of providers
        '''
        overrides = {'my-production-envs':
                         [{'extends': 'my-dev-envs ec2',
                           'location': 'us-east-1',
                           'user': 'ec2-user@mycorp.com'}],
                     'my-dev-envs':
                         [{'id': 'ABCDEFGHIJKLMNOP',
                           'user': 'user@mycorp.com',
                           'location': 'ap-southeast-1',
                           'key': 'supersecretkeysupersecretkey',
                           'driver': 'linode'}],
                     'conf_file': PATH}
        self.assertRaises(SaltCloudConfigError,
                          sconfig.apply_cloud_providers_config,
                          overrides,
                          DEFAULT)

    # is_provider_configured tests

    def test_is_provider_configured_no_alias(self):
        '''
        Tests when provider alias is not in opts
        '''
        opts = {'providers': 'test'}
        provider = 'foo:bar'
        self.assertFalse(sconfig.is_provider_configured(opts, provider))

    def test_is_provider_configured_no_driver(self):
        '''
        Tests when provider driver is not in opts
        '''
        opts = {'providers': {'foo': 'baz'}}
        provider = 'foo:bar'
        self.assertFalse(sconfig.is_provider_configured(opts, provider))

    def test_is_provider_configured_key_is_none(self):
        '''
        Tests when a required configuration key is not set
        '''
        opts = {'providers': {'foo': {'bar': {'api_key': None}}}}
        provider = 'foo:bar'
        self.assertFalse(
            sconfig.is_provider_configured(opts,
                                           provider,
                                           required_keys=('api_key',)))

    def test_is_provider_configured_success(self):
        '''
        Tests successful cloud provider configuration
        '''
        opts = {'providers': {'foo': {'bar': {'api_key': 'baz'}}}}
        provider = 'foo:bar'
        ret = {'api_key': 'baz'}
        self.assertEqual(
            sconfig.is_provider_configured(opts,
                                           provider,
                                           required_keys=('api_key',)), ret)

    def test_is_provider_configured_multiple_driver_not_provider(self):
        '''
        Tests when the drive is not the same as the provider when
        searching through multiple providers
        '''
        opts = {'providers': {'foo': {'bar': {'api_key': 'baz'}}}}
        provider = 'foo'
        self.assertFalse(sconfig.is_provider_configured(opts, provider))

    def test_is_provider_configured_multiple_key_is_none(self):
        '''
        Tests when a required configuration key is not set when
        searching through multiple providers
        '''
        opts = {'providers': {'foo': {'bar': {'api_key': None}}}}
        provider = 'bar'
        self.assertFalse(
            sconfig.is_provider_configured(opts,
                                           provider,
                                           required_keys=('api_key',)))

    def test_is_provider_configured_multiple_success(self):
        '''
        Tests successful cloud provider configuration when searching
        through multiple providers
        '''
        opts = {'providers': {'foo': {'bar': {'api_key': 'baz'}}}}
        provider = 'bar'
        ret = {'api_key': 'baz'}
        self.assertEqual(
            sconfig.is_provider_configured(opts,
                                           provider,
                                           required_keys=('api_key',)), ret)

    # other cloud configuration tests

    def test_load_cloud_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            salt.utils.fopen(env_fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(env_root_dir, env_fpath)
            )

            os.environ['SALT_CLOUD_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file
            config = sconfig.cloud_config('/etc/salt/cloud')
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            salt.utils.fopen(fpath, 'w').write(
                'root_dir: {0}\n'
                'log_file: {1}\n'.format(root_dir, fpath)
            )
            # Let's set the environment variable, yet, since the configuration
            # file path is not the default one, i.e., the user has passed an
            # alternative configuration file form the CLI parser, the
            # environment variable will be ignored.
            os.environ['SALT_CLOUD_CONFIG'] = env_fpath
            config = sconfig.cloud_config(fpath)
            self.assertEqual(config['log_file'], fpath)
        finally:
            # Reset the environ
            os.environ.clear()
            os.environ.update(original_environ)

            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_deploy_search_path_as_string(self):
        temp_conf_dir = os.path.join(integration.TMP, 'issue-8863')
        config_file_path = os.path.join(temp_conf_dir, 'cloud')
        deploy_dir_path = os.path.join(temp_conf_dir, 'test-deploy.d')
        try:
            for directory in (temp_conf_dir, deploy_dir_path):
                if not os.path.isdir(directory):
                    os.makedirs(directory)

            default_config = sconfig.cloud_config(config_file_path)
            default_config['deploy_scripts_search_path'] = deploy_dir_path
            with salt.utils.fopen(config_file_path, 'w') as cfd:
                cfd.write(yaml.dump(default_config))

            default_config = sconfig.cloud_config(config_file_path)

            # Our custom deploy scripts path was correctly added to the list
            self.assertIn(
                deploy_dir_path,
                default_config['deploy_scripts_search_path']
            )

            # And it's even the first occurrence as it should
            self.assertEqual(
                deploy_dir_path,
                default_config['deploy_scripts_search_path'][0]
            )
        finally:
            if os.path.isdir(temp_conf_dir):
                shutil.rmtree(temp_conf_dir)

    def test_includes_load(self):
        '''
        Tests that cloud.{providers,profiles}.d directories are loaded, even if not
        directly passed in through path
        '''
        config = sconfig.cloud_config(self.get_config_file_path('cloud'))
        self.assertIn('ec2-config', config['providers'])
        self.assertIn('ec2-test', config['profiles'])

# <---- Salt Cloud Configuration Tests ---------------------------------------------

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
