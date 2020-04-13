# -*- coding: utf-8 -*-
"""
    tests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration tests PyTest configuration/fixtures
"""
# pylint: disable=unused-argument,redefined-outer-name

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging
from collections import OrderedDict

# Import 3rd-party libs
import psutil
import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def default_session_daemons(
    request,
    log_server,
    session_salt_master,
    session_salt_minion,
    session_secondary_salt_minion,
):

    request.session.stats_processes.update(
        OrderedDict(
            (
                ("Salt Master", psutil.Process(session_salt_master.pid)),
                ("Salt Minion", psutil.Process(session_salt_minion.pid)),
                ("Salt Sub Minion", psutil.Process(session_secondary_salt_minion.pid)),
            )
        ).items()
    )

    # Run tests
    yield

    # Stop daemons now(they would be stopped at the end of the test run session
    for daemon in (
        session_secondary_salt_minion,
        session_salt_minion,
        session_salt_master,
    ):
        try:
            daemon.terminate()
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("Failed to terminate daemon: %s", daemon.__class__.__name__)
