"""
    tests.pytests.conftest
    ~~~~~~~~~~~~~~~~~~~~~~
"""
import logging
import os
import shutil
import stat

import pytest
import salt.utils.files
import salt.utils.platform
from salt.serializers import yaml
from saltfactories.utils import random_string
from tests.support.helpers import get_virtualenv_binary_path
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def salt_minion_id():
    return random_string("minion-")


@pytest.fixture(scope="session")
def salt_sub_minion_id():
    return random_string("sub-minion-")


@pytest.fixture(scope="session")
def salt_master_factory(
    request,
    salt_factories,
    salt_minion_id,
    salt_sub_minion_id,
    base_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_state_tree_root_dir,
    prod_env_pillar_tree_root_dir,
):
    master_id = random_string("master-")
    root_dir = salt_factories.get_root_dir_for_daemon(master_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = request.config.getoption("--transport")
    config_defaults["reactor"] = [
        {"salt/test/reactor": [os.path.join(RUNTIME_VARS.FILES, "reactor-test.sls")]}
    ]

    nodegroups = {
        "min": salt_minion_id,
        "sub_min": salt_sub_minion_id,
        "mins": "N@min or N@sub_min",
        "list_nodegroup": [salt_minion_id, salt_sub_minion_id],
        "multiline_nodegroup": [salt_minion_id, "or", salt_sub_minion_id],
        "one_minion_list": [salt_minion_id],
        "redundant_minions": "N@min or N@mins",
        "nodegroup_loop_a": "N@nodegroup_loop_b",
        "nodegroup_loop_b": "N@nodegroup_loop_a",
        "missing_minion": "L@{},ghostminion".format(salt_minion_id),
        "list_group": "N@multiline_nodegroup",
        "one_list_group": "N@one_minion_list",
        "list_group2": "N@list_nodegroup",
    }
    config_defaults["nodegroups"] = nodegroups
    config_overrides = {}
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
                "root_dir": os.path.join(RUNTIME_VARS.PILLAR_DIR, "base", "file_tree"),
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
            "file_roots": {
                "base": [
                    str(base_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    str(prod_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    str(base_env_pillar_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [str(prod_env_pillar_tree_root_dir)],
            },
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

    factory = salt_factories.get_salt_master_daemon(
        master_id,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_minion_factory(salt_master_factory, salt_minion_id):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.get_salt_minion_daemon(
        salt_minion_id,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.register_after_terminate_callback(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_sub_minion_factory(salt_master_factory, salt_sub_minion_id):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.get_salt_minion_daemon(
        salt_sub_minion_id,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.register_after_terminate_callback(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_proxy_factory(salt_factories, salt_master_factory):
    proxy_minion_id = random_string("proxytest-")
    root_dir = salt_factories.get_root_dir_for_daemon(proxy_minion_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)
    RUNTIME_VARS.TMP_PROXY_CONF_DIR = str(conf_dir)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "proxy")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]
    config_defaults["user"] = salt_master_factory.config["user"]

    factory = salt_master_factory.get_salt_proxy_minion_daemon(
        proxy_minion_id,
        config_defaults=config_defaults,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        start_timeout=240,
    )
    factory.register_after_terminate_callback(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def bridge_pytest_and_runtests():
    """
    We're basically overriding the same fixture defined in tests/conftest.py
    """
