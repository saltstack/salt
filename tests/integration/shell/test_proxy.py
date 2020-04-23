# -*- coding: utf-8 -*-
"""
    :codeauthor: Thayne Harbaugh (tharbaug@adobe.com)

    tests.integration.shell.proxy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from __future__ import absolute_import, print_function, unicode_literals

import logging
import time

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import ProcessNotStarted
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def shell_tests_salt_master(request, salt_factories):
    return salt_factories.spawn_master(request, "proxy-minion-shell-tests")


@pytest.fixture(scope="module")
def shell_tests_salt_proxy_minion_config(
    request, salt_factories, shell_tests_salt_master
):
    return salt_factories.configure_proxy_minion(
        request,
        shell_tests_salt_master.config["id"],
        master_id=shell_tests_salt_master.config["id"],
        config_overrides={"user": "unknown-user"},
    )


class TestProxyMinion:
    """
    Various integration tests for the salt-proxy executable.
    """

    @pytest.mark.slow_test(seconds=30)  # Test takes >10 and <=30 seconds
    def test_exit_status_no_proxyid(
        self, request, salt_factories, shell_tests_salt_proxy_minion_config
    ):
        """
        Ensure correct exit status when --proxyid argument is missing.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_proxy_minion(
                request,
                shell_tests_salt_proxy_minion_config["id"],
                master_id=shell_tests_salt_proxy_minion_config["id"],
                max_start_attempts=1,
                include_proxyid_cli_flag=False,
            )
        assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
        assert "Usage" in exc.value.stderr, exc.value
        assert "error: salt-proxy requires --proxyid" in exc.value.stderr, exc.value

    @pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
    @pytest.mark.slow_test(seconds=5)  # Test takes >1 and <=5 seconds
    def test_exit_status_unknown_user(
        self, request, salt_factories, shell_tests_salt_proxy_minion_config
    ):
        """
        Ensure correct exit status when the proxy is configured to run as an
        unknown user.
        """
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_proxy_minion(
                request,
                shell_tests_salt_proxy_minion_config["id"],
                master_id=shell_tests_salt_proxy_minion_config["id"],
                max_start_attempts=1,
            )

        assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
        assert "The user is not available." in exc.value.stderr, exc.value

    @pytest.mark.slow_test(seconds=5)  # Test takes >1 and <=5 seconds
    def test_exit_status_unknown_argument(
        self, request, salt_factories, shell_tests_salt_proxy_minion_config, tempdir
    ):
        """
        Ensure correct exit status when an unknown argument is passed to
        salt-proxy.
        """
        # We pass root_dir in order not to hit the max length socket path issue
        root_dir = tempdir.join("ex-st-unkn-arg-proxy").ensure(dir=True)
        with pytest.raises(ProcessNotStarted) as exc:
            salt_factories.spawn_proxy_minion(
                request,
                shell_tests_salt_proxy_minion_config["id"],
                master_id=shell_tests_salt_proxy_minion_config["id"],
                max_start_attempts=1,
                base_script_args=["--unknown-argument"],
                config_defaults={"root_dir": root_dir},
            )
        assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
        assert "Usage" in exc.value.stderr, exc.value
        assert "no such option: --unknown-argument" in exc.value.stderr, exc.value

    @pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
    @pytest.mark.slow_test(seconds=60)  # Test takes >30 and <=60 seconds
    def test_exit_status_correct_usage(
        self, request, salt_factories, shell_tests_salt_master
    ):
        """
        Ensure correct exit status when salt-proxy starts correctly.

        Skip on Windows because daemonization not supported
        """
        proc = salt_factories.spawn_proxy_minion(
            request,
            shell_tests_salt_master.config["id"] + "-2",
            master_id=shell_tests_salt_master.config["id"],
        )
        assert proc.is_alive()
        time.sleep(1)
        ret = proc.terminate()
        assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
