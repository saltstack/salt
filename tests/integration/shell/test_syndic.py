# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.syndic
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
    return salt_factories.spawn_master(request, "syndic-shell-tests-mom")


@pytest.mark.windows_whitelisted
class TestSaltSyndicCLI(object):
    @pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
    def test_exit_status_unknown_user(
        self, request, salt_factories, shell_tests_salt_master
    ):
        """
        Ensure correct exit status when the syndic is configured to run as an unknown user.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_syndic(
                request,
                "syndic-shell-tests-unknown-user",
                master_of_masters_id=shell_tests_salt_master.config["id"],
                max_start_attempts=1,
                config_overrides={"syndic": {"user": "unknown-user"}},
            )

        assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
        assert "The user is not available." in exc.value.stderr, exc.value

    @pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
    def test_exit_status_unknown_argument(
        self, request, salt_factories, shell_tests_salt_master
    ):
        """
        Ensure correct exit status when an unknown argument is passed to salt-syndic.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_syndic(
                request,
                "syndic-shell-tests-unknown-arguments",
                master_of_masters_id=shell_tests_salt_master.config["id"],
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
        proc = salt_factories.spawn_syndic(
            request,
            "syndic-shell-tests",
            master_of_masters_id=shell_tests_salt_master.config["id"],
        )
        assert proc.is_alive()
        time.sleep(1)
        ret = proc.terminate()
        assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
