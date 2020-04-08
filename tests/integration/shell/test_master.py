# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.master
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from __future__ import absolute_import

import logging
import time

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import ProcessNotStarted
from tests.support.helpers import PRE_PYTEST_SKIP

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def shell_tests_salt_master_config(request, salt_factories):
    return salt_factories.configure_master(
        request, "shell-tests-master", config_overrides={"user": "unknown-user"}
    )


@pytest.mark.windows_whitelisted
class TestSaltMasterCLI(object):
    @PRE_PYTEST_SKIP
    def test_exit_status_unknown_user(
        self, request, salt_factories, shell_tests_salt_master_config
    ):
        """
        Ensure correct exit status when the master is configured to run as an unknown user.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_master(
                request, shell_tests_salt_master_config["id"], max_start_attempts=1
            )

        assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
        assert "The user is not available." in exc.value.stderr, exc.value

    def test_exit_status_unknown_argument(
        self, request, salt_factories, shell_tests_salt_master_config
    ):
        """
        Ensure correct exit status when an unknown argument is passed to salt-master.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_master(
                request,
                shell_tests_salt_master_config["id"],
                max_start_attempts=1,
                base_script_args=["--unknown-argument"],
            )
        assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
        assert "Usage" in exc.value.stderr, exc.value
        assert "no such option: --unknown-argument" in exc.value.stderr, exc.value

    @PRE_PYTEST_SKIP
    def test_exit_status_correct_usage(
        self, request, salt_factories, shell_tests_salt_master_config
    ):
        proc = salt_factories.spawn_master(
            request, shell_tests_salt_master_config["id"] + "-2"
        )
        assert proc.is_alive()
        time.sleep(1)
        ret = proc.terminate()
        assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
