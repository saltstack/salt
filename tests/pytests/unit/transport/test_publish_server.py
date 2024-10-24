"""
Unit tests for salt transports PublishServer.
"""

import importlib
import inspect

import pytest

import salt.transport.base


@pytest.mark.parametrize("kind", salt.transport.base.TRANSPORTS)
def test_transport_publishserver_has_abstractmethods(kind):
    transport_mod = importlib.import_module(f"salt.transport.{kind}")
    abstractmethods = sorted(
        salt.transport.base.DaemonizedPublishServer.__abstractmethods__
    )
    implemented = []
    for methodname in abstractmethods:
        method = getattr(transport_mod.PublishServer, methodname)
        if not getattr(method, "__isabstractmethod__", False):
            implemented.append(methodname)
    assert implemented == abstractmethods


@pytest.mark.parametrize("kind", salt.transport.base.TRANSPORTS)
@pytest.mark.parametrize(
    "method", salt.transport.base.DaemonizedPublishServer.__abstractmethods__
)
def test_transport_publishserver_has_method_signatures(kind, method):
    transport_mod = importlib.import_module(f"salt.transport.{kind}")
    method_sig = inspect.signature(getattr(transport_mod.PublishServer, method))
    required_sig = inspect.signature(
        getattr(salt.transport.base.DaemonizedPublishServer, method)
    )
    # This print "OK" when it errors, but you have to dig through the message to find the
    # difference. It may make more sense to create a easier to digest datastructure (list/dict).
    assert method_sig == required_sig
