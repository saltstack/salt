"""
    tests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration tests PyTest configuration/fixtures
"""
import logging
import os
import shutil
import stat

import pytest
import salt.utils.files
import salt.utils.platform
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze
from saltfactories.utils.tempfiles import SaltPillarTree, SaltStateTree
from tests.support.helpers import get_virtualenv_binary_path
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def state_tree(integration_files_dir):
    state_tree_path = integration_files_dir / "state-tree"
    state_tree_path.mkdir(exist_ok=True)

    base_env_path = state_tree_path / "base"
    base_env_path.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_STATE_TREE = str(base_env_path.resolve())
    RUNTIME_VARS.TMP_BASEENV_STATE_TREE = RUNTIME_VARS.TMP_STATE_TREE

    prod_env_path = state_tree_path / "prod"
    prod_env_path.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = str(prod_env_path.resolve())

    envs = {
        "base": [
            str(base_env_path),
            os.path.join(RUNTIME_VARS.FILES, "file", "base"),
        ],
        # Alternate root to test __env__ choices
        "prod": [
            str(prod_env_path),
            os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
        ],
    }
    return SaltStateTree(envs=envs)


@pytest.fixture(scope="package")
def pillar_tree(integration_files_dir):
    pillar_tree_path = integration_files_dir / "pillar-tree"
    pillar_tree_path.mkdir(exist_ok=True)

    base_env_path = pillar_tree_path / "base"
    base_env_path.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PILLAR_TREE = str(base_env_path.resolve())
    RUNTIME_VARS.TMP_BASEENV_PILLAR_TREE = RUNTIME_VARS.TMP_PILLAR_TREE

    prod_env_path = pillar_tree_path / "prod"
    prod_env_path.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE = str(prod_env_path.resolve())

    envs = {
        "base": [
            str(base_env_path),
            os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
        ],
        # Alternate root to test __env__ choices
        "prod": [
            str(prod_env_path),
        ],
    }
    return SaltPillarTree(envs=envs)


@pytest.fixture(scope="package")
def salt_master_factory(
    request,
    salt_factories,
    state_tree,
    pillar_tree,
    ext_pillar_file_tree_root_dir,
):
    root_dir = salt_factories.get_root_dir_for_daemon("master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {"log_level_logfile": "quiet"}
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {"cmd_yaml": "type {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    ext_pillar.append(
        {
            "file_tree": {
                "root_dir": str(ext_pillar_file_tree_root_dir),
                "follow_dir_links": False,
                "keep_newline": True,
            }
        }
    )
    config_overrides["pillar_opts"] = True

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "ext_pillar": ext_pillar,
            "extension_modules": extension_modules_path,
            "file_roots": state_tree.as_dict(),
            "pillar_roots": pillar_tree.as_dict(),
        }
    )

    # Let's copy over the test cloud config files and directories into the running master config directory
    for entry in os.listdir(RUNTIME_VARS.CONF_DIR):
        if not entry.startswith("cloud"):
            continue
        source = os.path.join(RUNTIME_VARS.CONF_DIR, entry)
        dest = str(conf_dir / entry)
        if os.path.isdir(source):
            shutil.copytree(source, dest)
        else:
            shutil.copyfile(source, dest)

    factory = salt_factories.salt_master_daemon(
        "master",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture(scope="package")
def salt_minion_factory(salt_master_factory):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "log_level_logfile": "quiet",
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.salt_minion_daemon(
        "minion",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="package")
def salt_sub_minion_factory(salt_master_factory):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "log_level_logfile": "quiet",
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.salt_minion_daemon(
        "sub_minion",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="package")
def salt_cli(salt_master_factory):
    return salt_master_factory.salt_cli()


@pytest.fixture(scope="package")
def salt_cp_cli(salt_master_factory):
    return salt_master_factory.salt_cp_cli()


@pytest.fixture(scope="package")
def salt_key_cli(salt_master_factory):
    return salt_master_factory.salt_key_cli()


@pytest.fixture(scope="package")
def salt_run_cli(salt_master_factory):
    return salt_master_factory.salt_run_cli()


@pytest.fixture(scope="package")
def salt_call_cli(salt_minion_factory):
    return salt_minion_factory.salt_call_cli()


@pytest.fixture(scope="package")
def salt_master(salt_master_factory):
    """
    A running salt-master fixture
    """
    with salt_master_factory.started():
        yield salt_master_factory


@pytest.fixture(scope="package")
def salt_minion(salt_minion_factory):
    """
    A running salt-minion fixture
    """
    with salt_minion_factory.started():
        # Sync All
        salt_call_cli = salt_minion_factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield salt_minion_factory


@pytest.fixture(scope="module")
def salt_sub_minion(salt_sub_minion_factory):
    """
    A second running salt-minion fixture
    """
    with salt_sub_minion_factory.started():
        # Sync All
        salt_call_cli = salt_sub_minion_factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield salt_sub_minion_factory


@pytest.fixture(scope="package", autouse=True)
def bridge_pytest_and_runtests(
    reap_stray_processes,
    salt_factories,
    salt_master,
    salt_minion,
    salt_sub_minion_factory,
    sshd_config_dir,
):
    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["master"] = freeze(salt_master.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["minion"] = freeze(salt_minion.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["sub_minion"] = freeze(salt_sub_minion_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["client_config"] = freeze(
        salt.config.client_config(salt_master.config["conf_file"])
    )

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_ROOT_DIR = str(salt_factories.root_dir.resolve())
    RUNTIME_VARS.TMP_CONF_DIR = os.path.dirname(salt_master.config["conf_file"])
    RUNTIME_VARS.TMP_MINION_CONF_DIR = os.path.dirname(salt_minion.config["conf_file"])
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = os.path.dirname(
        salt_sub_minion_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SSH_CONF_DIR = str(sshd_config_dir)
