# -*- coding: utf-8 -*-
'''
    tests.integration.proxy.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Proxy related fixtures
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals
import os

# Import 3rd-party libs
import pytest


@pytest.fixture(scope='session', autouse=True)
def session_salt_proxy(session_salt_proxy,
                       session_proxy_id,
                       session_master_config):
    yield session_salt_proxy

    proxy_key_file = os.path.join(session_master_config['pki_dir'], 'minions', session_proxy_id)
    if os.path.exists(proxy_key_file):
        os.unlink(proxy_key_file)
