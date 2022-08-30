import contextlib
import pickle

import pytest

from salt._compat import ipaddress


@contextlib.contextmanager
def assert_clean_error(exc_type, details, *args):
    """
    Ensure exception does not display a context by default

    Wraps unittest.TestCase.assertRaisesRegex
    """
    if args:
        details = details % args
    with pytest.raises(exc_type, match=details) as exc:
        yield exc
    # Ensure we produce clean tracebacks on failure
    actual = exc.type(exc)
    if actual.__context__ is not None:
        assert actual.__suppress_context__ is True


def assert_address_error(details, *args):
    """Ensure a clean AddressValueError"""
    return assert_clean_error(ipaddress.AddressValueError, details, *args)


def assert_netmask_error(details, *args):
    """Ensure a clean NetmaskValueError"""
    return assert_clean_error(ipaddress.NetmaskValueError, details, *args)


def assert_instances_equal(factory, lhs, rhs):
    """Check constructor arguments produce equivalent instances"""
    assert factory(lhs) == factory(rhs)


def pickle_test(factory, addr):
    for proto in range(pickle.HIGHEST_PROTOCOL + 1):
        x = factory(addr)
        y = pickle.loads(pickle.dumps(x, proto))
        assert y == x
