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
    proxy_minion_id = "proxytest"
    root_dir = salt_factories._get_root_dir_for_daemon(proxy_minion_id)
    conf_dir = root_dir.join("conf").ensure(dir=True)
    RUNTIME_VARS.TMP_PROXY_CONF_DIR = conf_dir.strpath

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "proxy")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = request.config.getoption("--transport")
    yield salt_factories.spawn_proxy_minion(
        request, proxy_minion_id, master_id="master", config_defaults=config_defaults
    )

    proxy_key_file = os.path.join(
        salt_master.config["pki_dir"], "minions", proxy_minion_id
    )
    log.debug("Proxy minion %r KEY FILE: %s", proxy_minion_id, proxy_key_file)
    if os.path.exists(proxy_key_file):
        os.unlink(proxy_key_file)
    else:
        log.warning("The proxy minion key was not found at %s", proxy_key_file)
