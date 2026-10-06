"""
Unit tests for the netntp state.
"""

import pytest

import salt.states.netntp as netntp
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {netntp: {"__salt__": {}, "__opts__": {"test": False}}}


def test_check_rejects_non_list():
    assert netntp._check("192.0.2.1") is False


def test_check_resolves_in_place():
    # ``_check`` is documented to transform names into IP addresses; the resolved
    # values must replace the caller's list in place (the old ``peers = ...``
    # only rebound the local, discarding them).
    peers = ["192.0.2.1", "192.0.2.2"]
    # netaddr may be absent in the test env, so IPAddress is not always bound
    # in the module namespace; create=True lets us patch it regardless.
    with patch("salt.states.netntp.HAS_NETADDR", True), patch(
        "salt.states.netntp.IPAddress", create=True, side_effect=lambda p: f"ip:{p}"
    ):
        result = netntp._check(peers)
    assert result is True
    assert peers == ["ip:192.0.2.1", "ip:192.0.2.2"]


def test_check_keeps_unresolvable_without_resolver():
    # An entry that is neither an IP nor resolvable (no DNS resolver available)
    # is kept as specified, not silently dropped from the desired list.
    class _AddrErr(Exception):
        pass

    def _raise(peer):
        raise _AddrErr(peer)

    peers = ["ntp.example.com"]
    with patch("salt.states.netntp.HAS_NETADDR", True), patch(
        "salt.states.netntp.HAS_DNSRESOLVER", False
    ), patch("salt.states.netntp.AddrFormatError", _AddrErr, create=True), patch(
        "salt.states.netntp.IPAddress", create=True, side_effect=_raise
    ):
        result = netntp._check(peers)
    assert result is True
    assert peers == ["ntp.example.com"]


def test_managed_reports_retrieval_failure():
    # A device-retrieval failure must surface as result=False, not be masked as
    # "Device configured properly." by the no-changes branch.
    ntp_peers = MagicMock(return_value={"result": False, "comment": "boom"})
    with patch.dict(netntp.__salt__, {"ntp.peers": ntp_peers}):
        ret = netntp.managed("t", peers=["192.0.2.1"])
    assert ret["result"] is False
    assert "Cannot retrieve NTP peers" in ret["comment"]


def test_managed_no_args_is_noop():
    # Neither peers nor servers supplied -> exit without touching the device.
    ret = netntp.managed("t")
    assert ret["result"] is False
    assert ret["changes"] == {}
