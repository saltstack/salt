"""
Functional tests demonstrating the value of worker pool routing.

These tests prove that without pool routing, slow ext pillar requests can
starve out authentication requests — causing minions to fail to connect.
With pool routing enabled, auth requests are handled in a dedicated pool
and are never blocked by slow pillar work.

Test design:
- A custom ext pillar sleeps for several seconds per call, simulating a
  slow database, vault lookup, or expensive pillar computation.
- Several minions kick off pillar refreshes concurrently, saturating every
  worker in the single-pool (no-routing) case.
- A new minion then tries to authenticate.  Without routing it must queue
  behind the blocked workers and times out.  With routing its auth request
  lands in a dedicated pool and succeeds immediately.
"""

import logging
import pathlib
import textwrap
import time

import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms.",
    ),
]

# How long the slow ext pillar sleeps per call.  Should be long enough that
# worker_count concurrent calls block for longer than AUTH_TIMEOUT.
PILLAR_SLEEP_SECS = 8

# Number of minions that hammer pillar concurrently to saturate the workers.
# Must be >= worker_count in the single-pool scenario so all slots are filled.
SATURATING_MINION_COUNT = 5

# Timeout we allow for the late-arriving auth minion to become ready.
AUTH_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slow_ext_pillar_source(sleep_secs: int) -> str:
    """Return Python source for a slow ext pillar module."""
    return textwrap.dedent(
        f"""\
        import time

        def ext_pillar(minion_id, pillar, **kwargs):
            # Simulate an expensive pillar source (vault, database, etc.)
            time.sleep({sleep_secs})
            return {{"slow_pillar_key": "value_for_" + minion_id}}
        """
    )


def _write_ext_pillar(extmods_dir: pathlib.Path, sleep_secs: int) -> pathlib.Path:
    """Write the slow ext pillar module and return its directory."""
    pillar_dir = extmods_dir / "pillar"
    pillar_dir.mkdir(parents=True, exist_ok=True)
    (pillar_dir / "slow_pillar.py").write_text(_slow_ext_pillar_source(sleep_secs))
    return extmods_dir


def _minion_defaults() -> dict:
    return {
        "transport": "zeromq",
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extmods_dir(tmp_path):
    extmods = tmp_path / "extmods"
    _write_ext_pillar(extmods, PILLAR_SLEEP_SECS)
    return extmods


@pytest.fixture
def master_without_routing(salt_factories, extmods_dir, tmp_path):
    """
    Salt master with worker pools DISABLED (legacy single-pool behaviour).

    worker_threads equals SATURATING_MINION_COUNT so that firing that many
    concurrent pillar requests fully saturates every available worker.
    """
    pillar_dir = tmp_path / "pillar"
    pillar_dir.mkdir(exist_ok=True)

    config_defaults = {
        "transport": "zeromq",
        "auto_accept": True,
        "sign_pub_messages": False,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        # Disable pool routing — use the legacy single thread-pool
        "worker_pools_enabled": False,
        "worker_threads": SATURATING_MINION_COUNT,
        # Slow ext pillar
        "extension_modules": str(extmods_dir),
        "ext_pillar": [{"slow_pillar": {}}],
        "pillar_roots": {"base": [str(pillar_dir)]},
    }
    return salt_factories.salt_master_daemon(
        random_string("no-routing-master-"),
        defaults=config_defaults,
    )


@pytest.fixture
def master_with_routing(salt_factories, extmods_dir, tmp_path):
    """
    Salt master with worker pools ENABLED.

    An 'auth' pool handles ``_auth`` so authentication is never blocked by
    slow pillar work running in the 'default' pool.
    """
    pillar_dir = tmp_path / "pillar"
    pillar_dir.mkdir(exist_ok=True)

    config_defaults = {
        "transport": "zeromq",
        "auto_accept": True,
        "sign_pub_messages": False,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        # Enable pool routing with a dedicated auth pool
        "worker_pools_enabled": True,
        "worker_pools": {
            "auth": {
                "worker_count": 2,
                "commands": ["_auth"],
            },
            "default": {
                "worker_count": SATURATING_MINION_COUNT,
                "commands": ["*"],
            },
        },
        # Slow ext pillar (same load as the no-routing test)
        "extension_modules": str(extmods_dir),
        "ext_pillar": [{"slow_pillar": {}}],
        "pillar_roots": {"base": [str(pillar_dir)]},
    }
    return salt_factories.salt_master_daemon(
        random_string("with-routing-master-"),
        defaults=config_defaults,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "Without pool routing, slow ext pillar calls starve auth requests. "
        "This xfail documents the starvation problem that pool routing solves."
    ),
    strict=True,
)
def test_auth_starved_without_routing(master_without_routing):
    """
    WITHOUT pool routing, slow ext pillar calls starve out auth requests.

    Every worker becomes occupied serving slow pillar refreshes.  A new
    minion that arrives while the pool is saturated cannot get its ``_auth``
    request processed within the timeout and fails to start.

    The test is marked ``xfail(strict=True)`` because we *expect* auth to
    fail here — that is exactly the problem being demonstrated.
    """
    with master_without_routing.started():
        # Bring up minions that will each trigger a slow pillar refresh,
        # occupying one worker each for PILLAR_SLEEP_SECS seconds.
        saturating_minions = [
            master_without_routing.salt_minion_daemon(
                random_string(f"sat-{i}-"),
                defaults=_minion_defaults(),
            )
            for i in range(SATURATING_MINION_COUNT)
        ]

        for minion in saturating_minions:
            try:
                minion.start()
            except FactoryNotStarted:
                # Some saturating minions may fail on their own — that is fine,
                # we only need them to fire pillar requests.
                pass

        # Give the saturation traffic a moment to reach the workers.
        time.sleep(2)

        # Now attempt to authenticate a brand-new minion while the pool is
        # saturated.  This should time out because no worker is free to handle
        # the ``_auth`` request.
        auth_minion = master_without_routing.salt_minion_daemon(
            random_string("auth-victim-"),
            defaults=_minion_defaults(),
        )

        auth_started = False
        try:
            auth_minion.start(start_timeout=AUTH_TIMEOUT, max_start_attempts=1)
            auth_started = True
        except FactoryNotStarted:
            log.info("Auth minion failed to start as expected (workers starved).")
        finally:
            auth_minion.terminate()
            for minion in saturating_minions:
                minion.terminate()

        # Assert auth *failed* — this assertion flips the xfail.  If routing
        # is somehow in play and auth succeeds, the test will be an
        # unexpected pass (xpass), which also counts as a test failure with
        # strict=True.
        assert not auth_started, (
            "Auth succeeded even though all workers should have been blocked by "
            "slow pillar. This means pool routing may be active or the test "
            "parameters need tuning."
        )


def test_auth_not_starved_with_routing(master_with_routing):
    """
    WITH pool routing, auth succeeds even while the default pool is saturated.

    The ``_auth`` command is mapped to a dedicated 'auth' pool so it is
    processed immediately, independently of the slow pillar work happening
    in the 'default' pool.
    """
    with master_with_routing.started():
        # Saturate the 'default' pool workers with slow pillar refreshes.
        saturating_minions = [
            master_with_routing.salt_minion_daemon(
                random_string(f"sat-{i}-"),
                defaults=_minion_defaults(),
            )
            for i in range(SATURATING_MINION_COUNT)
        ]

        for minion in saturating_minions:
            try:
                minion.start()
            except FactoryNotStarted:
                pass

        # Give saturation traffic time to hit the default pool workers.
        time.sleep(2)

        # A new minion's _auth request should land in the 'auth' pool and
        # succeed immediately regardless of slow pillar activity.
        auth_minion = master_with_routing.salt_minion_daemon(
            random_string("auth-succeeds-"),
            defaults=_minion_defaults(),
        )

        start = time.time()
        try:
            auth_minion.start(start_timeout=AUTH_TIMEOUT, max_start_attempts=1)
            elapsed = time.time() - start
            log.info("Auth minion started in %.1fs", elapsed)
        except FactoryNotStarted as exc:
            elapsed = time.time() - start
            pytest.fail(
                f"Auth minion failed to start within {AUTH_TIMEOUT}s ({elapsed:.1f}s "
                f"elapsed) even though pool routing should have protected the auth "
                f"pool from slow pillar work.\n{exc}"
            )
        finally:
            auth_minion.terminate()
            for minion in saturating_minions:
                minion.terminate()

        assert elapsed < AUTH_TIMEOUT, (
            f"Auth took {elapsed:.1f}s — longer than the {AUTH_TIMEOUT}s timeout. "
            "Pool routing should have kept auth fast."
        )
