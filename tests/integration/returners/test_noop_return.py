# -*- coding: utf-8 -*-
"""
    tests.integration.returners.test_noop_return
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This test module is meant to cover the issue being fixed by:

        https://github.com/saltstack/salt/pull/54731
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

import pytest
import salt.ext.six as six
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture
def daemon_id():
    return "returner-test"


@pytest.fixture
def returner_salt_master(request, salt_factories, daemon_id):
    config_overrides = {
        "returner_dirs": [os.path.join(RUNTIME_VARS.FILES, "returners")],
        "event_return": "runtests_noop",
    }
    return salt_factories.spawn_master(
        request, daemon_id, config_overrides=config_overrides
    )


@pytest.fixture
def returner_salt_minion(request, salt_factories, daemon_id, returner_salt_master):
    return salt_factories.spawn_minion(request, daemon_id, master_id=daemon_id)


@pytest.fixture
def returner_salt_cli(salt_factories, daemon_id, returner_salt_minion):
    return salt_factories.get_salt_cli(daemon_id)


@pytest.mark.skipif(six.PY3, reason="Runtest Log Hander Disabled for PY3, #41836")
def test_noop_return(returner_salt_cli, daemon_id):
    with TstSuiteLoggingHandler(format="%(message)s", level=logging.DEBUG) as handler:
        ret = returner_salt_cli.run("test.ping", minion_tgt=daemon_id)
        assert ret.exitcode == 0
        assert (
            any("NOOP_RETURN" in s for s in handler.messages) is True
        ), "NOOP_RETURN not found in log messages"
