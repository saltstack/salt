import sys

import pytest

from salt._compat import ipaddress

pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


@pytest.fixture
def factory():
    return ipaddress.IPv4Network


def test_subnet_of(factory):
    # containee left of container
    assert factory("10.0.0.0/30").subnet_of(factory("10.0.1.0/24")) is False
    # containee inside container
    assert factory("10.0.0.0/30").subnet_of(factory("10.0.0.0/24")) is True
    # containee right of container
    assert factory("10.0.0.0/30").subnet_of(factory("10.0.1.0/24")) is False
    # containee larger than container
    assert factory("10.0.1.0/24").subnet_of(factory("10.0.0.0/30")) is False


def test_supernet_of(factory):
    # containee left of container
    assert factory("10.0.0.0/30").supernet_of(factory("10.0.1.0/24")) is False
    # containee inside container
    assert factory("10.0.0.0/30").supernet_of(factory("10.0.0.0/24")) is False
    # containee right of container
    assert factory("10.0.0.0/30").supernet_of(factory("10.0.1.0/24")) is False
    # containee larger than container
    assert factory("10.0.0.0/24").supernet_of(factory("10.0.0.0/30")) is True


def test_subnet_of_mixed_types():
    with pytest.raises(TypeError):
        ipaddress.IPv4Network("10.0.0.0/30").supernet_of(
            ipaddress.IPv6Network("::1/128")
        )
    with pytest.raises(TypeError):
        ipaddress.IPv6Network("::1/128").supernet_of(
            ipaddress.IPv4Network("10.0.0.0/30")
        )
    with pytest.raises(TypeError):
        ipaddress.IPv4Network("10.0.0.0/30").subnet_of(ipaddress.IPv6Network("::1/128"))
    with pytest.raises(TypeError):
        ipaddress.IPv6Network("::1/128").subnet_of(ipaddress.IPv4Network("10.0.0.0/30"))
