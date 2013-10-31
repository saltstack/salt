# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.config_test
    ~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import shutil
import tempfile
import warnings

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath, TestsLoggingHandler

ensure_in_syspath('../')

# Import salt libs
import salt.minion
import salt.utils
import integration
from salt import config as sconfig, version as salt_version


class ConfigTestCase(TestCase):
    def test_proper_path_joining(self):
        fpath = tempfile.mktemp()
        try:
            salt.utils.fopen(fpath, 'w').write(
                "root_dir: /\n"
                "key_logfile: key\n"
            )
            config = sconfig.master_config(fpath)
            # os.path.join behaviour
            self.assertEqual(config['key_logfile'], os.path.join('/', 'key'))
            # os.sep.join behaviour
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
            # file path is not the default one, ie, the user has passed an
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
            # file path is not the default one, ie, the user has passed an
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
            # file path is not the default one, ie, the user has passed an
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
            # Notice that above we've set blah as False and bellow as True.
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
            # Notice that above we've set blah as False and bellow as True.
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
        syndic_conf_path = os.path.join(
            integration.INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic'
        )
        minion_config_path = os.path.join(
            integration.INTEGRATION_TEST_DIR, 'files', 'conf', 'minion'
        )
        syndic_opts = sconfig.syndic_config(
            syndic_conf_path, minion_config_path
        )
        syndic_opts.update(salt.minion.resolve_dns(syndic_opts))
        # id & pki dir are shared & so configured on the minion side
        self.assertEqual(syndic_opts['id'], 'minion')
        self.assertEqual(syndic_opts['pki_dir'], '/tmp/salttest/pki')
        # the rest is configured master side
        self.assertEqual(syndic_opts['master_uri'], 'tcp://127.0.0.1:54506')
        self.assertEqual(syndic_opts['master_port'], 54506)
        self.assertEqual(syndic_opts['master_ip'], '127.0.0.1')
        self.assertEqual(syndic_opts['master'], 'localhost')
        self.assertEqual(syndic_opts['sock_dir'], '/tmp/salttest/minion_sock')
        self.assertEqual(syndic_opts['cachedir'], '/tmp/salttest/cachedir')
        self.assertEqual(syndic_opts['log_file'], '/tmp/salttest/osyndic.log')
        self.assertEqual(syndic_opts['pidfile'], '/tmp/salttest/osyndic.pid')
        # Show that the options of localclient that repub to local master
        # are not merged with syndic ones
        self.assertEqual(syndic_opts['_master_conf_file'], minion_config_path)
        self.assertEqual(syndic_opts['_minion_conf_file'], syndic_conf_path)

    def test_check_dns_deprecation_warning(self):
        if salt_version.__version_info__ >= (0, 19):
            raise AssertionError(
                'Failing this test on purpose! Please delete this test case, '
                'the \'check_dns\' keyword argument and the deprecation '
                'warnings in `salt.config.minion_config` and '
                'salt.config.apply_minion_config`'
            )

        # Let's force the warning to always be thrown
        warnings.resetwarnings()
        warnings.filterwarnings(
            'always', '(.*)check_dns(.*)', DeprecationWarning, 'salt.config'
        )
        with warnings.catch_warnings(record=True) as w:
            sconfig.minion_config(None, None, check_dns=True)
            self.assertEqual(
                'The functionality behind the \'check_dns\' keyword argument '
                'is no longer required, as such, it became unnecessary and is '
                'now deprecated. \'check_dns\' will be removed in salt > '
                '0.18.0', str(w[-1].message)
            )

        with warnings.catch_warnings(record=True) as w:
            sconfig.apply_minion_config(
                overrides=None, defaults=None, check_dns=True
            )
            self.assertEqual(
                'The functionality behind the \'check_dns\' keyword argument '
                'is no longer required, as such, it became unnecessary and is '
                'now deprecated. \'check_dns\' will be removed in salt > '
                '0.18.0', str(w[-1].message)
            )

        with warnings.catch_warnings(record=True) as w:
            sconfig.minion_config(None, None, check_dns=False)
            self.assertEqual(
                'The functionality behind the \'check_dns\' keyword argument '
                'is no longer required, as such, it became unnecessary and is '
                'now deprecated. \'check_dns\' will be removed in salt > '
                '0.18.0', str(w[-1].message)
            )

        with warnings.catch_warnings(record=True) as w:
            sconfig.apply_minion_config(
                overrides=None, defaults=None, check_dns=False
            )
            self.assertEqual(
                'The functionality behind the \'check_dns\' keyword argument '
                'is no longer required, as such, it became unnecessary and is '
                'now deprecated. \'check_dns\' will be removed in salt > '
                '0.18.0', str(w[-1].message)
            )

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
