# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.config_test
    ~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import shutil
import tempfile
import textwrap

# Import Salt Testing libs
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.paths import TMP
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt libs
import salt.minion
import salt.utils.files
import salt.utils.network
import salt.utils.platform
import salt.utils.yaml
from salt.ext import six
from salt.syspaths import CONFIG_DIR
from salt import config as sconfig
from salt.exceptions import (
    CommandExecutionError,
    SaltConfigurationError,
    SaltCloudConfigError
)

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
    Raise an error because we should not be calling salt.utils.files.fopen()
    '''
    raise CommandExecutionError('Unhandled mock read for {0}'.format(filename))


def _salt_configuration_error(filename):
    '''
    Raise an error to indicate error in the Salt configuration file
    '''
    raise SaltConfigurationError('Configuration error in {0}'.format(filename))


class ConfigTestCase(TestCase, AdaptedConfigurationTestCaseMixin):

    def test_sha256_is_default_for_master(self):
        fpath = salt.utils.files.mkstemp(dir=TMP)
        try:
            with salt.utils.files.fopen(fpath, 'w') as wfh:
                wfh.write(
                    "root_dir: /\n"
                    "key_logfile: key\n"
                )
            config = sconfig.master_config(fpath)
            self.assertEqual(config['hash_type'], 'sha256')
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)

    def test_sha256_is_default_for_minion(self):
        fpath = salt.utils.files.mkstemp(dir=TMP)
        try:
            with salt.utils.files.fopen(fpath, 'w') as wfh:
                wfh.write(
                    "root_dir: /\n"
                    "key_logfile: key\n"
                )
            config = sconfig.minion_config(fpath)
            self.assertEqual(config['hash_type'], 'sha256')
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)

    def test_proper_path_joining(self):
        fpath = salt.utils.files.mkstemp(dir=TMP)
        temp_config = 'root_dir: /\n'\
                      'key_logfile: key\n'
        if salt.utils.platform.is_windows():
            temp_config = 'root_dir: c:\\\n'\
                          'key_logfile: key\n'
        try:
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(temp_config)

            config = sconfig.master_config(fpath)
            expect_path_join = os.path.join('/', 'key')
            expect_sep_join = '//key'
            if salt.utils.platform.is_windows():
                expect_path_join = os.path.join('c:\\', 'key')
                expect_sep_join = 'c:\\\\key'

            # os.path.join behavior
            self.assertEqual(config['key_logfile'], expect_path_join)
            # os.sep.join behavior
            self.assertNotEqual(config['key_logfile'], expect_sep_join)
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)

    def test_common_prefix_stripping(self):
        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(
                    'root_dir: {0}\n'
                    'log_file: {1}\n'.format(root_dir, fpath)
                )
            config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_default_root_dir_included_in_config_root_dir(self):
        os.makedirs(os.path.join(TMP, 'tmp2'))
        tempdir = tempfile.mkdtemp(dir=os.path.join(TMP, 'tmp2'))
        try:
            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(
                    'root_dir: {0}\n'
                    'log_file: {1}\n'.format(root_dir, fpath)
                )
            with patch('salt.syspaths.ROOT_DIR', TMP):
                config = sconfig.master_config(fpath)
            self.assertEqual(config['log_file'], fpath)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    @skipIf(
        salt.utils.platform.is_windows(),
        'You can\'t set an environment dynamically in Windows')
    def test_load_master_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            with salt.utils.files.fopen(env_fpath, 'w') as fp_:
                fp_.write(
                    'root_dir: {0}\n'
                    'log_file: {1}\n'.format(env_root_dir, env_fpath)
                )

            os.environ['SALT_MASTER_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file.
            config = sconfig.master_config('{0}/master'.format(CONFIG_DIR))
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(
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

    @skipIf(
        salt.utils.platform.is_windows(),
        'You can\'t set an environment dynamically in Windows')
    def test_load_minion_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            with salt.utils.files.fopen(env_fpath, 'w') as fp_:
                fp_.write(
                    'root_dir: {0}\n'
                    'log_file: {1}\n'.format(env_root_dir, env_fpath)
                )

            os.environ['SALT_MINION_CONFIG'] = env_fpath
            # Should load from env variable, not the default configuration file
            config = sconfig.minion_config('{0}/minion'.format(CONFIG_DIR))
            self.assertEqual(config['log_file'], env_fpath)
            os.environ.clear()
            os.environ.update(original_environ)

            root_dir = os.path.join(tempdir, 'foo', 'bar')
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, 'config')
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(
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
            tempdir = tempfile.mkdtemp(dir=TMP)
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)

            # Let's populate a master configuration file which should not get
            # picked up since the client configuration tries to load the master
            # configuration settings using the provided client configuration
            # file
            master_config = os.path.join(env_root_dir, 'master')
            with salt.utils.files.fopen(master_config, 'w') as fp_:
                fp_.write(
                    'blah: true\n'
                    'root_dir: {0}\n'
                    'log_file: {1}\n'.format(env_root_dir, master_config)
                )
            os.environ['SALT_MASTER_CONFIG'] = master_config

            # Now the client configuration file
            env_fpath = os.path.join(env_root_dir, 'config-env')
            with salt.utils.files.fopen(env_fpath, 'w') as fp_:
                fp_.write(
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
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(
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
            tempdir = tempfile.mkdtemp(dir=TMP)
            minion_config = os.path.join(tempdir, 'minion')
            minion_confd = os.path.join(tempdir, 'minion.d')
            os.makedirs(minion_confd)

            # Let's populate a minion configuration file with some basic
            # settings
            with salt.utils.files.fopen(minion_config, 'w') as fp_:
                fp_.write(
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
            with salt.utils.files.fopen(extra_config, 'w') as fp_:
                fp_.write('blah: true\n')

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
            tempdir = tempfile.mkdtemp(dir=TMP)
            master_config = os.path.join(tempdir, 'master')
            master_confd = os.path.join(tempdir, 'master.d')
            os.makedirs(master_confd)

            # Let's populate a master configuration file with some basic
            # settings
            with salt.utils.files.fopen(master_config, 'w') as fp_:
                fp_.write(
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
            with salt.utils.files.fopen(extra_config, 'w') as fp_:
                fp_.write('blah: true\n')

            # Let's load the configuration
            config = sconfig.master_config(master_config)

            self.assertEqual(config['log_file'], master_config)
            # As proven by the assertion below, blah is True
            self.assertTrue(config['blah'])
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_master_file_roots_glob(self):
        # Config file and stub file_roots.
        fpath = salt.utils.files.mkstemp()
        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            # Create some kown files.
            for f in 'abc':
                fpath = os.path.join(tempdir, f)
                with salt.utils.files.fopen(fpath, 'w') as wfh:
                    wfh.write(f)

            with salt.utils.files.fopen(fpath, 'w') as wfh:
                wfh.write(
                    'file_roots:\n'
                    '  base:\n'
                    '    - {0}'.format(os.path.join(tempdir, '*'))
                )
            config = sconfig.master_config(fpath)
            base = config['file_roots']['base']
            self.assertEqual(set(base), set([
                os.path.join(tempdir, 'a'),
                os.path.join(tempdir, 'b'),
                os.path.join(tempdir, 'c')
            ]))
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_master_pillar_roots_glob(self):
        # Config file and stub pillar_roots.
        fpath = salt.utils.files.mkstemp()
        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            # Create some kown files.
            for f in 'abc':
                fpath = os.path.join(tempdir, f)
                with salt.utils.files.fopen(fpath, 'w') as wfh:
                    wfh.write(f)

            with salt.utils.files.fopen(fpath, 'w') as wfh:
                wfh.write(
                    'pillar_roots:\n'
                    '  base:\n'
                    '    - {0}'.format(os.path.join(tempdir, '*'))
                )
            config = sconfig.master_config(fpath)
            base = config['pillar_roots']['base']
            self.assertEqual(set(base), set([
                os.path.join(tempdir, 'a'),
                os.path.join(tempdir, 'b'),
                os.path.join(tempdir, 'c')
            ]))
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_master_id_function(self):
        try:
            tempdir = tempfile.mkdtemp(dir=TMP)
            master_config = os.path.join(tempdir, 'master')

            with salt.utils.files.fopen(master_config, 'w') as fp_:
                fp_.write(
                    'id_function:\n'
                    '  test.echo:\n'
                    '    text: hello_world\n'
                    'root_dir: {0}\n'
                    'log_file: {1}\n'.format(tempdir, master_config)
                )

            # Let's load the configuration
            config = sconfig.master_config(master_config)

            self.assertEqual(config['log_file'], master_config)
            # 'master_config' appends '_master' to the ID
            self.assertEqual(config['id'], 'hello_world_master')
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_minion_file_roots_glob(self):
        # Config file and stub file_roots.
        fpath = salt.utils.files.mkstemp()
        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            # Create some kown files.
            for f in 'abc':
                fpath = os.path.join(tempdir, f)
                with salt.utils.files.fopen(fpath, 'w') as wfh:
                    wfh.write(f)

            with salt.utils.files.fopen(fpath, 'w') as wfh:
                wfh.write(
                    'file_roots:\n'
                    '  base:\n'
                    '    - {0}'.format(os.path.join(tempdir, '*'))
                )
            config = sconfig.minion_config(fpath)
            base = config['file_roots']['base']
            self.assertEqual(set(base), set([
                os.path.join(tempdir, 'a'),
                os.path.join(tempdir, 'b'),
                os.path.join(tempdir, 'c')
            ]))
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_minion_pillar_roots_glob(self):
        # Config file and stub pillar_roots.
        fpath = salt.utils.files.mkstemp()
        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            # Create some kown files.
            for f in 'abc':
                fpath = os.path.join(tempdir, f)
                with salt.utils.files.fopen(fpath, 'w') as wfh:
                    wfh.write(f)

            with salt.utils.files.fopen(fpath, 'w') as wfh:
                wfh.write(
                    'pillar_roots:\n'
                    '  base:\n'
                    '    - {0}'.format(os.path.join(tempdir, '*'))
                )
            config = sconfig.minion_config(fpath)
            base = config['pillar_roots']['base']
            self.assertEqual(set(base), set([
                os.path.join(tempdir, 'a'),
                os.path.join(tempdir, 'b'),
                os.path.join(tempdir, 'c')
            ]))
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_minion_id_function(self):
        try:
            tempdir = tempfile.mkdtemp(dir=TMP)
            minion_config = os.path.join(tempdir, 'minion')

            with salt.utils.files.fopen(minion_config, 'w') as fp_:
                fp_.write(
                    'id_function:\n'
                    '  test.echo:\n'
                    '    text: hello_world\n'
                    'root_dir: {0}\n'
                    'log_file: {1}\n'.format(tempdir, minion_config)
                )

            # Let's load the configuration
            config = sconfig.minion_config(minion_config)

            self.assertEqual(config['log_file'], minion_config)
            self.assertEqual(config['id'], 'hello_world')
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)

    def test_backend_rename(self):
        '''
        This tests that we successfully rename git, hg, svn, and minion to
        gitfs, hgfs, svnfs, and minionfs in the master and minion opts.
        '''
        tempdir = tempfile.mkdtemp(dir=TMP)
        fpath = salt.utils.files.mkstemp(dir=tempdir)
        self.addCleanup(shutil.rmtree, tempdir, ignore_errors=True)
        with salt.utils.files.fopen(fpath, 'w') as fp_:
            fp_.write(textwrap.dedent('''\
                fileserver_backend:
                  - roots
                  - git
                  - hg
                  - svn
                  - minion
                '''))

        master_config = sconfig.master_config(fpath)
        minion_config = sconfig.minion_config(fpath)
        expected = ['roots', 'gitfs', 'hgfs', 'svnfs', 'minionfs']

        self.assertEqual(master_config['fileserver_backend'], expected)
        self.assertEqual(minion_config['fileserver_backend'], expected)

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
        self.assertEqual(syndic_opts['log_file'], os.path.join(root_dir, 'syndic.log'))
        self.assertEqual(syndic_opts['pidfile'], os.path.join(root_dir, 'syndic.pid'))
        # Show that the options of localclient that repub to local master
        # are not merged with syndic ones
        self.assertEqual(syndic_opts['_master_conf_file'], minion_conf_path)
        self.assertEqual(syndic_opts['_minion_conf_file'], syndic_conf_path)

    def _get_tally(self, conf_func):
        '''
        This ensures that any strings which are loaded are unicode strings
        '''
        tally = {}

        def _count_strings(config):
            if isinstance(config, dict):
                for key, val in six.iteritems(config):
                    log.debug('counting strings in dict key: %s', key)
                    log.debug('counting strings in dict val: %s', val)
                    _count_strings(key)
                    _count_strings(val)
            elif isinstance(config, list):
                log.debug('counting strings in list: %s', config)
                for item in config:
                    _count_strings(item)
            else:
                if isinstance(config, six.string_types):
                    if isinstance(config, six.text_type):
                        tally['unicode'] = tally.get('unicode', 0) + 1
                    else:
                        # We will never reach this on PY3
                        tally.setdefault('non_unicode', []).append(config)

        fpath = salt.utils.files.mkstemp(dir=TMP)
        try:
            with salt.utils.files.fopen(fpath, 'w') as wfh:
                wfh.write(textwrap.dedent('''
                    foo: bar
                    mylist:
                      - somestring
                      - 9
                      - 123.456
                      - True
                      - nested:
                        - key: val
                        - nestedlist:
                          - foo
                          - bar
                          - baz
                    mydict:
                      - somestring: 9
                      - 123.456: 789
                      - True: False
                      - nested:
                        - key: val
                        - nestedlist:
                          - foo
                          - bar
                          - baz'''))
                if conf_func is sconfig.master_config:
                    wfh.write('\n\n')
                    wfh.write(textwrap.dedent('''
                        rest_cherrypy:
                          port: 8000
                          disable_ssl: True
                          app_path: /beacon_demo
                          app: /srv/web/html/index.html
                          static: /srv/web/static'''))
            config = conf_func(fpath)
            _count_strings(config)
            return tally
        finally:
            if os.path.isfile(fpath):
                os.unlink(fpath)

    def test_conf_file_strings_are_unicode_for_master(self):
        '''
        This ensures that any strings which are loaded are unicode strings
        '''
        tally = self._get_tally(sconfig.master_config)
        non_unicode = tally.get('non_unicode', [])
        self.assertEqual(len(non_unicode), 8 if six.PY2 else 0, non_unicode)
        self.assertTrue(tally['unicode'] > 0)

    def test_conf_file_strings_are_unicode_for_minion(self):
        '''
        This ensures that any strings which are loaded are unicode strings
        '''
        tally = self._get_tally(sconfig.minion_config)
        non_unicode = tally.get('non_unicode', [])
        self.assertEqual(len(non_unicode), 0, non_unicode)
        self.assertTrue(tally['unicode'] > 0)

# <---- Salt Cloud Configuration Tests ---------------------------------------------

    # cloud_config tests

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_cloud_config_double_master_path(self):
        '''
        Tests passing in master_config_path and master_config kwargs.
        '''
        with patch('salt.config.load_config', MagicMock(return_value={})):
            self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                              master_config_path='foo', master_config='bar')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_cloud_config_double_providers_path(self):
        '''
        Tests passing in providers_config_path and providers_config kwargs.
        '''
        with patch('salt.config.load_config', MagicMock(return_value={})):
            self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                              providers_config_path='foo', providers_config='bar')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_cloud_config_double_profiles_path(self):
        '''
        Tests passing in profiles_config_path and profiles_config kwargs.
        '''
        with patch('salt.config.load_config', MagicMock(return_value={})):
            self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                              profiles_config_path='foo', profiles_config='bar')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_cloud_config_providers_in_opts(self):
        '''
        Tests mixing old cloud providers with pre-configured providers configurations
        using the providers_config kwarg
        '''
        with patch('salt.config.load_config', MagicMock(return_value={})):
            with patch('salt.config.apply_cloud_config',
                       MagicMock(return_value={'providers': 'foo'})):
                self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                                  providers_config='bar')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_cloud_config_providers_in_opts_path(self):
        '''
        Tests mixing old cloud providers with pre-configured providers configurations
        using the providers_config_path kwarg
        '''
        with patch('salt.config.load_config', MagicMock(return_value={})):
            with patch('salt.config.apply_cloud_config',
                       MagicMock(return_value={'providers': 'foo'})):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    self.assertRaises(SaltCloudConfigError, sconfig.cloud_config, PATH,
                                      providers_config_path='bar')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
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
        with patch('os.path.isdir', MagicMock(return_value=True)):
            search_paths = sconfig.cloud_config('/etc/salt/cloud').get('deploy_scripts_search_path')
            etc_deploy_path = '/salt/cloud.deploy.d'
            deploy_path = '/salt/cloud/deploy'
            if salt.utils.platform.is_windows():
                etc_deploy_path = '/salt\\cloud.deploy.d'
                deploy_path = '\\salt\\cloud\\deploy'

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

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_apply_cloud_config_success_list(self):
        '''
        Tests success when valid data is passed into the function as a list
        '''
        with patch('salt.config.old_to_new',
                   MagicMock(return_value={'default_include': 'path/to/some/cloud/conf/file',
                                           'providers': {
                                               'foo': {
                                                   'bar': {
                                                       'driver': 'foo:bar'}}}})):
            overrides = {'providers': {'foo': [{'driver': 'bar'}]}}
            ret = {'default_include': 'path/to/some/cloud/conf/file',
                   'providers': {'foo': {'bar': {'driver': 'foo:bar'}}}}
            self.assertEqual(sconfig.apply_cloud_config(overrides, defaults=DEFAULT), ret)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_apply_cloud_config_success_dict(self):
        '''
        Tests success when valid data is passed into function as a dictionary
        '''
        with patch('salt.config.old_to_new',
                   MagicMock(return_value={'default_include': 'path/to/some/cloud/conf/file',
                                           'providers': {
                                               'foo': {
                                                   'bar': {
                                                       'driver': 'foo:bar'}}}})):
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
                         {'digitalocean':
                              {'driver': 'digitalocean', 'profiles': {}}}}
        overrides = {'test-profile':
                         {'provider': 'test-provider',
                          'image': 'Ubuntu 12.10 x64',
                          'size': '512MB'},
                     'conf_file': PATH}
        ret = {'test-profile':
                   {'profile': 'test-profile',
                    'provider': 'test-provider:digitalocean',
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

    def test_apply_vm_profiles_config_extend_override_success(self):
        '''
        Tests profile extends and recursively merges data elements
        '''
        self.maxDiff = None
        providers = {'test-config': {'ec2': {'profiles': {}, 'driver': 'ec2'}}}
        overrides = {'Fedora': {'image': 'test-image-2',
                                'extends': 'dev-instances',
                                'minion': {'grains': {'stage': 'experimental'}}},
                     'conf_file': PATH,
                     'dev-instances': {'ssh_username': 'test_user',
                                       'provider': 'test-config',
                                       'minion': {'grains': {'role': 'webserver'}}}}
        ret = {'Fedora': {'profile': 'Fedora',
                          'ssh_username': 'test_user',
                          'image': 'test-image-2',
                          'minion': {'grains': {'role': 'webserver',
                                                'stage': 'experimental'}},
                          'provider': 'test-config:ec2'},
               'dev-instances': {'profile': 'dev-instances',
                                 'ssh_username': 'test_user',
                                 'minion': {'grains': {'role': 'webserver'}},
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

    @skipIf(
        salt.utils.platform.is_windows(),
        'You can\'t set an environment dynamically in Windows')
    def test_load_cloud_config_from_environ_var(self):
        original_environ = os.environ.copy()

        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            env_root_dir = os.path.join(tempdir, 'foo', 'env')
            os.makedirs(env_root_dir)
            env_fpath = os.path.join(env_root_dir, 'config-env')

            with salt.utils.files.fopen(env_fpath, 'w') as fp_:
                fp_.write(
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
            with salt.utils.files.fopen(fpath, 'w') as fp_:
                fp_.write(
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
        temp_conf_dir = os.path.join(TMP, 'issue-8863')
        config_file_path = os.path.join(temp_conf_dir, 'cloud')
        deploy_dir_path = os.path.join(temp_conf_dir, 'test-deploy.d')
        try:
            for directory in (temp_conf_dir, deploy_dir_path):
                if not os.path.isdir(directory):
                    os.makedirs(directory)

            default_config = sconfig.cloud_config(config_file_path)
            default_config['deploy_scripts_search_path'] = deploy_dir_path
            with salt.utils.files.fopen(config_file_path, 'w') as cfd:
                salt.utils.yaml.safe_dump(default_config, cfd, default_flow_style=False)

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

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_include_config_without_errors(self):
        '''
        Tests that include_config function returns valid configuration
        '''
        include_file = 'minion.d/my.conf'
        config_path = '/etc/salt/minion'
        config_opts = {'id': 'myminion.example.com'}

        with patch('glob.glob', MagicMock(return_value=include_file)):
            with patch('salt.config._read_conf_file', MagicMock(return_value=config_opts)):
                configuration = sconfig.include_config(include_file, config_path, verbose=False)

        self.assertEqual(config_opts, configuration)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_include_config_with_errors(self):
        '''
        Tests that include_config function returns valid configuration even on errors
        '''
        include_file = 'minion.d/my.conf'
        config_path = '/etc/salt/minion'
        config_opts = {}

        with patch('glob.glob', MagicMock(return_value=include_file)):
            with patch('salt.config._read_conf_file', _salt_configuration_error):
                configuration = sconfig.include_config(include_file, config_path, verbose=False)

        self.assertEqual(config_opts, configuration)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_include_config_with_errors_exit(self):
        '''
        Tests that include_config exits on errors
        '''
        include_file = 'minion.d/my.conf'
        config_path = '/etc/salt/minion'

        with patch('glob.glob', MagicMock(return_value=include_file)):
            with patch('salt.config._read_conf_file', _salt_configuration_error):
                with self.assertRaises(SystemExit):
                    sconfig.include_config(include_file,
                                           config_path,
                                           verbose=False,
                                           exit_on_config_errors=True)
