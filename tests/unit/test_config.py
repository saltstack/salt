"""
Unit tests for salt.config
"""

import logging
import os
import textwrap

import pytest

import salt.config
import salt.minion
import salt.syspaths
import salt.utils.files
import salt.utils.network
import salt.utils.platform
import salt.utils.yaml
from salt.exceptions import (
    CommandExecutionError,
    SaltCloudConfigError,
    SaltConfigurationError,
)
from salt.syspaths import CONFIG_DIR
from tests.support.helpers import patched_environ, with_tempdir, with_tempfile
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)

SAMPLE_CONF_DIR = os.path.join(RUNTIME_VARS.CODE_DIR, "conf") + os.sep

# mock hostname should be more complex than the systems FQDN
MOCK_HOSTNAME = "very.long.complex.fqdn.that.is.crazy.extra.long.example.com"

MOCK_ETC_HOSTS = textwrap.dedent(
    """\
    ##
    # Host Database
    #
    # localhost is used to configure the loopback interface
    # when the system is booting.  Do not change this entry.
    ## The empty line below must remain, it factors into the tests.

    127.0.0.1      localhost   {hostname}
    10.0.0.100     {hostname}
    200.200.200.2  other.host.alias.com
    ::1            ip6-localhost ip6-loopback
    fe00::0        ip6-localnet
    ff00::0        ip6-mcastprefix
    """.format(
        hostname=MOCK_HOSTNAME
    )
)
MOCK_ETC_HOSTNAME = f"{MOCK_HOSTNAME}\n"
PATH = "path/to/some/cloud/conf/file"
DEFAULT = {"default_include": PATH}


class DefaultConfigsBase:
    @classmethod
    def setUpClass(cls):
        cls.mock_master_default_opts = dict(
            root_dir=RUNTIME_VARS.TMP_ROOT_DIR,
            log_file=os.path.join(
                RUNTIME_VARS.TMP_ROOT_DIR, "var", "log", "salt", "master"
            ),
            pid_file=os.path.join(
                RUNTIME_VARS.TMP_ROOT_DIR, "var", "run", "salt-master.pid"
            ),
        )


class SampleConfTest(DefaultConfigsBase, TestCase):
    """
    Validate files in the salt/conf directory.
    """

    def test_conf_master_sample_is_commented(self):
        """
        The sample config file located in salt/conf/master must be completely
        commented out. This test checks for any lines that are not commented or blank.
        """
        master_config = SAMPLE_CONF_DIR + "master"
        ret = salt.config._read_conf_file(master_config)
        self.assertEqual(
            ret,
            {},
            f"Sample config file '{master_config}' must be commented out.",
        )

    def test_conf_minion_sample_is_commented(self):
        """
        The sample config file located in salt/conf/minion must be completely
        commented out. This test checks for any lines that are not commented or blank.
        """
        minion_config = SAMPLE_CONF_DIR + "minion"
        ret = salt.config._read_conf_file(minion_config)
        self.assertEqual(
            ret,
            {},
            f"Sample config file '{minion_config}' must be commented out.",
        )

    def test_conf_cloud_sample_is_commented(self):
        """
        The sample config file located in salt/conf/cloud must be completely
        commented out. This test checks for any lines that are not commented or blank.
        """
        cloud_config = SAMPLE_CONF_DIR + "cloud"
        ret = salt.config._read_conf_file(cloud_config)
        self.assertEqual(
            ret,
            {},
            f"Sample config file '{cloud_config}' must be commented out.",
        )

    def test_conf_cloud_profiles_sample_is_commented(self):
        """
        The sample config file located in salt/conf/cloud.profiles must be completely
        commented out. This test checks for any lines that are not commented or blank.
        """
        cloud_profiles_config = SAMPLE_CONF_DIR + "cloud.profiles"
        ret = salt.config._read_conf_file(cloud_profiles_config)
        self.assertEqual(
            ret,
            {},
            "Sample config file '{}' must be commented out.".format(
                cloud_profiles_config
            ),
        )

    def test_conf_cloud_providers_sample_is_commented(self):
        """
        The sample config file located in salt/conf/cloud.providers must be completely
        commented out. This test checks for any lines that are not commented or blank.
        """
        cloud_providers_config = SAMPLE_CONF_DIR + "cloud.providers"
        ret = salt.config._read_conf_file(cloud_providers_config)
        self.assertEqual(
            ret,
            {},
            "Sample config file '{}' must be commented out.".format(
                cloud_providers_config
            ),
        )

    def test_conf_proxy_sample_is_commented(self):
        """
        The sample config file located in salt/conf/proxy must be completely
        commented out. This test checks for any lines that are not commented or blank.
        """
        proxy_config = SAMPLE_CONF_DIR + "proxy"
        ret = salt.config._read_conf_file(proxy_config)
        self.assertEqual(
            ret,
            {},
            f"Sample config file '{proxy_config}' must be commented out.",
        )

    def test_conf_roster_sample_is_commented(self):
        """
        The sample config file located in salt/conf/roster must be completely
        commented out. This test checks for any lines that are not commented or blank.
        """
        roster_config = SAMPLE_CONF_DIR + "roster"
        ret = salt.config._read_conf_file(roster_config)
        self.assertEqual(
            ret,
            {},
            f"Sample config file '{roster_config}' must be commented out.",
        )

    def test_conf_cloud_profiles_d_files_are_commented(self):
        """
        All cloud profile sample configs in salt/conf/cloud.profiles.d/* must be completely
        commented out. This test loops through all of the files in that directory to check
        for any lines that are not commented or blank.
        """
        cloud_sample_dir = SAMPLE_CONF_DIR + "cloud.profiles.d/"
        if not os.path.exists(cloud_sample_dir):
            self.skipTest(f"Sample config directory '{cloud_sample_dir}' is missing.")
        cloud_sample_files = os.listdir(cloud_sample_dir)
        for conf_file in cloud_sample_files:
            profile_conf = cloud_sample_dir + conf_file
            ret = salt.config._read_conf_file(profile_conf)
            self.assertEqual(
                ret,
                {},
                f"Sample config file '{conf_file}' must be commented out.",
            )

    def test_conf_cloud_providers_d_files_are_commented(self):
        """
        All cloud profile sample configs in salt/conf/cloud.providers.d/* must be completely
        commented out. This test loops through all of the files in that directory to check
        for any lines that are not commented or blank.
        """
        cloud_sample_dir = SAMPLE_CONF_DIR + "cloud.providers.d/"
        if not os.path.exists(cloud_sample_dir):
            self.skipTest(f"Sample config directory '{cloud_sample_dir}' is missing.")
        cloud_sample_files = os.listdir(cloud_sample_dir)
        for conf_file in cloud_sample_files:
            provider_conf = cloud_sample_dir + conf_file
            ret = salt.config._read_conf_file(provider_conf)
            self.assertEqual(
                ret,
                {},
                f"Sample config file '{conf_file}' must be commented out.",
            )

    def test_conf_cloud_maps_d_files_are_commented(self):
        """
        All cloud profile sample configs in salt/conf/cloud.maps.d/* must be completely
        commented out. This test loops through all of the files in that directory to check
        for any lines that are not commented or blank.
        """
        cloud_sample_dir = SAMPLE_CONF_DIR + "cloud.maps.d/"
        if not os.path.exists(cloud_sample_dir):
            self.skipTest(f"Sample config directory '{cloud_sample_dir}' is missing.")
        cloud_sample_files = os.listdir(cloud_sample_dir)
        for conf_file in cloud_sample_files:
            map_conf = cloud_sample_dir + conf_file
            ret = salt.config._read_conf_file(map_conf)
            self.assertEqual(
                ret,
                {},
                f"Sample config file '{conf_file}' must be commented out.",
            )


def _unhandled_mock_read(filename):
    """
    Raise an error because we should not be calling salt.utils.files.fopen()
    """
    raise CommandExecutionError(f"Unhandled mock read for {filename}")


def _salt_configuration_error(filename):
    """
    Raise an error to indicate error in the Salt configuration file
    """
    raise SaltConfigurationError(f"Configuration error in {filename}")


class ConfigTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    @with_tempfile()
    def test_sha256_is_default_for_master(self, fpath):
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write("root_dir: /\nkey_logfile: key\n")
        config = salt.config.master_config(fpath)
        self.assertEqual(config["hash_type"], "sha256")

    @with_tempfile()
    def test_sha256_is_default_for_minion(self, fpath):
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write("root_dir: /\nkey_logfile: key\n")
        config = salt.config.minion_config(fpath)
        self.assertEqual(config["hash_type"], "sha256")

    @with_tempfile()
    def test_proper_path_joining(self, fpath):
        temp_config = "root_dir: /\nkey_logfile: key\n"
        if salt.utils.platform.is_windows():
            temp_config = "root_dir: c:\\\nkey_logfile: key\n"
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(temp_config)

        config = salt.config.master_config(fpath)
        expect_path_join = os.path.join("/", "key")
        expect_sep_join = "//key"
        if salt.utils.platform.is_windows():
            expect_path_join = os.path.join("c:\\", "key")
            expect_sep_join = "c:\\\\key"

        # os.path.join behavior
        self.assertEqual(config["key_logfile"], expect_path_join)
        # os.sep.join behavior
        self.assertNotEqual(config["key_logfile"], expect_sep_join)

    @with_tempdir()
    def test_common_prefix_stripping(self, tempdir):
        root_dir = os.path.join(tempdir, "foo", "bar")
        os.makedirs(root_dir)
        fpath = os.path.join(root_dir, "config")
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(f"root_dir: {root_dir}\nlog_file: {fpath}\n")
        config = salt.config.master_config(fpath)
        self.assertEqual(config["log_file"], fpath)

    @with_tempdir()
    def test_default_root_dir_included_in_config_root_dir(self, tempdir):
        root_dir = os.path.join(tempdir, "foo", "bar")
        os.makedirs(root_dir)
        fpath = os.path.join(root_dir, "config")
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(f"root_dir: {root_dir}\nlog_file: {fpath}\n")
        config = salt.config.master_config(fpath)
        self.assertEqual(config["log_file"], fpath)

    @pytest.mark.skip_on_windows(
        reason="You can't set an environment dynamically in Windows"
    )
    @with_tempdir()
    def test_load_master_config_from_environ_var(self, tempdir):
        env_root_dir = os.path.join(tempdir, "foo", "env")
        os.makedirs(env_root_dir)
        env_fpath = os.path.join(env_root_dir, "config-env")

        with salt.utils.files.fopen(env_fpath, "w") as fp_:
            fp_.write(f"root_dir: {env_root_dir}\nlog_file: {env_fpath}\n")
        with patched_environ(SALT_MASTER_CONFIG=env_fpath):
            # Should load from env variable, not the default configuration file.
            config = salt.config.master_config(f"{CONFIG_DIR}/master")
            self.assertEqual(config["log_file"], env_fpath)

        root_dir = os.path.join(tempdir, "foo", "bar")
        os.makedirs(root_dir)
        fpath = os.path.join(root_dir, "config")
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(f"root_dir: {root_dir}\nlog_file: {fpath}\n")
        # Let's set the environment variable, yet, since the configuration
        # file path is not the default one, i.e., the user has passed an
        # alternative configuration file form the CLI parser, the
        # environment variable will be ignored.
        with patched_environ(SALT_MASTER_CONFIG=env_fpath):
            config = salt.config.master_config(fpath)
            self.assertEqual(config["log_file"], fpath)

    @pytest.mark.skip_on_windows(
        reason="You can't set an environment dynamically in Windows"
    )
    @with_tempdir()
    def test_load_minion_config_from_environ_var(self, tempdir):
        env_root_dir = os.path.join(tempdir, "foo", "env")
        os.makedirs(env_root_dir)
        env_fpath = os.path.join(env_root_dir, "config-env")

        with salt.utils.files.fopen(env_fpath, "w") as fp_:
            fp_.write(f"root_dir: {env_root_dir}\nlog_file: {env_fpath}\n")

        with patched_environ(SALT_MINION_CONFIG=env_fpath):
            # Should load from env variable, not the default configuration file
            config = salt.config.minion_config(f"{CONFIG_DIR}/minion")
            self.assertEqual(config["log_file"], env_fpath)

        root_dir = os.path.join(tempdir, "foo", "bar")
        os.makedirs(root_dir)
        fpath = os.path.join(root_dir, "config")
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(f"root_dir: {root_dir}\nlog_file: {fpath}\n")
        # Let's set the environment variable, yet, since the configuration
        # file path is not the default one, i.e., the user has passed an
        # alternative configuration file form the CLI parser, the
        # environment variable will be ignored.
        with patched_environ(SALT_MINION_CONFIG=env_fpath):
            config = salt.config.minion_config(fpath)
            self.assertEqual(config["log_file"], fpath)

    @pytest.mark.skip_on_windows(
        reason="You can't set an environment dynamically in Windows"
    )
    @with_tempdir()
    def test_load_client_config_from_environ_var(self, tempdir):
        env_root_dir = os.path.join(tempdir, "foo", "env")
        os.makedirs(env_root_dir)

        # Let's populate a master configuration file which should not get
        # picked up since the client configuration tries to load the master
        # configuration settings using the provided client configuration
        # file
        master_config = os.path.join(env_root_dir, "master")
        with salt.utils.files.fopen(master_config, "w") as fp_:
            fp_.write(
                "blah: true\nroot_dir: {}\nlog_file: {}\n".format(
                    env_root_dir, master_config
                )
            )

        # Now the client configuration file
        env_fpath = os.path.join(env_root_dir, "config-env")
        with salt.utils.files.fopen(env_fpath, "w") as fp_:
            fp_.write(f"root_dir: {env_root_dir}\nlog_file: {env_fpath}\n")

        with patched_environ(
            SALT_MASTER_CONFIG=master_config, SALT_CLIENT_CONFIG=env_fpath
        ):
            # Should load from env variable, not the default configuration file
            config = salt.config.client_config(os.path.expanduser("~/.salt"))
            self.assertEqual(config["log_file"], env_fpath)
            self.assertTrue("blah" not in config)

        root_dir = os.path.join(tempdir, "foo", "bar")
        os.makedirs(root_dir)
        fpath = os.path.join(root_dir, "config")
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(f"root_dir: {root_dir}\nlog_file: {fpath}\n")
        # Let's set the environment variable, yet, since the configuration
        # file path is not the default one, i.e., the user has passed an
        # alternative configuration file form the CLI parser, the
        # environment variable will be ignored.
        with patched_environ(
            SALT_MASTER_CONFIG=env_fpath, SALT_CLIENT_CONFIG=env_fpath
        ):
            config = salt.config.master_config(fpath)
            self.assertEqual(config["log_file"], fpath)

    @with_tempdir()
    def test_issue_5970_minion_confd_inclusion(self, tempdir):
        minion_config = os.path.join(tempdir, "minion")
        minion_confd = os.path.join(tempdir, "minion.d")
        os.makedirs(minion_confd)

        # Let's populate a minion configuration file with some basic
        # settings
        with salt.utils.files.fopen(minion_config, "w") as fp_:
            fp_.write(
                "blah: false\nroot_dir: {}\nlog_file: {}\n".format(
                    tempdir, minion_config
                )
            )

        # Now, let's populate an extra configuration file under minion.d
        # Notice that above we've set blah as False and below as True.
        # Since the minion.d files are loaded after the main configuration
        # file so overrides can happen, the final value of blah should be
        # True.
        extra_config = os.path.join(minion_confd, "extra.conf")
        with salt.utils.files.fopen(extra_config, "w") as fp_:
            fp_.write("blah: true\n")

        # Let's load the configuration
        config = salt.config.minion_config(minion_config)

        self.assertEqual(config["log_file"], minion_config)
        # As proven by the assertion below, blah is True
        self.assertTrue(config["blah"])

    @with_tempdir()
    def test_master_confd_inclusion(self, tempdir):
        master_config = os.path.join(tempdir, "master")
        master_confd = os.path.join(tempdir, "master.d")
        os.makedirs(master_confd)

        # Let's populate a master configuration file with some basic
        # settings
        with salt.utils.files.fopen(master_config, "w") as fp_:
            fp_.write(
                "blah: false\nroot_dir: {}\nlog_file: {}\n".format(
                    tempdir, master_config
                )
            )

        # Now, let's populate an extra configuration file under master.d
        # Notice that above we've set blah as False and below as True.
        # Since the master.d files are loaded after the main configuration
        # file so overrides can happen, the final value of blah should be
        # True.
        extra_config = os.path.join(master_confd, "extra.conf")
        with salt.utils.files.fopen(extra_config, "w") as fp_:
            fp_.write("blah: true\n")

        # Let's load the configuration
        config = salt.config.master_config(master_config)

        self.assertEqual(config["log_file"], master_config)
        # As proven by the assertion below, blah is True
        self.assertTrue(config["blah"])

    @with_tempfile()
    @with_tempdir()
    def test_master_file_roots_glob(self, tempdir, fpath):
        # Create some files
        for f in "abc":
            fpath = os.path.join(tempdir, f)
            with salt.utils.files.fopen(fpath, "w") as wfh:
                wfh.write(f)

        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(
                "file_roots:\n  base:\n    - {}".format(os.path.join(tempdir, "*"))
            )
        config = salt.config.master_config(fpath)
        base = config["file_roots"]["base"]
        self.assertEqual(
            set(base),
            {
                os.path.join(tempdir, "a"),
                os.path.join(tempdir, "b"),
                os.path.join(tempdir, "c"),
            },
        )

    def test_validate_bad_file_roots(self):
        expected = salt.config._expand_glob_path([salt.syspaths.BASE_FILE_ROOTS_DIR])
        with patch("salt.config._normalize_roots") as mk:
            ret = salt.config._validate_file_roots(None)
            assert not mk.called
        assert ret == {"base": expected}

    @with_tempfile()
    @with_tempdir()
    def test_master_pillar_roots_glob(self, tempdir, fpath):
        # Create some files.
        for f in "abc":
            fpath = os.path.join(tempdir, f)
            with salt.utils.files.fopen(fpath, "w") as wfh:
                wfh.write(f)

        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(
                "pillar_roots:\n  base:\n    - {}".format(os.path.join(tempdir, "*"))
            )
        config = salt.config.master_config(fpath)
        base = config["pillar_roots"]["base"]
        self.assertEqual(
            set(base),
            {
                os.path.join(tempdir, "a"),
                os.path.join(tempdir, "b"),
                os.path.join(tempdir, "c"),
            },
        )

    def test_validate_bad_pillar_roots(self):
        expected = salt.config._expand_glob_path([salt.syspaths.BASE_PILLAR_ROOTS_DIR])
        with patch("salt.config._normalize_roots") as mk:
            ret = salt.config._validate_pillar_roots(None)
            assert not mk.called
        assert ret == {"base": expected}

    @with_tempdir()
    @pytest.mark.slow_test
    def test_master_id_function(self, tempdir):
        master_config = os.path.join(tempdir, "master")

        with salt.utils.files.fopen(master_config, "w") as fp_:
            fp_.write(
                "id_function:\n"
                "  test.echo:\n"
                "    text: hello_world\n"
                "root_dir: {}\n"
                "log_file: {}\n".format(tempdir, master_config)
            )

        # Let's load the configuration
        config = salt.config.master_config(master_config)

        self.assertEqual(config["log_file"], master_config)
        # 'master_config' appends '_master' to the ID
        self.assertEqual(config["id"], "hello_world_master")

    @with_tempfile()
    @with_tempdir()
    def test_minion_file_roots_glob(self, tempdir, fpath):
        # Create some files.
        for f in "abc":
            fpath = os.path.join(tempdir, f)
            with salt.utils.files.fopen(fpath, "w") as wfh:
                wfh.write(f)

        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(
                "file_roots:\n  base:\n    - {}".format(os.path.join(tempdir, "*"))
            )
        config = salt.config.minion_config(fpath)
        base = config["file_roots"]["base"]
        self.assertEqual(
            set(base),
            {
                os.path.join(tempdir, "a"),
                os.path.join(tempdir, "b"),
                os.path.join(tempdir, "c"),
            },
        )

    @with_tempfile()
    @with_tempdir()
    def test_minion_pillar_roots_glob(self, tempdir, fpath):
        # Create some files.
        for f in "abc":
            fpath = os.path.join(tempdir, f)
            with salt.utils.files.fopen(fpath, "w") as wfh:
                wfh.write(f)

        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(
                "pillar_roots:\n  base:\n    - {}".format(os.path.join(tempdir, "*"))
            )
        config = salt.config.minion_config(fpath)
        base = config["pillar_roots"]["base"]
        self.assertEqual(
            set(base),
            {
                os.path.join(tempdir, "a"),
                os.path.join(tempdir, "b"),
                os.path.join(tempdir, "c"),
            },
        )

    @with_tempdir()
    @pytest.mark.slow_test
    def test_minion_id_function(self, tempdir):
        minion_config = os.path.join(tempdir, "minion")

        with salt.utils.files.fopen(minion_config, "w") as fp_:
            fp_.write(
                "id_function:\n"
                "  test.echo:\n"
                "    text: hello_world\n"
                "root_dir: {}\n"
                "log_file: {}\n".format(tempdir, minion_config)
            )

        # Let's load the configuration
        config = salt.config.minion_config(minion_config)

        self.assertEqual(config["log_file"], minion_config)
        self.assertEqual(config["id"], "hello_world")

    @with_tempdir()
    @pytest.mark.slow_test
    def test_minion_id_lowercase(self, tempdir):
        """
        This tests that setting `minion_id_lowercase: True` does lower case
        the minion id. Lowercase does not operate on a static `id: KING_BOB`
        setting, or a cached id.
        """
        minion_config = os.path.join(tempdir, "minion")
        with salt.utils.files.fopen(minion_config, "w") as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
                id_function:
                  test.echo:
                    text: KING_BOB
                minion_id_caching: False
                minion_id_lowercase: True
            """
                )
            )
        config = salt.config.minion_config(minion_config)  # Load the configuration
        self.assertEqual(config["minion_id_caching"], False)  # Check the configuration
        self.assertEqual(config["minion_id_lowercase"], True)  # Check the configuration
        self.assertEqual(config["id"], "king_bob")

    @with_tempdir()
    @pytest.mark.slow_test
    def test_minion_id_remove_domain_string_positive(self, tempdir):
        """
        This tests that the values of `minion_id_remove_domain` is suppressed from a generated minion id,
        effectivly generating a hostname minion_id.
        """
        minion_config = os.path.join(tempdir, "minion")
        with salt.utils.files.fopen(minion_config, "w") as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
                id_function:
                  test.echo:
                    text: king_bob.foo.org
                minion_id_remove_domain: foo.org
                minion_id_caching: False
            """
                )
            )

        # Let's load the configuration
        config = salt.config.minion_config(minion_config)
        self.assertEqual(config["minion_id_remove_domain"], "foo.org")
        self.assertEqual(config["id"], "king_bob")

    @with_tempdir()
    @pytest.mark.slow_test
    def test_minion_id_remove_domain_string_negative(self, tempdir):
        """
        See above
        """
        minion_config = os.path.join(tempdir, "minion")
        with salt.utils.files.fopen(minion_config, "w") as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
                id_function:
                  test.echo:
                    text: king_bob.foo.org
                minion_id_remove_domain: bar.org
                minion_id_caching: False
            """
                )
            )

        config = salt.config.minion_config(minion_config)
        self.assertEqual(config["id"], "king_bob.foo.org")

    @with_tempdir()
    @pytest.mark.slow_test
    def test_minion_id_remove_domain_bool_true(self, tempdir):
        """
        See above
        """
        minion_config = os.path.join(tempdir, "minion")
        with salt.utils.files.fopen(minion_config, "w") as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
                id_function:
                  test.echo:
                    text: king_bob.foo.org
                minion_id_remove_domain: True
                minion_id_caching: False
            """
                )
            )
        config = salt.config.minion_config(minion_config)
        self.assertEqual(config["id"], "king_bob")

    @with_tempdir()
    @pytest.mark.slow_test
    def test_minion_id_remove_domain_bool_false(self, tempdir):
        """
        See above
        """
        minion_config = os.path.join(tempdir, "minion")
        with salt.utils.files.fopen(minion_config, "w") as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
                id_function:
                  test.echo:
                    text: king_bob.foo.org
                minion_id_remove_domain: False
                minion_id_caching: False
            """
                )
            )
        config = salt.config.minion_config(minion_config)
        self.assertEqual(config["id"], "king_bob.foo.org")

    @with_tempdir()
    def test_backend_rename(self, tempdir):
        """
        This tests that we successfully rename git, hg, svn, and minion to
        gitfs, hgfs, svnfs, and minionfs in the master and minion opts.
        """
        fpath = salt.utils.files.mkstemp(dir=tempdir)
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
                fileserver_backend:
                  - roots
                  - git
                  - hg
                  - svn
                  - minion
                """
                )
            )

        master_config = salt.config.master_config(fpath)
        minion_config = salt.config.minion_config(fpath)
        expected = ["roots", "gitfs", "hgfs", "svnfs", "minionfs"]

        self.assertEqual(master_config["fileserver_backend"], expected)
        self.assertEqual(minion_config["fileserver_backend"], expected)

    def test_syndic_config(self):
        minion_conf_path = self.get_config_file_path("syndic")
        master_conf_path = os.path.join(os.path.dirname(minion_conf_path), "master")
        syndic_opts = salt.config.syndic_config(master_conf_path, minion_conf_path)
        root_dir = syndic_opts["root_dir"]
        # id & pki dir are shared & so configured on the minion side
        self.assertEqual(syndic_opts["id"], "syndic")
        self.assertEqual(syndic_opts["pki_dir"], os.path.join(root_dir, "pki"))
        # the rest is configured master side
        self.assertEqual(syndic_opts["master"], "127.0.0.1")
        self.assertEqual(
            syndic_opts["sock_dir"], os.path.join(root_dir, "run", "minion")
        )
        self.assertEqual(syndic_opts["cachedir"], os.path.join(root_dir, "cache"))
        self.assertEqual(
            syndic_opts["log_file"], os.path.join(root_dir, "logs", "syndic.log")
        )
        self.assertEqual(
            syndic_opts["pidfile"], os.path.join(root_dir, "run", "syndic.pid")
        )
        # Show that the options of localclient that repub to local master
        # are not merged with syndic ones
        self.assertEqual(syndic_opts["_master_conf_file"], minion_conf_path)
        self.assertEqual(syndic_opts["_minion_conf_file"], master_conf_path)

    @with_tempfile()
    def _get_tally(self, fpath, conf_func):
        """
        This ensures that any strings which are loaded are unicode strings
        """
        tally = {}

        def _count_strings(config):
            if isinstance(config, dict):
                for key, val in config.items():
                    log.debug("counting strings in dict key: %s", key)
                    log.debug("counting strings in dict val: %s", val)
                    _count_strings(key)
                    _count_strings(val)
            elif isinstance(config, list):
                log.debug("counting strings in list: %s", config)
                for item in config:
                    _count_strings(item)
            else:
                if isinstance(config, str):
                    tally["unicode"] = tally.get("unicode", 0) + 1

        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(
                textwrap.dedent(
                    """
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
                      - baz"""
                )
            )
            if conf_func is salt.config.master_config:
                wfh.write("\n\n")
                wfh.write(
                    textwrap.dedent(
                        """
                    rest_cherrypy:
                      port: 8000
                      disable_ssl: True
                      app_path: /beacon_demo
                      app: /srv/web/html/index.html
                      static: /srv/web/static"""
                    )
                )
        config = conf_func(fpath)
        _count_strings(config)
        return tally

    def test_conf_file_strings_are_unicode_for_master(self):
        """
        This ensures that any strings which are loaded are unicode strings
        """
        # pylint: disable=no-value-for-parameter
        tally = self._get_tally(salt.config.master_config)
        # pylint: enable=no-value-for-parameter
        non_unicode = tally.get("non_unicode", [])
        self.assertEqual(len(non_unicode), 0, non_unicode)
        self.assertTrue(tally["unicode"] > 0)

    def test_conf_file_strings_are_unicode_for_minion(self):
        """
        This ensures that any strings which are loaded are unicode strings
        """
        # pylint: disable=no-value-for-parameter
        tally = self._get_tally(salt.config.minion_config)
        # pylint: enable=no-value-for-parameter
        non_unicode = tally.get("non_unicode", [])
        self.assertEqual(len(non_unicode), 0, non_unicode)
        self.assertTrue(tally["unicode"] > 0)

    def test__read_conf_file_invalid_yaml__schedule_conf(self):
        """
        If ``_schedule.conf`` is an invalid file a YAMLError will be thrown
        which should cause the invalid file to be replaced by ``_schedule.confYAMLError``
        """
        import salt.config as config

        yaml_error = MagicMock(side_effect=[salt.utils.yaml.YAMLError])
        with patch("salt.utils.files.fopen", MagicMock()), patch(
            "salt.utils.yaml.safe_load", yaml_error
        ), patch("os.replace") as mock_os:
            path = os.sep + os.path.join("some", "path", "_schedule.conf")
            config._read_conf_file(path)
            mock_os.assert_called_once_with(path, path + "YAMLError")

    def test__read_conf_file_invalid_yaml(self):
        """
        Any other file that throws a YAMLError should raise a
        SaltConfigurationError and should not trigger an os.replace
        """
        import salt.config as config

        yaml_error = MagicMock(side_effect=[salt.utils.yaml.YAMLError])
        with patch("salt.utils.files.fopen", MagicMock()), patch(
            "salt.utils.yaml.safe_load", yaml_error
        ), patch("os.replace") as mock_os:
            path = os.sep + os.path.join("etc", "salt", "minion")
            self.assertRaises(SaltConfigurationError, config._read_conf_file, path=path)
            mock_os.assert_not_called()

    def test__read_conf_file_empty_dict(self):
        """
        A config file that is not rendered as a dictionary by the YAML loader
        should also raise a SaltConfigurationError and should not trigger
        an os.replace
        """
        import salt.config as config

        mock_safe_load = MagicMock(return_value="some non dict data")
        with patch("salt.utils.files.fopen", MagicMock()), patch(
            "salt.utils.yaml.safe_load", mock_safe_load
        ), patch("os.replace") as mock_os:
            path = os.sep + os.path.join("etc", "salt", "minion")
            self.assertRaises(SaltConfigurationError, config._read_conf_file, path=path)
            mock_os.assert_not_called()

    def test__read_conf_file_integer_id(self):
        """
        An integer id should be a string
        """
        import salt.config as config

        mock_safe_load = MagicMock(return_value={"id": 1234})
        with patch("salt.utils.files.fopen", MagicMock()), patch(
            "salt.utils.yaml.safe_load", mock_safe_load
        ), patch("os.replace") as mock_os:
            path = os.sep + os.path.join("etc", "salt", "minion")
            expected = {"id": "1234"}
            result = config._read_conf_file(path)
            mock_os.assert_not_called()
            self.assertEqual(expected, result)

    # <---- Salt Cloud Configuration Tests ---------------------------------------------

    # cloud_config tests

    def test_cloud_config_double_master_path(self):
        """
        Tests passing in master_config_path and master_config kwargs.
        """
        with patch("salt.config.load_config", MagicMock(return_value={})):
            self.assertRaises(
                SaltCloudConfigError,
                salt.config.cloud_config,
                PATH,
                master_config_path="foo",
                master_config="bar",
            )

    def test_cloud_config_double_providers_path(self):
        """
        Tests passing in providers_config_path and providers_config kwargs.
        """
        with patch("salt.config.load_config", MagicMock(return_value={})):
            self.assertRaises(
                SaltCloudConfigError,
                salt.config.cloud_config,
                PATH,
                providers_config_path="foo",
                providers_config="bar",
            )

    def test_cloud_config_double_profiles_path(self):
        """
        Tests passing in profiles_config_path and profiles_config kwargs.
        """
        with patch("salt.config.load_config", MagicMock(return_value={})):
            self.assertRaises(
                SaltCloudConfigError,
                salt.config.cloud_config,
                PATH,
                profiles_config_path="foo",
                profiles_config="bar",
            )

    def test_cloud_config_providers_in_opts(self):
        """
        Tests mixing old cloud providers with pre-configured providers configurations
        using the providers_config kwarg
        """
        with patch("salt.config.load_config", MagicMock(return_value={})):
            with patch(
                "salt.config.apply_cloud_config",
                MagicMock(return_value={"providers": "foo"}),
            ):
                self.assertRaises(
                    SaltCloudConfigError,
                    salt.config.cloud_config,
                    PATH,
                    providers_config="bar",
                )

    def test_cloud_config_providers_in_opts_path(self):
        """
        Tests mixing old cloud providers with pre-configured providers configurations
        using the providers_config_path kwarg
        """
        with patch("salt.config.load_config", MagicMock(return_value={})):
            with patch(
                "salt.config.apply_cloud_config",
                MagicMock(return_value={"providers": "foo"}),
            ):
                with patch("os.path.isfile", MagicMock(return_value=True)):
                    self.assertRaises(
                        SaltCloudConfigError,
                        salt.config.cloud_config,
                        PATH,
                        providers_config_path="bar",
                    )

    def test_cloud_config_deploy_scripts_search_path(self):
        """
        Tests the contents of the 'deploy_scripts_search_path' tuple to ensure that
        the correct deploy search paths are present.

        There should be two search paths reported in the tuple: ``/etc/salt/cloud.deploy.d``
        and ``<path-to-salt-install>/salt/cloud/deploy``. The first element is usually
        ``/etc/salt/cloud.deploy.d``, but sometimes is can be something like
        ``/etc/local/salt/cloud.deploy.d``, so we'll only test against the last part of
        the path.
        """
        with patch("os.path.isdir", MagicMock(return_value=True)):
            search_paths = salt.config.cloud_config("/etc/salt/cloud").get(
                "deploy_scripts_search_path"
            )
            etc_deploy_path = "/salt/cloud.deploy.d"
            deploy_path = "/salt/cloud/deploy"
            if salt.utils.platform.is_windows():
                etc_deploy_path = "/salt\\cloud.deploy.d"
                deploy_path = "\\salt\\cloud\\deploy"

            # Check cloud.deploy.d path is the first element in the search_paths tuple
            self.assertTrue(search_paths[0].endswith(etc_deploy_path))

            # Check the second element in the search_paths tuple
            self.assertTrue(search_paths[1].endswith(deploy_path))

    # apply_cloud_config tests

    def test_apply_cloud_config_no_provider_detail_list(self):
        """
        Tests when the provider is not contained in a list of details
        """
        overrides = {"providers": {"foo": [{"bar": "baz"}]}}
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_cloud_config,
            overrides,
            defaults=DEFAULT,
        )

    def test_apply_cloud_config_no_provider_detail_dict(self):
        """
        Tests when the provider is not contained in the details dictionary
        """
        overrides = {"providers": {"foo": {"bar": "baz"}}}
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_cloud_config,
            overrides,
            defaults=DEFAULT,
        )

    def test_apply_cloud_config_success_list(self):
        """
        Tests success when valid data is passed into the function as a list
        """
        with patch(
            "salt.config.old_to_new",
            MagicMock(
                return_value={
                    "default_include": "path/to/some/cloud/conf/file",
                    "providers": {"foo": {"bar": {"driver": "foo:bar"}}},
                }
            ),
        ):
            overrides = {"providers": {"foo": [{"driver": "bar"}]}}
            ret = {
                "default_include": "path/to/some/cloud/conf/file",
                "providers": {"foo": {"bar": {"driver": "foo:bar"}}},
            }
            self.assertEqual(
                salt.config.apply_cloud_config(overrides, defaults=DEFAULT), ret
            )

    def test_apply_cloud_config_success_dict(self):
        """
        Tests success when valid data is passed into function as a dictionary
        """
        with patch(
            "salt.config.old_to_new",
            MagicMock(
                return_value={
                    "default_include": "path/to/some/cloud/conf/file",
                    "providers": {"foo": {"bar": {"driver": "foo:bar"}}},
                }
            ),
        ):
            overrides = {"providers": {"foo": {"driver": "bar"}}}
            ret = {
                "default_include": "path/to/some/cloud/conf/file",
                "providers": {"foo": {"bar": {"driver": "foo:bar"}}},
            }
            self.assertEqual(
                salt.config.apply_cloud_config(overrides, defaults=DEFAULT), ret
            )

    # apply_vm_profiles_config tests

    def test_apply_vm_profiles_config_bad_profile_format(self):
        """
        Tests passing in a bad profile format in overrides
        """
        overrides = {"foo": "bar", "conf_file": PATH}
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_vm_profiles_config,
            PATH,
            overrides,
            defaults=DEFAULT,
        )

    def test_apply_vm_profiles_config_success(self):
        """
        Tests passing in valid provider and profile config files successfully
        """
        providers = {
            "test-provider": {
                "digitalocean": {"driver": "digitalocean", "profiles": {}}
            }
        }
        overrides = {
            "test-profile": {
                "provider": "test-provider",
                "image": "Ubuntu 12.10 x64",
                "size": "512MB",
            },
            "conf_file": PATH,
        }
        ret = {
            "test-profile": {
                "profile": "test-profile",
                "provider": "test-provider:digitalocean",
                "image": "Ubuntu 12.10 x64",
                "size": "512MB",
            }
        }
        self.assertEqual(
            salt.config.apply_vm_profiles_config(
                providers, overrides, defaults=DEFAULT
            ),
            ret,
        )

    def test_apply_vm_profiles_config_extend_success(self):
        """
        Tests profile extends functionality with valid provider and profile configs
        """
        providers = {"test-config": {"ec2": {"profiles": {}, "driver": "ec2"}}}
        overrides = {
            "Amazon": {"image": "test-image-1", "extends": "dev-instances"},
            "Fedora": {"image": "test-image-2", "extends": "dev-instances"},
            "conf_file": PATH,
            "dev-instances": {"ssh_username": "test_user", "provider": "test-config"},
        }
        ret = {
            "Amazon": {
                "profile": "Amazon",
                "ssh_username": "test_user",
                "image": "test-image-1",
                "provider": "test-config:ec2",
            },
            "Fedora": {
                "profile": "Fedora",
                "ssh_username": "test_user",
                "image": "test-image-2",
                "provider": "test-config:ec2",
            },
            "dev-instances": {
                "profile": "dev-instances",
                "ssh_username": "test_user",
                "provider": "test-config:ec2",
            },
        }
        self.assertEqual(
            salt.config.apply_vm_profiles_config(
                providers, overrides, defaults=DEFAULT
            ),
            ret,
        )

    def test_apply_vm_profiles_config_extend_override_success(self):
        """
        Tests profile extends and recursively merges data elements
        """
        self.maxDiff = None
        providers = {"test-config": {"ec2": {"profiles": {}, "driver": "ec2"}}}
        overrides = {
            "Fedora": {
                "image": "test-image-2",
                "extends": "dev-instances",
                "minion": {"grains": {"stage": "experimental"}},
            },
            "conf_file": PATH,
            "dev-instances": {
                "ssh_username": "test_user",
                "provider": "test-config",
                "minion": {"grains": {"role": "webserver"}},
            },
        }
        ret = {
            "Fedora": {
                "profile": "Fedora",
                "ssh_username": "test_user",
                "image": "test-image-2",
                "minion": {"grains": {"role": "webserver", "stage": "experimental"}},
                "provider": "test-config:ec2",
            },
            "dev-instances": {
                "profile": "dev-instances",
                "ssh_username": "test_user",
                "minion": {"grains": {"role": "webserver"}},
                "provider": "test-config:ec2",
            },
        }
        self.assertEqual(
            salt.config.apply_vm_profiles_config(
                providers, overrides, defaults=DEFAULT
            ),
            ret,
        )

    # apply_cloud_providers_config tests

    def test_apply_cloud_providers_config_same_providers(self):
        """
        Tests when two providers are given with the same provider name
        """
        overrides = {
            "my-dev-envs": [
                {
                    "id": "ABCDEFGHIJKLMNOP",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                },
                {
                    "apikey": "abcdefghijklmnopqrstuvwxyz",
                    "password": "supersecret",
                    "driver": "ec2",
                },
            ],
            "conf_file": PATH,
        }
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_cloud_providers_config,
            overrides,
            DEFAULT,
        )

    def test_apply_cloud_providers_config_extend(self):
        """
        Tests the successful extension of a cloud provider
        """
        overrides = {
            "my-production-envs": [
                {
                    "extends": "my-dev-envs:ec2",
                    "location": "us-east-1",
                    "user": "ec2-user@mycorp.com",
                }
            ],
            "my-dev-envs": [
                {
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "user@mycorp.com",
                    "location": "ap-southeast-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                },
                {
                    "apikey": "abcdefghijklmnopqrstuvwxyz",
                    "password": "supersecret",
                    "driver": "linode",
                },
                {
                    "id": "a-tencentcloud-id",
                    "key": "a-tencentcloud-key",
                    "location": "ap-guangzhou",
                    "driver": "tencentcloud",
                },
            ],
            "conf_file": PATH,
        }
        ret = {
            "my-production-envs": {
                "ec2": {
                    "profiles": {},
                    "location": "us-east-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "ec2-user@mycorp.com",
                }
            },
            "my-dev-envs": {
                "linode": {
                    "apikey": "abcdefghijklmnopqrstuvwxyz",
                    "password": "supersecret",
                    "profiles": {},
                    "driver": "linode",
                },
                "tencentcloud": {
                    "id": "a-tencentcloud-id",
                    "key": "a-tencentcloud-key",
                    "location": "ap-guangzhou",
                    "profiles": {},
                    "driver": "tencentcloud",
                },
                "ec2": {
                    "profiles": {},
                    "location": "ap-southeast-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "user@mycorp.com",
                },
            },
        }
        self.assertEqual(
            ret, salt.config.apply_cloud_providers_config(overrides, defaults=DEFAULT)
        )

    def test_apply_cloud_providers_config_extend_multiple(self):
        """
        Tests the successful extension of two cloud providers
        """
        overrides = {
            "my-production-envs": [
                {
                    "extends": "my-dev-envs:ec2",
                    "location": "us-east-1",
                    "user": "ec2-user@mycorp.com",
                },
                {
                    "password": "new-password",
                    "extends": "my-dev-envs:linode",
                    "location": "Salt Lake City",
                },
                {
                    "extends": "my-dev-envs:tencentcloud",
                    "id": "new-id",
                    "key": "new-key",
                    "location": "ap-beijing",
                },
            ],
            "my-dev-envs": [
                {
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "user@mycorp.com",
                    "location": "ap-southeast-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                },
                {
                    "apikey": "abcdefghijklmnopqrstuvwxyz",
                    "password": "supersecret",
                    "driver": "linode",
                },
                {
                    "id": "the-tencentcloud-id",
                    "location": "ap-beijing",
                    "key": "the-tencentcloud-key",
                    "driver": "tencentcloud",
                },
            ],
            "conf_file": PATH,
        }
        ret = {
            "my-production-envs": {
                "linode": {
                    "apikey": "abcdefghijklmnopqrstuvwxyz",
                    "profiles": {},
                    "location": "Salt Lake City",
                    "driver": "linode",
                    "password": "new-password",
                },
                "ec2": {
                    "user": "ec2-user@mycorp.com",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                    "id": "ABCDEFGHIJKLMNOP",
                    "profiles": {},
                    "location": "us-east-1",
                },
                "tencentcloud": {
                    "id": "new-id",
                    "key": "new-key",
                    "location": "ap-beijing",
                    "profiles": {},
                    "driver": "tencentcloud",
                },
            },
            "my-dev-envs": {
                "linode": {
                    "apikey": "abcdefghijklmnopqrstuvwxyz",
                    "password": "supersecret",
                    "profiles": {},
                    "driver": "linode",
                },
                "ec2": {
                    "profiles": {},
                    "user": "user@mycorp.com",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                    "id": "ABCDEFGHIJKLMNOP",
                    "location": "ap-southeast-1",
                },
                "tencentcloud": {
                    "id": "the-tencentcloud-id",
                    "key": "the-tencentcloud-key",
                    "location": "ap-beijing",
                    "profiles": {},
                    "driver": "tencentcloud",
                },
            },
        }
        self.assertEqual(
            ret, salt.config.apply_cloud_providers_config(overrides, defaults=DEFAULT)
        )

    def test_apply_cloud_providers_config_extends_bad_alias(self):
        """
        Tests when the extension contains an alias not found in providers list
        """
        overrides = {
            "my-production-envs": [
                {
                    "extends": "test-alias:ec2",
                    "location": "us-east-1",
                    "user": "ec2-user@mycorp.com",
                }
            ],
            "my-dev-envs": [
                {
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "user@mycorp.com",
                    "location": "ap-southeast-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                }
            ],
            "conf_file": PATH,
        }
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_cloud_providers_config,
            overrides,
            DEFAULT,
        )

    def test_apply_cloud_providers_config_extends_bad_provider(self):
        """
        Tests when the extension contains a provider not found in providers list
        """
        overrides = {
            "my-production-envs": [
                {
                    "extends": "my-dev-envs:linode",
                    "location": "us-east-1",
                    "user": "ec2-user@mycorp.com",
                },
                {
                    "extends": "my-dev-envs:tencentcloud",
                    "location": "ap-shanghai",
                    "id": "the-tencentcloud-id",
                },
            ],
            "my-dev-envs": [
                {
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "user@mycorp.com",
                    "location": "ap-southeast-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "ec2",
                }
            ],
            "conf_file": PATH,
        }
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_cloud_providers_config,
            overrides,
            DEFAULT,
        )

    def test_apply_cloud_providers_config_extends_no_provider(self):
        """
        Tests when no provider is supplied in the extends statement
        """
        overrides = {
            "my-production-envs": [
                {
                    "extends": "my-dev-envs",
                    "location": "us-east-1",
                    "user": "ec2-user@mycorp.com",
                },
                {
                    "extends": "my-dev-envs:tencentcloud",
                    "location": "ap-shanghai",
                    "id": "the-tencentcloud-id",
                },
            ],
            "my-dev-envs": [
                {
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "user@mycorp.com",
                    "location": "ap-southeast-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "linode",
                }
            ],
            "conf_file": PATH,
        }
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_cloud_providers_config,
            overrides,
            DEFAULT,
        )

    def test_apply_cloud_providers_extends_not_in_providers(self):
        """
        Tests when extends is not in the list of providers
        """
        overrides = {
            "my-production-envs": [
                {
                    "extends": "my-dev-envs ec2",
                    "location": "us-east-1",
                    "user": "ec2-user@mycorp.com",
                }
            ],
            "my-dev-envs": [
                {
                    "id": "ABCDEFGHIJKLMNOP",
                    "user": "user@mycorp.com",
                    "location": "ap-southeast-1",
                    "key": "supersecretkeysupersecretkey",
                    "driver": "linode",
                },
                {
                    "id": "a-tencentcloud-id",
                    "key": "a-tencentcloud-key",
                    "location": "ap-guangzhou",
                    "driver": "tencentcloud",
                },
            ],
            "conf_file": PATH,
        }
        self.assertRaises(
            SaltCloudConfigError,
            salt.config.apply_cloud_providers_config,
            overrides,
            DEFAULT,
        )

    # is_provider_configured tests

    def test_is_provider_configured_no_alias(self):
        """
        Tests when provider alias is not in opts
        """
        opts = {"providers": "test"}
        provider = "foo:bar"
        self.assertFalse(salt.config.is_provider_configured(opts, provider))

    def test_is_provider_configured_no_driver(self):
        """
        Tests when provider driver is not in opts
        """
        opts = {"providers": {"foo": "baz"}}
        provider = "foo:bar"
        self.assertFalse(salt.config.is_provider_configured(opts, provider))

    def test_is_provider_configured_key_is_none(self):
        """
        Tests when a required configuration key is not set
        """
        opts = {"providers": {"foo": {"bar": {"api_key": None}}}}
        provider = "foo:bar"
        self.assertFalse(
            salt.config.is_provider_configured(
                opts, provider, required_keys=("api_key",)
            )
        )

    def test_is_provider_configured_success(self):
        """
        Tests successful cloud provider configuration
        """
        opts = {"providers": {"foo": {"bar": {"api_key": "baz"}}}}
        provider = "foo:bar"
        ret = {"api_key": "baz"}
        self.assertEqual(
            salt.config.is_provider_configured(
                opts, provider, required_keys=("api_key",)
            ),
            ret,
        )

    def test_is_provider_configured_multiple_driver_not_provider(self):
        """
        Tests when the drive is not the same as the provider when
        searching through multiple providers
        """
        opts = {"providers": {"foo": {"bar": {"api_key": "baz"}}}}
        provider = "foo"
        self.assertFalse(salt.config.is_provider_configured(opts, provider))

    def test_is_provider_configured_multiple_key_is_none(self):
        """
        Tests when a required configuration key is not set when
        searching through multiple providers
        """
        opts = {"providers": {"foo": {"bar": {"api_key": None}}}}
        provider = "bar"
        self.assertFalse(
            salt.config.is_provider_configured(
                opts, provider, required_keys=("api_key",)
            )
        )

    def test_is_provider_configured_multiple_success(self):
        """
        Tests successful cloud provider configuration when searching
        through multiple providers
        """
        opts = {"providers": {"foo": {"bar": {"api_key": "baz"}}}}
        provider = "bar"
        ret = {"api_key": "baz"}
        self.assertEqual(
            salt.config.is_provider_configured(
                opts, provider, required_keys=("api_key",)
            ),
            ret,
        )

    # other cloud configuration tests

    @pytest.mark.skip_on_windows(
        reason="You can't set an environment dynamically in Windows"
    )
    @with_tempdir()
    def test_load_cloud_config_from_environ_var(self, tempdir):
        env_root_dir = os.path.join(tempdir, "foo", "env")
        os.makedirs(env_root_dir)
        env_fpath = os.path.join(env_root_dir, "config-env")

        with salt.utils.files.fopen(env_fpath, "w") as fp_:
            fp_.write(f"root_dir: {env_root_dir}\nlog_file: {env_fpath}\n")

        with patched_environ(SALT_CLOUD_CONFIG=env_fpath):
            # Should load from env variable, not the default configuration file
            config = salt.config.cloud_config("/etc/salt/cloud")
            self.assertEqual(config["log_file"], env_fpath)

        root_dir = os.path.join(tempdir, "foo", "bar")
        os.makedirs(root_dir)
        fpath = os.path.join(root_dir, "config")
        with salt.utils.files.fopen(fpath, "w") as fp_:
            fp_.write(f"root_dir: {root_dir}\nlog_file: {fpath}\n")
        # Let's set the environment variable, yet, since the configuration
        # file path is not the default one, i.e., the user has passed an
        # alternative configuration file form the CLI parser, the
        # environment variable will be ignored.
        with patched_environ(SALT_CLOUD_CONFIG=env_fpath):
            config = salt.config.cloud_config(fpath)
            self.assertEqual(config["log_file"], fpath)

    @with_tempdir()
    def test_deploy_search_path_as_string(self, temp_conf_dir):
        config_file_path = os.path.join(temp_conf_dir, "cloud")
        deploy_dir_path = os.path.join(temp_conf_dir, "test-deploy.d")
        for directory in (temp_conf_dir, deploy_dir_path):
            if not os.path.isdir(directory):
                os.makedirs(directory)

        default_config = salt.config.cloud_config(config_file_path)
        default_config["deploy_scripts_search_path"] = deploy_dir_path
        with salt.utils.files.fopen(config_file_path, "w") as cfd:
            salt.utils.yaml.safe_dump(default_config, cfd, default_flow_style=False)

        default_config = salt.config.cloud_config(config_file_path)

        # Our custom deploy scripts path was correctly added to the list
        self.assertIn(deploy_dir_path, default_config["deploy_scripts_search_path"])

        # And it's even the first occurrence as it should
        self.assertEqual(
            deploy_dir_path, default_config["deploy_scripts_search_path"][0]
        )

    def test_includes_load(self):
        """
        Tests that cloud.{providers,profiles}.d directories are loaded, even if not
        directly passed in through path
        """
        config_file = self.get_config_file_path("cloud")
        log.debug("Cloud config file path: %s", config_file)
        self.assertTrue(os.path.exists(config_file), f"{config_file} does not exist")
        config = salt.config.cloud_config(config_file)
        self.assertIn("providers", config)
        self.assertIn("ec2-config", config["providers"])
        self.assertIn("ec2-test", config["profiles"])

    # <---- Salt Cloud Configuration Tests ---------------------------------------------

    def test_include_config_without_errors(self):
        """
        Tests that include_config function returns valid configuration
        """
        include_file = "minion.d/my.conf"
        config_path = "/etc/salt/minion"
        config_opts = {"id": "myminion.example.com"}

        with patch("glob.glob", MagicMock(return_value=include_file)):
            with patch(
                "salt.config._read_conf_file", MagicMock(return_value=config_opts)
            ):
                configuration = salt.config.include_config(
                    include_file, config_path, verbose=False
                )

        self.assertEqual(config_opts, configuration)

    def test_include_config_with_errors(self):
        """
        Tests that include_config function returns valid configuration even on errors
        """
        include_file = "minion.d/my.conf"
        config_path = "/etc/salt/minion"
        config_opts = {}

        with patch("glob.glob", MagicMock(return_value=include_file)):
            with patch("salt.config._read_conf_file", _salt_configuration_error):
                configuration = salt.config.include_config(
                    include_file, config_path, verbose=False
                )

        self.assertEqual(config_opts, configuration)

    def test_include_config_with_errors_exit(self):
        """
        Tests that include_config exits on errors
        """
        include_file = "minion.d/my.conf"
        config_path = "/etc/salt/minion"

        with patch("glob.glob", MagicMock(return_value=include_file)):
            with patch("salt.config._read_conf_file", _salt_configuration_error):
                with self.assertRaises(SystemExit):
                    salt.config.include_config(
                        include_file,
                        config_path,
                        verbose=False,
                        exit_on_config_errors=True,
                    )

    @staticmethod
    def _get_defaults(**kwargs):
        ret = {
            "saltenv": kwargs.pop("saltenv", None),
            "id": "test",
            "cachedir": "/A",
            "sock_dir": "/B",
            "root_dir": "/C",
            "fileserver_backend": "roots",
            "open_mode": False,
            "auto_accept": False,
            "file_roots": {},
            "pillar_roots": {},
            "file_ignore_glob": [],
            "file_ignore_regex": [],
            "worker_threads": 5,
            "hash_type": "sha256",
            "log_file": "foo.log",
        }
        ret.update(kwargs)
        return ret

    def test_apply_config(self):
        """
        Ensure that the environment and saltenv options work properly
        """
        with patch.object(
            salt.config, "_adjust_log_file_override", Mock()
        ), patch.object(salt.config, "_update_ssl_config", Mock()), patch.object(
            salt.config, "_update_discovery_config", Mock()
        ):
            # MASTER CONFIG

            # Ensure that environment overrides saltenv when saltenv not
            # explicitly passed.
            defaults = self._get_defaults(environment="foo")
            ret = salt.config.apply_master_config(defaults=defaults)
            self.assertEqual(ret["environment"], "foo")
            self.assertEqual(ret["saltenv"], "foo")

            # Ensure that environment overrides saltenv when saltenv not
            # explicitly passed.
            defaults = self._get_defaults(environment="foo", saltenv="bar")
            ret = salt.config.apply_master_config(defaults=defaults)
            self.assertEqual(ret["environment"], "bar")
            self.assertEqual(ret["saltenv"], "bar")

            # If environment was not explicitly set, it should not be in the
            # opts at all.
            defaults = self._get_defaults()
            ret = salt.config.apply_master_config(defaults=defaults)
            self.assertNotIn("environment", ret)
            self.assertEqual(ret["saltenv"], None)

            # Same test as above but with saltenv explicitly set
            defaults = self._get_defaults(saltenv="foo")
            ret = salt.config.apply_master_config(defaults=defaults)
            self.assertNotIn("environment", ret)
            self.assertEqual(ret["saltenv"], "foo")

            # Test config to verify that `keep_acl_in_token` is forced to True
            # when `rest` is present as driver in the `external_auth` config.
            overrides = {"external_auth": {"rest": {"^url": "http://test_url/rest"}}}
            ret = salt.config.apply_master_config(overrides=overrides)
            self.assertTrue(ret["keep_acl_in_token"])

            # MINION CONFIG

            # Ensure that environment overrides saltenv when saltenv not
            # explicitly passed.
            defaults = self._get_defaults(environment="foo")
            ret = salt.config.apply_minion_config(defaults=defaults)
            self.assertEqual(ret["environment"], "foo")
            self.assertEqual(ret["saltenv"], "foo")

            # Ensure that environment overrides saltenv when saltenv not
            # explicitly passed.
            defaults = self._get_defaults(environment="foo", saltenv="bar")
            ret = salt.config.apply_minion_config(defaults=defaults)
            self.assertEqual(ret["environment"], "bar")
            self.assertEqual(ret["saltenv"], "bar")

            # If environment was not explicitly set, it should not be in the
            # opts at all.
            defaults = self._get_defaults()
            ret = salt.config.apply_minion_config(defaults=defaults)
            self.assertNotIn("environment", ret)
            self.assertEqual(ret["saltenv"], None)

            # Same test as above but with saltenv explicitly set
            defaults = self._get_defaults(saltenv="foo")
            ret = salt.config.apply_minion_config(defaults=defaults)
            self.assertNotIn("environment", ret)
            self.assertEqual(ret["saltenv"], "foo")

    @with_tempfile()
    def test_minion_config_role_master(self, fpath):
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write("root_dir: /\nkey_logfile: key\n")
        with patch("salt.config.apply_sdb") as apply_sdb_mock, patch(
            "salt.config._validate_opts"
        ) as validate_opts_mock:
            config = salt.config.minion_config(fpath, role="master")
            apply_sdb_mock.assert_not_called()

            validate_opts_mock.assert_not_called()
        self.assertEqual(config["__role"], "master")

    @with_tempfile()
    def test_mminion_config_cache_path(self, fpath):
        cachedir = os.path.abspath("/path/to/master/cache")
        overrides = {}

        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(f"root_dir: /\nkey_logfile: key\ncachedir: {cachedir}")
        config = salt.config.mminion_config(fpath, overrides)
        self.assertEqual(config["__role"], "master")
        self.assertEqual(config["cachedir"], cachedir)

    @with_tempfile()
    def test_mminion_config_cache_path_overrides(self, fpath):
        cachedir = os.path.abspath("/path/to/master/cache")
        overrides = {"cachedir": cachedir}

        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write("root_dir: /\nkey_logfile: key\n")
        config = salt.config.mminion_config(fpath, overrides)
        self.assertEqual(config["__role"], "master")
        self.assertEqual(config["cachedir"], cachedir)


class APIConfigTestCase(DefaultConfigsBase, TestCase):
    """
    TestCase for the api_config function in salt.config.__init__.py
    """

    def setUp(self):
        # Copy DEFAULT_API_OPTS to restore after the test
        self.default_api_opts = salt.config.DEFAULT_API_OPTS.copy()

    def tearDown(self):
        # Reset DEFAULT_API_OPTS settings as to not interfere with other unit tests
        salt.config.DEFAULT_API_OPTS = self.default_api_opts

    def test_api_config_log_file_values(self):
        """
        Tests the opts value of the 'log_file' after running through the
        various default dict updates. 'log_file' should be updated to match
        the DEFAULT_API_OPTS 'api_logfile' value.
        """
        with patch(
            "salt.config.client_config",
            MagicMock(return_value=self.mock_master_default_opts),
        ):
            expected = "{}/var/log/salt/api".format(
                RUNTIME_VARS.TMP_ROOT_DIR if RUNTIME_VARS.TMP_ROOT_DIR != "/" else ""
            )
            if salt.utils.platform.is_windows():
                expected = f"{RUNTIME_VARS.TMP_ROOT_DIR}\\var\\log\\salt\\api"

            ret = salt.config.api_config("/some/fake/path")
            self.assertEqual(ret["log_file"], expected)

    def test_api_config_pidfile_values(self):
        """
        Tests the opts value of the 'pidfile' after running through the
        various default dict updates. 'pidfile' should be updated to match
        the DEFAULT_API_OPTS 'api_pidfile' value.
        """
        with patch(
            "salt.config.client_config",
            MagicMock(return_value=self.mock_master_default_opts),
        ):
            expected = "{}/var/run/salt-api.pid".format(
                RUNTIME_VARS.TMP_ROOT_DIR if RUNTIME_VARS.TMP_ROOT_DIR != "/" else ""
            )
            if salt.utils.platform.is_windows():
                expected = "{}\\var\\run\\salt-api.pid".format(
                    RUNTIME_VARS.TMP_ROOT_DIR
                )

            ret = salt.config.api_config("/some/fake/path")
            self.assertEqual(ret["pidfile"], expected)

    def test_master_config_file_overrides_defaults(self):
        """
        Tests the opts value of the api config values after running through the
        various default dict updates that should be overridden by settings in
        the user's master config file.
        """
        foo_dir = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, "foo/bar/baz")
        hello_dir = os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, "hello/world")
        if salt.utils.platform.is_windows():
            foo_dir = "c:\\{}".format(foo_dir.replace("/", "\\"))
            hello_dir = "c:\\{}".format(hello_dir.replace("/", "\\"))

        mock_master_config = {
            "api_pidfile": foo_dir,
            "api_logfile": hello_dir,
            "rest_timeout": 5,
        }
        mock_master_config.update(self.mock_master_default_opts.copy())

        with patch(
            "salt.config.client_config", MagicMock(return_value=mock_master_config)
        ):
            ret = salt.config.api_config("/some/fake/path")
            self.assertEqual(ret["rest_timeout"], 5)
            self.assertEqual(ret["api_pidfile"], foo_dir)
            self.assertEqual(ret["pidfile"], foo_dir)
            self.assertEqual(ret["api_logfile"], hello_dir)
            self.assertEqual(ret["log_file"], hello_dir)

    def test_api_config_prepend_root_dirs_return(self):
        """
        Tests the opts value of the api_logfile, log_file, api_pidfile, and pidfile
        when a custom root directory is used. This ensures that each of these
        values is present in the list of opts keys that should have the root_dir
        prepended when the api_config function returns the opts dictionary.
        """
        mock_log = "/mock/root/var/log/salt/api"
        mock_pid = "/mock/root/var/run/salt-api.pid"

        mock_master_config = self.mock_master_default_opts.copy()
        mock_master_config["root_dir"] = "/mock/root/"

        if salt.utils.platform.is_windows():
            mock_log = "c:\\mock\\root\\var\\log\\salt\\api"
            mock_pid = "c:\\mock\\root\\var\\run\\salt-api.pid"
            mock_master_config["root_dir"] = "c:\\mock\\root"

        with patch(
            "salt.config.client_config", MagicMock(return_value=mock_master_config)
        ):
            ret = salt.config.api_config("/some/fake/path")
            self.assertEqual(ret["api_logfile"], mock_log)
            self.assertEqual(ret["log_file"], mock_log)
            self.assertEqual(ret["api_pidfile"], mock_pid)
            self.assertEqual(ret["pidfile"], mock_pid)
