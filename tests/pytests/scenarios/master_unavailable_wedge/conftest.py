"""
Fixtures for the master-unavailable-wedge scenario.

The scenario stands up a real salt-master + salt-minion pair via
saltfactories, waits for the minion to auth, then terminates the master
so that subsequent minion REQ sends time out.  With aggressive scheduled
event rates on the minion, this reliably reproduces the pre-wedge log
sequence observed in the wild (Request timed out → unclosed
SyncWrapper → Error dispatching event: Message timed out) and often
progresses to the actual ``zmq_ctx_term()`` freeze on MainThread.
"""

import logging

import pytest
from saltfactories.utils import random_string

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def salt_master(salt_factories):
    """A real salt-master on localhost.  Started before the test, then
    terminated mid-test by the scenario to force the minion's REQ sends
    to time out.  We start it here rather than yielding an unstarted
    factory so the minion fixture has a live ret_port to auth against.
    """
    config_defaults = {
        "transport": "zeromq",
        "auto_accept": True,
        "sign_pub_messages": False,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("wedge-master-"),
        defaults=config_defaults,
    )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="module")
def salt_minion(salt_master):
    """A salt-minion with aggressive event churn so the leaked-context
    finalizer fires within a bounded test window once the master goes
    away.

    ``mine_interval`` is measured in *minutes* in the minion config;
    0.1 = 6 seconds between mine returns, each of which constructs a
    REQ channel to the master.  Combined with a 3-second
    ``request_channel_timeout``, this produces one leak-eligible REQ
    site every ~9 seconds under a downed master.
    """
    config_defaults = {
        "transport": "zeromq",
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "publish_port": salt_master.config["publish_port"],
        "master_uri": f"tcp://127.0.0.1:{salt_master.config['ret_port']}",
        "mine_interval": 0.1,
        "grains_refresh_every": 0.1,
        "auth_timeout": 3,
        "auth_tries": 1,
        "request_channel_timeout": 3,
        "request_channel_tries": 1,
        # Keep the alive-ping quiet -- we want the wedge trigger to be
        # the REQ churn, not the alive-ping (which has its own recovery
        # path via resolve_dns() re-run).
        "master_alive_interval": 0,
    }
    factory = salt_master.salt_minion_daemon(
        random_string("wedge-minion-"),
        defaults=config_defaults,
    )
    return factory
