"""
Scenario fixtures for the ``minion_memory_headroom`` opt-in configurable
queue-admission memory check (issue #69884). Each test parametrizes on the
minion-config overrides so a fresh minion is booted per scenario, proving
end-to-end that the loader accepts the new opts and the minion runs with
them in effect.
"""

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN


@pytest.fixture(scope="package")
def salt_master(salt_factories):
    factory = salt_factories.salt_master_daemon(
        random_string("mem-headroom-master-"),
        overrides={
            "open_mode": True,
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    with factory.started():
        yield factory


def _minion_overrides(extra=None):
    overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    if extra:
        overrides.update(extra)
    return overrides


@pytest.fixture(scope="function")
def minion_with_opts(salt_master, request):
    """
    Boot a fresh minion for the current test with the caller-supplied
    ``minion_memory_headroom`` / ``minion_memory_max`` overrides applied.

    Use like:

        @pytest.mark.parametrize(
            "minion_with_opts",
            [{"minion_memory_headroom": "5G"}],
            indirect=True,
        )
        def test_something(minion_with_opts):
            salt_call = minion_with_opts.salt_call_cli()
            ...
    """
    overrides = _minion_overrides(getattr(request, "param", None))
    factory = salt_master.salt_minion_daemon(
        random_string("mem-headroom-minion-"),
        overrides=overrides,
    )
    with factory.started():
        yield factory
