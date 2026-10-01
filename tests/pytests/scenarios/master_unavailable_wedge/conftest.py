# Copyright © 2026 Broadcom Inc. and/or its subsidiaries. All Rights Reserved.
"""
Fixtures for the salt-minion pyzmq ``Context.__del__`` wedge scenario.

Two moving parts are stitched together here:

1. A test-only beacon (``wedge_beacons/wedge_leak.py``) that runs on
   the MPM ioloop via salt's periodic-callback beacon dispatcher and
   leaks a ``zmq.Context`` + REQ socket + queued send each tick. This
   is the deployment shape of a third-party beacon or engine that
   forgets to call ``close()`` -- exactly the pattern that wedged
   an affected minion in production.

2. A silent iptables DROP blackhole around the master's ret_port and
   publish_port (see ``test_master_ret_timeout.py``). Silent DROP,
   not REJECT or an RST-style proxy, is what lets the minion's queued
   REQ sends actually park undelivered under TCP retransmit for
   60+ seconds -- the shape libzmq needs for ``LINGER=-1`` to make
   ``socket.close()`` block in ``zmq_ctx_term()``.
"""

import logging
import pathlib

import pytest
from saltfactories.utils import random_string

log = logging.getLogger(__name__)

WEDGE_BEACONS_DIR = str(pathlib.Path(__file__).parent / "wedge_beacons")


@pytest.fixture(scope="module")
def salt_master(salt_factories):
    """Real salt-master on localhost with auto_accept."""
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
    """Salt-minion configured with the leaky ``wedge_leak`` beacon.

    The beacon fires every ioloop tick (``loop_interval: 1``,
    ``interval: 1``). Each tick constructs a ``zmq.Context`` +
    LINGER=-1 REQ socket, queues an undeliverable send, and lets the
    locals drop. Once ``test_master_ret_timeout.py`` installs the
    iptables blackhole those queued sends stop draining -- from that
    point every subsequent beacon tick's ``Context.__del__`` blocks
    in ``zmq_ctx_term()`` from inside the MPM ioloop.
    """
    ret_port = salt_master.config["ret_port"]
    master_uri = f"tcp://127.0.0.1:{ret_port}"
    config_defaults = {
        "transport": "zeromq",
        "master_ip": "127.0.0.1",
        "master_port": ret_port,
        "publish_port": salt_master.config["publish_port"],
        "master_uri": master_uri,
        "loop_interval": 1,
        "beacons_dirs": [WEDGE_BEACONS_DIR],
        "beacons": {
            "wedge_leak": [
                {"master_uri": master_uri},
                {"interval": 1},
            ],
        },
    }
    factory = salt_master.salt_minion_daemon(
        random_string("wedge-minion-"),
        defaults=config_defaults,
    )
    return factory
