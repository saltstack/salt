"""
Integration tests for ``salt-run manage.present`` and friends with minions
whose connecting address is not in their grains (issue #58592).

``manage.present`` only reads the master's presence detection, it sends nothing
to the minions. Presence detection used to compare the addresses connected to
the publish port with the addresses in the minions' cached grains, so a minion
behind NAT or on the internet was never reported as present.

We reproduce that without a NAT by overwriting a connected minion's cached
grains with addresses that are never the ones it connects from.

With ``presence_id_tracking`` enabled the master also records every
authenticated request of an accepted minion and reports minions seen within
``presence_id_ttl`` seconds as present.
"""

import logging
import time

import pytest
from saltfactories.utils import random_string

import salt.cache
import salt.utils.network
from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

PRESENCE_TTL = 30
# RFC 5737 TEST-NET-3: never an address of the machine running the tests
NAT_GRAINS = {"ipv4": ["203.0.113.10"], "ipv6": []}


def _minion_overrides(master):
    return {
        "master": master.config["interface"],
        "master_port": master.config["ret_port"],
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }


class PresenceHelper:
    """
    Drive a master's CLIs and its cache for the presence tests.
    """

    def __init__(self, master):
        self.master = master
        self.cli = master.salt_cli()
        self.run_cli = master.salt_run_cli()
        self.cache = salt.cache.Cache(master.config)

    def seen(self, minion_id):
        """
        Make the minion send an authenticated request to the master by running
        a job on it: the job return is an AES encrypted request.
        """
        ret = self.cli.run("test.ping", minion_tgt=minion_id)
        assert ret.returncode == 0, ret
        assert ret.data is True

    def natted(self, minion_id):
        """
        Have the master see the minion, then make it believe the minion lives
        at an address it never connects from.

        The master refreshes a minion's cached grains on every pillar request,
        so the grains are overwritten last and only checked afterwards.
        """
        self.seen(minion_id)
        self.poison(minion_id)

    def poison(self, minion_id):
        self.cache.store("grains", minion_id, NAT_GRAINS)

    def run(self, runner, *args, natted=()):
        """
        Run a manage runner. ``natted`` lists the minions whose cached grains
        must still be the poisoned ones afterwards, otherwise the result could
        have come from the grains-address detection and proves nothing.
        """
        ret = self.run_cli.run(runner, *args)
        assert ret.returncode == 0, ret
        for minion_id in natted:
            assert (
                self.cache.fetch("grains", minion_id) == NAT_GRAINS
            ), f"The cached grains of {minion_id} were refreshed during the test"
        return ret.data or []


@pytest.fixture(scope="module")
def presence_master(request, salt_factories):
    config_defaults = {
        "transport": request.config.getoption("--transport"),
        "auto_accept": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "presence_id_tracking": True,
        "presence_id_ttl": PRESENCE_TTL,
        "presence_events": True,
        "loop_interval": 5,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("presence-master-"),
        defaults=config_defaults,
        overrides=config_overrides,
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="module")
def presence_minion(presence_master):
    factory = presence_master.salt_minion_daemon(
        random_string("presence-minion-"),
        overrides=_minion_overrides(presence_master),
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="module")
def presence(presence_master):
    return PresenceHelper(presence_master)


def _wait_for(predicate, timeout, interval=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_natted_minion_is_present(presence, presence_minion):
    presence.natted(presence_minion.id)
    result = presence.run("manage.present", natted=[presence_minion.id])
    assert presence_minion.id in result


@pytest.mark.parametrize("runner", ["manage.joined", "manage.allowed", "manage.alived"])
def test_aliases_use_presence(runner, presence, presence_minion):
    presence.natted(presence_minion.id)
    result = presence.run(runner, natted=[presence_minion.id])
    assert presence_minion.id in result


def test_natted_minion_is_not_in_not_present(presence, presence_minion):
    presence.natted(presence_minion.id)
    result = presence.run("manage.not_present", natted=[presence_minion.id])
    assert presence_minion.id not in result


def test_present_with_show_ip(presence, presence_minion):
    presence.natted(presence_minion.id)
    result = presence.run("manage.present", "show_ip=True", natted=[presence_minion.id])
    assert presence_minion.id in result


def test_presence_event_names_natted_minion(
    event_listener, presence, presence_master, presence_minion
):
    presence.natted(presence_minion.id)
    start_time = time.time()

    def _event_lists_minion():
        if presence.cache.fetch("grains", presence_minion.id) != NAT_GRAINS:
            pytest.fail("The cached grains were refreshed during the test")
        matched = event_listener.wait_for_events(
            [(presence_master.id, "salt/presence/present")],
            after_time=start_time,
            timeout=10,
        )
        return any(
            presence_minion.id in event.data["present"] for event in matched.matches
        )

    assert _wait_for(_event_lists_minion, timeout=60, interval=0)


def test_minion_matching_by_address_is_still_present(presence, presence_minion):
    """
    Minions that connect from one of their grains addresses keep being found
    by the original address based detection, without any presence record.
    """
    addrs = salt.utils.network.ip_addrs(include_loopback=False)
    if not addrs:
        pytest.skip("No non-loopback address to match the minion's grains against")
    # a pillar refresh would rewrite this too, and without a presence record
    presence.cache.store("grains", presence_minion.id, {"ipv4": addrs, "ipv6": []})
    presence.cache.flush("presence", presence_minion.id)
    assert presence_minion.id in presence.run("manage.present")


def test_stopped_minion_stops_being_present(presence, presence_master):
    """
    A minion that stops sending requests drops out of ``manage.present`` once
    its presence record is older than ``presence_id_ttl``.
    """
    factory = presence_master.salt_minion_daemon(
        random_string("presence-stopped-"),
        overrides=_minion_overrides(presence_master),
    )
    with factory.started(start_timeout=120):
        presence.natted(factory.id)
        assert factory.id in presence.run("manage.present", natted=[factory.id])
    # Only the presence record can expire from here on.
    presence.poison(factory.id)
    assert _wait_for(
        lambda: factory.id not in presence.run("manage.present"),
        timeout=PRESENCE_TTL + 90,
    ), "Stopped minion was still present after the presence ttl"


def test_deleted_key_is_no_longer_present(presence, presence_master):
    factory = presence_master.salt_minion_daemon(
        random_string("presence-deleted-"),
        overrides=_minion_overrides(presence_master),
    )
    key_cli = presence_master.salt_key_cli()
    with factory.started(start_timeout=120):
        presence.natted(factory.id)
        assert factory.id in presence.run("manage.present", natted=[factory.id])
        ret = key_cli.run("-d", factory.id, "-y")
        assert ret.returncode == 0, ret
        assert factory.id not in presence.run("manage.present")


def test_option_off_natted_minion_is_not_present(salt_master, salt_minion):
    """
    Default configuration (``presence_id_tracking: False``): behavior is
    unchanged, a minion connecting from an address that is not in its grains
    is not reported by ``manage.present``.
    """
    presence = PresenceHelper(salt_master)
    original = presence.cache.fetch("grains", salt_minion.id)
    try:
        presence.natted(salt_minion.id)
        result = presence.run("manage.present", natted=[salt_minion.id])
        assert salt_minion.id not in result
    finally:
        if original:
            presence.cache.store("grains", salt_minion.id, original)
