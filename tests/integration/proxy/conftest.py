# -*- coding: utf-8 -*-
"""
    tests.integration.proxy.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Proxy related fixtures
"""
from __future__ import absolute_import, unicode_literals

import logging
import os

import pytest
import salt.utils.files
from salt.serializers import yaml
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def salt_proxy(request, salt_factories, salt_master):
    yield salt_factories.spawn_proxy_minion(request, "proxytest", master_id="master")

    proxy_key_file = os.path.join(salt_master.config["pki_dir"], "minions", "proxytest")
    log.warning("KEY FILE: %s", proxy_key_file)
    if os.path.exists(proxy_key_file):
        os.unlink(proxy_key_file)
    else:
        log.warning("The proxy minion key was not found at %s", proxy_key_file)


def pytest_saltfactories_generate_default_proxy_minion_configuration(
    request, factories_manager, root_dir, proxy_minion_id, master_port
):
    """
    Hook which should return a dictionary tailored for the provided proxy_minion_id

    Stops at the first non None result
    """
    if proxy_minion_id == "proxytest":
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.CONF_DIR, "proxy")
        ) as rfh:
            opts = yaml.deserialize(rfh.read())
    else:
        raise RuntimeError(
            "Not prepared to handle proxy_minion_id '{}'".format(proxy_minion_id)
        )

    opts["hosts.file"] = root_dir.join("hosts").strpath
    opts["aliases.file"] = root_dir.join("aliases").strpath
    opts["transport"] = request.config.getoption("--transport")

    RUNTIME_VARS.TMP_PROXY_CONF_DIR = root_dir.join("conf").strpath

    return opts


def pytest_saltfactories_proxy_minion_configuration_overrides(
    request, factories_manager, root_dir, proxy_minion_id, default_options
):
    """
    Hook which should return a dictionary tailored for the provided proxy_minion_id.
    This dictionary will override the default_options dictionary.

    Stops at the first non None result
    """
