"""
    tests.multimaster.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Multimaster PyTest prep routines
"""

import logging
import os
import pathlib
import shutil

import pytest
import salt.utils.files
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def ext_pillar_file_tree():
    pillar_file_tree = {
        "root_dir": str(pathlib.Path(RUNTIME_VARS.PILLAR_DIR) / "base" / "file_tree"),
        "follow_dir_links": False,
        "keep_newline": True,
    }
    return {"file_tree": pillar_file_tree}


@pytest.fixture(scope="package")
def salt_mm_master(request, salt_factories, ext_pillar_file_tree):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_master")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

    master_id = "mm-master"
    root_dir = salt_factories.get_root_dir_for_daemon(master_id)
    config_defaults["root_dir"] = str(root_dir)
    config_defaults["ext_pillar"] = [ext_pillar_file_tree]
    config_defaults["open_mode"] = True
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
    factory = salt_factories.get_salt_master_daemon(
        master_id,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_mm_sub_master(salt_factories, salt_mm_master, ext_pillar_file_tree):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_sub_master")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

    master_id = "mm-sub-master"
    root_dir = salt_factories.get_root_dir_for_daemon(master_id)
    config_defaults["root_dir"] = str(root_dir)
    config_defaults["ext_pillar"] = [ext_pillar_file_tree]
    config_defaults["open_mode"] = True
    config_defaults["transport"] = salt_mm_master.config["transport"]

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

    factory = salt_factories.get_salt_master_daemon(
        master_id,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )

    # The secondary salt master depends on the primarily salt master fixture
    # because we need to clone the keys
    for keyfile in ("master.pem", "master.pub"):
        shutil.copyfile(
            os.path.join(salt_mm_master.config["pki_dir"], keyfile),
            os.path.join(factory.config["pki_dir"], keyfile),
        )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_mm_minion(salt_mm_master, salt_mm_sub_master):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_mm_master.config["transport"]

    mm_master_port = salt_mm_master.config["ret_port"]
    mm_sub_master_port = salt_mm_sub_master.config["ret_port"]
    config_overrides = {
        "master": [
            "localhost:{}".format(mm_master_port),
            "localhost:{}".format(mm_sub_master_port),
        ],
        "test.foo": "baz",
    }
    factory = salt_mm_master.get_salt_minion_daemon(
        "mm-minion",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_mm_sub_minion(salt_mm_master, salt_mm_sub_master):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_sub_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_mm_master.config["transport"]

    mm_master_port = salt_mm_master.config["ret_port"]
    mm_sub_master_port = salt_mm_sub_master.config["ret_port"]
    config_overrides = {
        "master": [
            "localhost:{}".format(mm_master_port),
            "localhost:{}".format(mm_sub_master_port),
        ],
        "test.foo": "baz",
    }
    factory = salt_mm_sub_master.get_salt_minion_daemon(
        "mm-sub-minion",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package", autouse=True)
def bridge_pytest_and_runtests(  # pylint: disable=function-redefined
    reap_stray_processes,
    base_env_state_tree_root_dir,
    prod_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_pillar_tree_root_dir,
    salt_mm_master,
    salt_mm_sub_master,
    salt_mm_minion,
    salt_mm_sub_minion,
):
    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_master"] = freeze(salt_mm_master.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_minion"] = freeze(salt_mm_minion.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_sub_master"] = freeze(salt_mm_sub_master.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_sub_minion"] = freeze(salt_mm_sub_minion.config)

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_MM_CONF_DIR = os.path.dirname(salt_mm_master.config["conf_file"])
    RUNTIME_VARS.TMP_MM_MINION_CONF_DIR = os.path.dirname(
        salt_mm_minion.config["conf_file"]
    )
    RUNTIME_VARS.TMP_MM_SUB_CONF_DIR = os.path.dirname(
        salt_mm_sub_master.config["conf_file"]
    )
    RUNTIME_VARS.TMP_MM_SUB_MINION_CONF_DIR = os.path.dirname(
        salt_mm_sub_minion.config["conf_file"]
    )
