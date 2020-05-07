# -*- coding: utf-8 -*-
"""
    tests.multimaster.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Multimaster PyTest prep routines
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil

import pytest
from salt.utils.immutabletypes import freeze
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def salt_mm_master_config(request, salt_factories):
    return salt_factories.configure_master(request, "mm-master")


@pytest.fixture(scope="package")
def salt_mm_minion_config(request, salt_factories, salt_mm_master, salt_mm_sub_master):
    return salt_factories.configure_minion(
        request, "mm-minion", master_id=salt_mm_master.config["id"]
    )


@pytest.fixture(scope="package")
def salt_mm_sub_master_config(request, salt_factories, salt_mm_master):
    return salt_factories.configure_master(request, "mm-sub-master")


@pytest.fixture(scope="package")
def salt_mm_sub_minion_config(
    request, salt_factories, salt_mm_master, salt_mm_sub_master
):
    return salt_factories.configure_minion(
        request, "mm-sub-minion", master_id=salt_mm_sub_master.config["id"]
    )


@pytest.fixture(scope="package")
def salt_mm_master(request, salt_factories):
    return salt_factories.spawn_master(request, "mm-master")


@pytest.fixture(scope="package")
def salt_mm_sub_master(
    request, salt_factories, salt_mm_master, salt_mm_sub_master_config
):
    # The secondary salt master depends on the primarily salt master fixture
    # because we need to clone the keys
    for keyfile in ("master.pem", "master.pub"):
        shutil.copyfile(
            os.path.join(salt_mm_master.config["pki_dir"], keyfile),
            os.path.join(salt_mm_sub_master_config["pki_dir"], keyfile),
        )
    return salt_factories.spawn_master(request, "mm-sub-master")


@pytest.fixture(scope="package")
def salt_mm_minion(request, salt_factories, salt_mm_master, salt_mm_sub_master):
    return salt_factories.spawn_minion(
        request, "mm-minion", master_id=salt_mm_master.config["id"]
    )


@pytest.fixture(scope="package")
def salt_mm_sub_minion(request, salt_factories, salt_mm_master, salt_mm_sub_master):
    return salt_factories.spawn_minion(
        request, "mm-sub-minion", master_id=salt_mm_sub_master.config["id"]
    )


@pytest.fixture(scope="package", autouse=True)
def bridge_pytest_and_runtests(
    reap_stray_processes,
    base_env_state_tree_root_dir,
    prod_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_pillar_tree_root_dir,
    salt_factories,
    salt_mm_master,
    salt_mm_minion,
    salt_mm_sub_master,
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
