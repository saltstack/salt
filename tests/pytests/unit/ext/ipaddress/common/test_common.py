import operator
import re
import sys

import pytest

from salt._compat import ipaddress
from tests.support.pytest.ipaddress import assert_address_error

pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


@pytest.fixture(
    params=(
        ipaddress.IPv4Address,
        ipaddress.IPv6Address,
        ipaddress.IPv4Interface,
        ipaddress.IPv6Interface,
        ipaddress.IPv4Network,
        ipaddress.IPv6Network,
    ),
)
def factory(request):
    return request.param


def test_empty_address(factory):
    with assert_address_error("Address cannot be empty"):
        factory("")


def test_floats_rejected(factory):
    with assert_address_error(re.escape(repr("1.0"))):
        factory(1.0)


def test_not_an_index_issue15559(factory):
    # Implementing __index__ makes for a very nasty interaction with the
    # bytes constructor. Thus, we disallow implicit use as an integer
    pytest.raises(TypeError, operator.index, factory(1))
    pytest.raises(TypeError, hex, factory(1))
    pytest.raises(TypeError, bytes, factory(1))
