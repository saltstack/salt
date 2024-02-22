"""
These only test the provider selection and verification logic, they do not init
any remotes.
"""

import logging
import pathlib

## import os
import tempfile

import pytest
from saltfactories.utils import random_string

import salt.ext.tornado.ioloop
import salt.fileserver.gitfs
import salt.utils.files
import salt.utils.gitfs
import salt.utils.path
import salt.utils.platform
from salt.utils.immutabletypes import freeze
from salt.utils.verify import verify_env

## from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def _create_old_tempdir():
    pathlib.Path(RUNTIME_VARS.TMP).mkdir(exist_ok=True, parents=True)


@pytest.fixture(scope="session", autouse=True)
def bridge_pytest_and_runtests(
    reap_stray_processes,
    salt_factories,
    salt_syndic_master_factory,
    salt_syndic_factory,
    salt_master_factory,
    salt_minion_factory,
    salt_sub_minion_factory,
    sshd_config_dir,
):
    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["master"] = freeze(salt_master_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["minion"] = freeze(salt_minion_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["sub_minion"] = freeze(salt_sub_minion_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic_master"] = freeze(
        salt_syndic_master_factory.config
    )
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic"] = freeze(salt_syndic_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["client_config"] = freeze(
        salt.config.client_config(salt_master_factory.config["conf_file"])
    )

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_ROOT_DIR = str(salt_factories.root_dir.resolve())
    RUNTIME_VARS.TMP_CONF_DIR = pathlib.PurePath(
        salt_master_factory.config["conf_file"]
    ).parent
    RUNTIME_VARS.TMP_MINION_CONF_DIR = pathlib.PurePath(
        salt_minion_factory.config["conf_file"]
    ).parent
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = pathlib.PurePath(
        salt_sub_minion_factory.config["conf_file"]
    ).parent
    RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR = pathlib.PurePath(
        salt_syndic_master_factory.config["conf_file"]
    ).parent
    RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR = pathlib.PurePath(
        salt_syndic_factory.config["conf_file"]
    ).parent
    RUNTIME_VARS.TMP_SSH_CONF_DIR = str(sshd_config_dir)


## @pytest.fixture(scope="session", autouse=True)
## def get_tmp_dir(tmp_path):
##     dirpath = tmp_path / "git_test"
##     dirpath.mkdir(parents=True)
##     return dirpath
##
##     ## dirpath.cleanup()


def _clear_instance_map():
    try:
        del salt.utils.gitfs.GitFS.instance_map[
            salt.ext.tornado.ioloop.IOLoop.current()
        ]
    except KeyError:
        pass


class AdaptedConfigurationTestCaseMixin:

    ## __slots__ = ()

    @staticmethod
    def get_temp_config(config_for, **config_overrides):
        log.debug(
            f"DGM AdaptedConfigurationTestCaseMixin get_temp_config, config_for '{config_for}, config_overrides '{config_overrides}', runtime_vars tmp '{RUNTIME_VARS.TMP}', user '{RUNTIME_VARS.RUNNING_TESTS_USER}'"
        )

        rootdir = config_overrides.get("root_dir", RUNTIME_VARS.TMP)

        if not pathlib.Path(rootdir).exists():
            log.debug(
                f"DGM AdaptedConfigurationTestCaseMixin get_temp_config, oddity runtime_vars '{RUNTIME_VARS.TMP}' should already exist"
            )
            pathlib.Path(RUNTIME_VARS.TMP).mkdir(exist_ok=True, parents=True)

        rootdir = config_overrides.get("root_dir", RUNTIME_VARS.TMP)
        conf_dir = config_overrides.pop(
            "conf_dir", pathlib.PurePath(rootdir).joinpath("conf")
        )
        for key in ("cachedir", "pki_dir", "sock_dir"):
            if key not in config_overrides:
                config_overrides[key] = key
        if "log_file" not in config_overrides:
            config_overrides["log_file"] = f"logs/{config_for}.log".format()
        if "user" not in config_overrides:
            config_overrides["user"] = RUNTIME_VARS.RUNNING_TESTS_USER
        config_overrides["root_dir"] = rootdir

        cdict = AdaptedConfigurationTestCaseMixin.get_config(
            config_for, from_scratch=True
        )

        if config_for in ("master", "client_config"):
            rdict = salt.config.apply_master_config(config_overrides, cdict)
        if config_for == "minion":
            minion_id = (
                config_overrides.get("id")
                or config_overrides.get("minion_id")
                or cdict.get("id")
                or cdict.get("minion_id")
                or random_string("temp-minion-")
            )
            config_overrides["minion_id"] = config_overrides["id"] = minion_id
            rdict = salt.config.apply_minion_config(
                config_overrides, cdict, cache_minion_id=False, minion_id=minion_id
            )

        verify_env(
            [
                pathlib.PurePath(rdict["pki_dir"]).joinpath("minions"),
                pathlib.PurePath(rdict["pki_dir"]).joinpath("minions_pre"),
                pathlib.PurePath(rdict["pki_dir"]).joinpath("minions_rejected"),
                pathlib.PurePath(rdict["pki_dir"]).joinpath("minions_denied"),
                pathlib.PurePath(rdict["cachedir"]).joinpath("jobs"),
                pathlib.PurePath(rdict["cachedir"]).joinpath("tokens"),
                pathlib.PurePath(rdict["root_dir"]).joinpath("cache", "tokens"),
                pathlib.PurePath(rdict["pki_dir"]).joinpath("accepted"),
                pathlib.PurePath(rdict["pki_dir"]).joinpath("rejected"),
                pathlib.PurePath(rdict["pki_dir"]).joinpath("pending"),
                pathlib.PurePath(rdict["log_file"]).parent,
                rdict["sock_dir"],
                conf_dir,
            ],
            RUNTIME_VARS.RUNNING_TESTS_USER,
            root_dir=rdict["root_dir"],
        )

        rdict["conf_file"] = pathlib.PurePath(conf_dir).joinpath(config_for)
        with salt.utils.files.fopen(rdict["conf_file"], "w") as wfh:
            salt.utils.yaml.safe_dump(rdict, wfh, default_flow_style=False)
        return rdict

    @staticmethod
    def get_config(config_for, from_scratch=False):
        log.debug(
            f"DGM AdaptedConfigurationTestCaseMixin get_config, config_for '{config_for}, from_scratch '{from_scratch}', runtime runtime_configs '{RUNTIME_VARS.RUNTIME_CONFIGS}'"
        )

        if from_scratch:
            if config_for in ("master", "syndic_master", "mm_master", "mm_sub_master"):
                return salt.config.master_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path(config_for)
                )
            elif config_for in ("minion", "sub_minion"):
                return salt.config.minion_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path(config_for),
                    cache_minion_id=False,
                )
            elif config_for in ("syndic",):
                return salt.config.syndic_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path(config_for),
                    AdaptedConfigurationTestCaseMixin.get_config_file_path("minion"),
                )
            elif config_for == "client_config":
                return salt.config.client_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path("master")
                )

        if config_for not in RUNTIME_VARS.RUNTIME_CONFIGS:
            if config_for in ("master", "syndic_master", "mm_master", "mm_sub_master"):
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.master_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            config_for
                        )
                    )
                )
            elif config_for in ("minion", "sub_minion"):
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.minion_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            config_for
                        )
                    )
                )
            elif config_for in ("syndic",):
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.syndic_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            config_for
                        ),
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            "minion"
                        ),
                    )
                )
            elif config_for == "client_config":
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.client_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path("master")
                    )
                )
        return RUNTIME_VARS.RUNTIME_CONFIGS[config_for]

    @property
    def config_dir(self):
        return RUNTIME_VARS.TMP_CONF_DIR

    def get_config_dir(self):
        log.warning("Use the config_dir attribute instead of calling get_config_dir()")
        return self.config_dir

    @staticmethod
    def get_config_file_path(filename):
        if filename == "master":
            return pathlib.PurePath(RUNTIME_VARS.TMP_CONF_DIR).joinpath(filename)
        if filename == "minion":
            return pathlib.PurePath(RUNTIME_VARS.TMP_MINION_CONF_DIR).joinpath(filename)
        if filename == "syndic_master":
            return pathlib.PurePath(RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR).joinpath(
                "master"
            )
        if filename == "syndic":
            return pathlib.PurePath(RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR).joinpath(
                "minion"
            )
        if filename == "sub_minion":
            return pathlib.PurePath(RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR).joinpath(
                "minion"
            )
        if filename == "mm_master":
            return pathlib.PurePath(RUNTIME_VARS.TMP_MM_CONF_DIR).joinpath("master")
        if filename == "mm_sub_master":
            return pathlib.PurePath(RUNTIME_VARS.TMP_MM_SUB_CONF_DIR).joinpath("master")
        if filename == "mm_minion":
            return pathlib.PurePath(RUNTIME_VARS.TMP_MM_MINION_CONF_DIR).joinpath(
                "minion"
            )
        if filename == "mm_sub_minion":
            return pathlib.PurePath(RUNTIME_VARS.TMP_MM_SUB_MINION_CONF_DIR).joinpath(
                "minion"
            )
        return pathlib.PurePath(RUNTIME_VARS.TMP_CONF_DIR).joinpath(filename)

    @property
    def master_opts(self):
        """
        Return the options used for the master
        """
        return self.get_config("master")

    @property
    def minion_opts(self):
        """
        Return the options used for the minion
        """
        return self.get_config("minion")

    @property
    def sub_minion_opts(self):
        """
        Return the options used for the sub_minion
        """
        return self.get_config("sub_minion")


class TestGitBase(AdaptedConfigurationTestCaseMixin):
    """
    mocked GitFS provider leveraging tmp_path
    """

    def __init__(
        self,
    ):
        # TBD DGM need to fixup using tmp_path fixture
        ## self._tmp_dir = pathlib.Path(tmp_path / "git_test").mkdir(exist_ok=True, parents=True)
        ## tmp_name = str(self._tmp_dir)
        self._tmp_dir = tempfile.TemporaryDirectory()
        tmp_name = self._tmp_dir.name

        class MockedProvider(
            salt.utils.gitfs.GitProvider
        ):  # pylint: disable=abstract-method
            def __init__(
                self,
                opts,
                remote,
                per_remote_defaults,
                per_remote_only,
                override_params,
                cache_root,
                role="gitfs",
            ):
                self.provider = "mocked"
                self.fetched = False
                super().__init__(
                    opts,
                    remote,
                    per_remote_defaults,
                    per_remote_only,
                    override_params,
                    cache_root,
                    role,
                )

            def init_remote(self):
                self.gitdir = salt.utils.path.join(tmp_name, ".git")
                self.repo = True
                new = False
                return new

            def envs(self):
                return ["base"]

            def fetch(self):
                self.fetched = True

        # Clear the instance map so that we make sure to create a new instance
        # for this test class.
        _clear_instance_map()

        git_providers = {
            "mocked": MockedProvider,
        }
        gitfs_remotes = ["file://repo1.git", {"file://repo2.git": [{"name": "repo2"}]}]

        self.opts = self.get_temp_config(
            "master", gitfs_remotes=gitfs_remotes, verified_gitfs_provider="mocked"
        )
        self.main_class = salt.utils.gitfs.GitFS(
            self.opts,
            self.opts["gitfs_remotes"],
            per_remote_overrides=salt.fileserver.gitfs.PER_REMOTE_OVERRIDES,
            per_remote_only=salt.fileserver.gitfs.PER_REMOTE_ONLY,
            git_providers=git_providers,
        )

    def tearDown(self):
        # Providers are preserved with GitFS's instance_map
        for remote in self.main_class.remotes:
            remote.fetched = False
        del self.main_class
        ## self._tmp_dir.cleanup()


@pytest.fixture
def main_class(tmp_path):
    test_git_base = TestGitBase()
    log.debug(f"DGM main_class, test_git_base '{dir(test_git_base)}'")
    log.debug(
        f"DGM main_class, test_git_base.main_class '{dir(test_git_base.main_class)}'"
    )
    yield test_git_base.main_class

    test_git_base.tearDown()


def test_update_all(main_class):
    log.debug(f"DGM test_update_all, main_class '{dir(main_class)}'")
    main_class.update()
    assert len(main_class.remotes) == 2, "Wrong number of remotes"
    assert main_class.remotes[0].fetched
    assert main_class.remotes[1].fetched


def test_update_by_name(main_class):
    main_class.update("repo2")
    assert len(main_class.remotes) == 2, "Wrong number of remotes"
    assert not main_class.remotes[0].fetched
    assert main_class.remotes[1].fetched


def test_update_by_id_and_name(main_class):
    main_class.update([("file://repo1.git", None)])
    assert len(main_class.remotes) == 2, "Wrong number of remotes"
    assert main_class.remotes[0].fetched
    assert not main_class.remotes[1].fetched


def test_get_cachedir_basename(main_class):
    assert main_class.remotes[0].get_cache_basename() == "_"
    assert main_class.remotes[1].get_cache_basename() == "_"


def test_git_provider_mp_lock(main_class):
    """
    Check that lock is released after provider.lock()
    """
    provider = main_class.remotes[0]
    provider.lock()
    # check that lock has been released
    assert provider._master_lock.acquire(timeout=5)
    provider._master_lock.release()


def test_git_provider_mp_clear_lock(main_class):
    """
    Check that lock is released after provider.clear_lock()
    """
    provider = main_class.remotes[0]
    provider.clear_lock()
    # check that lock has been released
    assert provider._master_lock.acquire(timeout=5)
    provider._master_lock.release()


@pytest.mark.slow_test
@pytest.mark.timeout_unless_on_windows(120)
def test_git_provider_mp_lock_timeout(main_class):
    """
    Check that lock will time out if master lock is locked.
    """
    provider = main_class.remotes[0]
    # Hijack the lock so git provider is fooled into thinking another instance is doing somthing.
    assert provider._master_lock.acquire(timeout=5)
    try:
        # git provider should raise timeout error to avoid lock race conditions
        pytest.raises(TimeoutError, provider.lock)
    finally:
        provider._master_lock.release()


@pytest.mark.slow_test
@pytest.mark.timeout_unless_on_windows(120)
def test_git_provider_mp_clear_lock_timeout(main_class):
    """
    Check that clear lock will time out if master lock is locked.
    """
    provider = main_class.remotes[0]
    # Hijack the lock so git provider is fooled into thinking another instance is doing somthing.
    assert provider._master_lock.acquire(timeout=5)
    try:
        # git provider should raise timeout error to avoid lock race conditions
        pytest.raises(TimeoutError, provider.clear_lock)
    finally:
        provider._master_lock.release()


@pytest.mark.slow_test
@pytest.mark.timeout_unless_on_windows(120)
def test_git_provider_mp_gen_lock(main_class):
    """
    Check that gen_lock is obtains lock, and then releases, provider.lock()
    """
    log.debug(f"DGM test_git_provider_mp_gen_lock, main_class '{dir(main_class)}'")
    provider = main_class.remotes[0]
    provider.gen_lock()
    try:
        # check that lock has been acquired
        assert provider._master_lock.acquire(timeout=5)
        # git provider should raise timeout error to avoid lock race conditions
        pytest.raises(TimeoutError, provider.lock)
    finally:
        provider.gen_lock()

    # check that lock has been released
    assert provider._master_lock.acquire(timeout=5)
    provider._master_lock.release()
