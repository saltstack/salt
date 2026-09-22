"""
Unit tests for the ipcidr matcher.
"""

import logging

import pytest

import salt.matchers.ipcidr_match as ipcidr_match


@pytest.fixture
def configure_loader_modules():
    return {ipcidr_match: {}}


def _make_opts(ipv4_addrs=None, ipv6_addrs=None):
    grains = {}
    if ipv4_addrs is not None:
        grains["ipv4"] = ipv4_addrs
    if ipv6_addrs is not None:
        grains["ipv6"] = ipv6_addrs
    return {"grains": grains}


def test_match_ipv4_address_hit():
    """Match a specific IPv4 address that is in the minion's grains."""
    opts = _make_opts(ipv4_addrs=["192.168.1.1", "10.0.0.1"])
    assert ipcidr_match.match("192.168.1.1", opts=opts) is True


def test_match_ipv4_address_miss():
    """No match when the IPv4 address is not in the minion's grains."""
    opts = _make_opts(ipv4_addrs=["192.168.1.2"])
    assert ipcidr_match.match("192.168.1.1", opts=opts) is False


def test_match_ipv4_cidr_hit():
    """Match a CIDR network that contains the minion's IPv4 address."""
    opts = _make_opts(ipv4_addrs=["192.168.1.5"])
    assert ipcidr_match.match("192.168.1.0/24", opts=opts) is True


def test_match_ipv4_cidr_miss():
    """No match when the CIDR network does not contain any minion address."""
    opts = _make_opts(ipv4_addrs=["10.0.0.1"])
    assert ipcidr_match.match("192.168.1.0/24", opts=opts) is False


def test_match_invalid_target_returns_empty_list(caplog):
    """An invalid IP/CIDR target logs an error and returns an empty list."""
    opts = _make_opts(ipv4_addrs=["192.168.1.1"])
    with caplog.at_level(logging.ERROR, logger="salt.matchers.ipcidr_match"):
        result = ipcidr_match.match("not-an-ip", opts=opts)
    assert result == []
    assert "Invalid IP/CIDR target" in caplog.text


def test_match_proto_not_in_grains():
    """Returns False when the IP version is not present in grains."""
    opts = _make_opts()  # no ipv4 or ipv6
    assert ipcidr_match.match("192.168.1.1", opts=opts) is False
