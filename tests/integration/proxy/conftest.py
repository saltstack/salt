# -*- coding: utf-8 -*-
"""
    tests.integration.proxy.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Proxy related fixtures
"""
# pylint: disable=unused-argument,redefined-outer-name

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging
import os

# Import 3rd-party libs
import psutil
import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def session_salt_proxy(
    request, session_salt_proxy, session_proxy_id, session_master_config
):

    stats_key = "        Salt Proxy"
    request.session.stats_processes[stats_key] = psutil.Process(session_salt_proxy.pid)
    yield session_salt_proxy
    # Terminate Proxy now, we want to cleanup it's key before we move along
    session_salt_proxy.terminate()
    del request.session.stats_processes[stats_key]

    proxy_key_file = os.path.join(
        session_master_config["pki_dir"], "minions", session_proxy_id
    )
    log.warning("KEY FILE: %s", proxy_key_file)
    if os.path.exists(proxy_key_file):
        os.unlink(proxy_key_file)
    else:
        log.warning("The proxy minion key was not found at %s", proxy_key_file)
