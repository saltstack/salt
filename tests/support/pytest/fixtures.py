"""
    tests.support.pytest.fixtures
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    The purpose of this fixtures module is provide the same set of available fixture for the old unittest
    test suite under ``test/integration``, ``tests/multimaster`` and ``tests/unit``.

    Please refrain from adding fixtures to this module and instead add them to the appropriate
    ``conftest.py`` file.
"""
import os
import shutil
import stat

import pytest
import salt.utils.files
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze
from tests.support.helpers import get_virtualenv_binary_path
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture(scope="session")
def integration_files_dir(salt_factories):
    """
    Fixture which returns the salt integration files directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = salt_factories.root_dir.join("integration-files")
    dirname.ensure(dir=True)
    return dirname


@pytest.fixture(scope="session")
def state_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt state tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir.join("state-tree")
    dirname.ensure(dir=True)
    return dirname


@pytest.fixture(scope="session")
def pillar_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt pillar tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir.join("pillar-tree")
    dirname.ensure(dir=True)
    return dirname


@pytest.fixture(scope="session")
def base_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt base environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir.join("base")
    dirname.ensure(dir=True)
    RUNTIME_VARS.TMP_STATE_TREE = dirname.realpath().strpath
    RUNTIME_VARS.TMP_BASEENV_STATE_TREE = RUNTIME_VARS.TMP_STATE_TREE
    return dirname


@pytest.fixture(scope="session")
def prod_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt prod environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir.join("prod")
    dirname.ensure(dir=True)
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = dirname.realpath().strpath
    return dirname


@pytest.fixture(scope="session")
def base_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt base environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir.join("base")
    dirname.ensure(dir=True)
    RUNTIME_VARS.TMP_PILLAR_TREE = dirname.realpath().strpath
    RUNTIME_VARS.TMP_BASEENV_PILLAR_TREE = RUNTIME_VARS.TMP_PILLAR_TREE
    return dirname


@pytest.fixture(scope="session")
def prod_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt prod environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir.join("prod")
    dirname.ensure(dir=True)
    RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE = dirname.realpath().strpath
    return dirname


@pytest.fixture(scope="session")
def salt_syndic_master_config(request, salt_factories):
    root_dir = salt_factories._get_root_dir_for_daemon("syndic_master")

    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "syndic_master")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = root_dir.join("salt_ssh_known_hosts").strpath
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = root_dir.strpath
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = request.config.getoption("--transport")

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

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = root_dir.join("extension_modules").strpath
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = root_dir.join("autosign_file").strpath
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
                    RUNTIME_VARS.TMP_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    RUNTIME_VARS.TMP_PILLAR_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
            },
        }
    )
    return salt_factories.configure_master(
        request,
        "syndic_master",
        order_masters=True,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    )


@pytest.fixture(scope="session")
def salt_syndic_config(request, salt_factories, salt_syndic_master_config):
    return salt_factories.configure_syndic(
        request, "syndic", master_of_masters_id="syndic_master"
    )


@pytest.fixture(scope="session")
def salt_master_config(request, salt_factories, salt_syndic_master_config):
    root_dir = salt_factories._get_root_dir_for_daemon("master")
    conf_dir = root_dir.join("conf").ensure(dir=True)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = root_dir.join("salt_ssh_known_hosts").strpath
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = root_dir.strpath
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = request.config.getoption("--transport")
    config_defaults["reactor"] = [
        {"salt/test/reactor": [os.path.join(RUNTIME_VARS.FILES, "reactor-test.sls")]}
    ]

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
    extension_modules_path = root_dir.join("extension_modules").strpath
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = root_dir.join("autosign_file").strpath
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
                    RUNTIME_VARS.TMP_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    RUNTIME_VARS.TMP_PILLAR_TREE,
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
            },
        }
    )

    # Let's copy over the test cloud config files and directories into the running master config directory
    for entry in os.listdir(RUNTIME_VARS.CONF_DIR):
        if not entry.startswith("cloud"):
            continue
        source = os.path.join(RUNTIME_VARS.CONF_DIR, entry)
        dest = conf_dir.join(entry).strpath
        if os.path.isdir(source):
            shutil.copytree(source, dest)
        else:
            shutil.copyfile(source, dest)

    return salt_factories.configure_master(
        request,
        "master",
        master_of_masters_id="syndic_master",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    )


@pytest.fixture(scope="session")
def salt_minion_config(request, salt_factories, salt_master_config):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {
        "file_roots": {
            "base": [
                RUNTIME_VARS.TMP_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "base"),
            ],
            # Alternate root to test __env__ choices
            "prod": [
                RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
            ],
        },
        "pillar_roots": {
            "base": [
                RUNTIME_VARS.TMP_PILLAR_TREE,
                os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
            ],
            "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
        },
    }
    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    return salt_factories.configure_minion(
        request,
        "minion",
        master_id="master",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    )


@pytest.fixture(scope="session")
def salt_sub_minion_config(request, salt_factories, salt_master_config):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {
        "file_roots": {
            "base": [
                RUNTIME_VARS.TMP_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "base"),
            ],
            # Alternate root to test __env__ choices
            "prod": [
                RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
                os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
            ],
        },
        "pillar_roots": {
            "base": [
                RUNTIME_VARS.TMP_PILLAR_TREE,
                os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
            ],
            "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
        },
    }
    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    return salt_factories.configure_minion(
        request,
        "sub_minion",
        master_id="master",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    )


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_syndic_configuration_defaults(
    request, factories_manager, root_dir, syndic_id, syndic_master_port
):
    """
    Hook which should return a dictionary tailored for the provided syndic_id with 3 keys:

    * `master`: The default config for the master running along with the syndic
    * `minion`: The default config for the master running along with the syndic
    * `syndic`: The default config for the master running along with the syndic

    Stops at the first non None result
    """
    factory_opts = {"master": None, "minion": None, "syndic": None}
    if syndic_id == "syndic":
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.CONF_DIR, "syndic")
        ) as rfh:
            opts = yaml.deserialize(rfh.read())

            opts["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
            opts["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
            opts["transport"] = request.config.getoption("--transport")
            factory_opts["syndic"] = opts
    return factory_opts


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_syndic_configuration_overrides(
    request, factories_manager, syndic_id, config_defaults
):
    """
    Hook which should return a dictionary tailored for the provided syndic_id.
    This dictionary will override the default_options dictionary.

    The returned dictionary should contain 3 keys:

    * `master`: The config overrides for the master running along with the syndic
    * `minion`: The config overrides for the master running along with the syndic
    * `syndic`: The config overridess for the master running along with the syndic

    The `default_options` parameter be None or have 3 keys, `master`, `minion`, `syndic`,
    while will contain the default options for each of the daemons.

    Stops at the first non None result
    """


@pytest.fixture(scope="session", autouse=True)
def bridge_pytest_and_runtests(
    reap_stray_processes,
    base_env_state_tree_root_dir,
    prod_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_pillar_tree_root_dir,
    salt_factories,
    salt_syndic_master_config,
    salt_syndic_config,
    salt_master_config,
    salt_minion_config,
    salt_sub_minion_config,
):
    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["master"] = freeze(salt_master_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["minion"] = freeze(salt_minion_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["sub_minion"] = freeze(salt_sub_minion_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic_master"] = freeze(salt_syndic_master_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic"] = freeze(salt_syndic_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["client_config"] = freeze(
        salt.config.client_config(salt_master_config["conf_file"])
    )

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_ROOT_DIR = salt_factories.root_dir.realpath().strpath
    RUNTIME_VARS.TMP_CONF_DIR = os.path.dirname(salt_master_config["conf_file"])
    RUNTIME_VARS.TMP_MINION_CONF_DIR = os.path.dirname(salt_minion_config["conf_file"])
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = os.path.dirname(
        salt_sub_minion_config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR = os.path.dirname(
        salt_syndic_master_config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR = os.path.dirname(
        salt_syndic_config["conf_file"]
    )


# Only allow star importing the functions defined in this module
__all__ = [
    name
    for (name, func) in locals().items()
    if getattr(func, "__module__", None) == __name__
]
