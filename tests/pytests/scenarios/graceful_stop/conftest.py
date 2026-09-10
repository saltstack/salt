"""
Package-local fixtures for the minion graceful-stop scenario.

Kept in its own package (not under ``scenarios/daemons``) so the
package-scoped ``salt_master_factory`` here does not share state with
``test_salt_as_daemons.py`` -- that neighbour test asserts on
``salt_master_factory.impl._terminal_result.stdout == ""`` on its first
``.started("-d")`` call and would see leftover stdout captured by
whichever test in the package ran the master first.
"""

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN


@pytest.fixture(scope="package")
def salt_master_factory(request, salt_factories):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    return salt_factories.salt_master_daemon(
        random_string("graceful-stop-master-"),
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )


@pytest.fixture(scope="package")
def salt_minion_factory(salt_master_factory):
    config_defaults = {
        "transport": salt_master_factory.config["transport"],
    }
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": ("OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"),
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
    }
    return salt_master_factory.salt_minion_daemon(
        random_string("graceful-stop-minion-"),
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
