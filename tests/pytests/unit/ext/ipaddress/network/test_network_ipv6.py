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
    return ipaddress.IPv6Network


def test_subnet_of(factory):
    # containee left of container
    assert factory("2000:999::/56").subnet_of(factory("2000:aaa::/48")) is False
    # containee inside container
    assert factory("2000:aaa::/56").subnet_of(factory("2000:aaa::/48")) is True
    # containee right of container
    assert factory("2000:bbb::/56").subnet_of(factory("2000:aaa::/48")) is False
    # containee larger than container
    assert factory("2000:aaa::/48").subnet_of(factory("2000:aaa::/56")) is False

    assert (
        factory("2000:999::%scope/56").subnet_of(factory("2000:aaa::%scope/48"))
        is False
    )
    assert (
        factory("2000:aaa::%scope/56").subnet_of(factory("2000:aaa::%scope/48")) is True
    )


def test_supernet_of(factory):
    # containee left of container
    assert factory("2000:999::/56").supernet_of(factory("2000:aaa::/48")) is False
    # containee inside container
    assert factory("2000:aaa::/56").supernet_of(factory("2000:aaa::/48")) is False
    # containee right of container
    assert factory("2000:bbb::/56").supernet_of(factory("2000:aaa::/48")) is False
    # containee larger than container
    assert factory("2000:aaa::/48").supernet_of(factory("2000:aaa::/56")) is True
