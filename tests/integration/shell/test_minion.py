# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.minion
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from __future__ import absolute_import

import logging
import time

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import ProcessNotStarted
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def shell_tests_salt_master(request, salt_factories):
    return salt_factories.spawn_master(request, "minion-shell-tests")


@pytest.fixture(scope="module")
def shell_tests_salt_minion_config(request, salt_factories, shell_tests_salt_master):
    return salt_factories.configure_minion(
        request,
        shell_tests_salt_master.config["id"],
        master_id=shell_tests_salt_master.config["id"],
        config_overrides={"user": "unknown-user"},
    )


@pytest.mark.windows_whitelisted
class TestSaltMinionCLI(object):
    @pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
    def test_exit_status_unknown_user(
        self, request, salt_factories, shell_tests_salt_minion_config
    ):
        """
        Ensure correct exit status when the minion is configured to run as an unknown user.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_minion(
                request,
                shell_tests_salt_minion_config["id"],
                master_id=shell_tests_salt_minion_config["id"],
                max_start_attempts=1,
            )

        assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
        assert "The user is not available." in exc.value.stderr, exc.value

    def test_exit_status_unknown_argument(
        self, request, salt_factories, shell_tests_salt_minion_config
    ):
        """
        Ensure correct exit status when an unknown argument is passed to salt-minion.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_minion(
                request,
                shell_tests_salt_minion_config["id"],
                master_id=shell_tests_salt_minion_config["id"],
                max_start_attempts=1,
                base_script_args=["--unknown-argument"],
            )
        assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
        assert "Usage" in exc.value.stderr, exc.value
        assert "no such option: --unknown-argument" in exc.value.stderr, exc.value

    @pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
    def test_exit_status_correct_usage(
        self, request, salt_factories, shell_tests_salt_master
    ):
        proc = salt_factories.spawn_minion(
            request,
            shell_tests_salt_master.config["id"] + "-2",
            master_id=shell_tests_salt_master.config["id"],
        )
        assert proc.is_alive()
        time.sleep(1)
        ret = proc.terminate()
        assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
