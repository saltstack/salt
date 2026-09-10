"""
Unit tests for the netusers state.
"""

import pytest

import salt.states.netusers as netusers


@pytest.fixture
def configure_loader_modules():
    return {netusers: {}}


def test_expand_users_without_defaults():
    """
    Regression test for #62170.

    ``netusers.managed`` passes its ``defaults`` argument through to
    ``_expand_users`` as ``common_users``. That argument is optional, so it is
    ``None`` whenever the SLS does not declare any defaults -- the common case.
    ``_expand_users`` must treat that as "no defaults" instead of crashing with
    ``AttributeError: 'NoneType' object has no attribute 'update'``.
    """
    users = {"admin": {"level": 15, "password": "$1$xyz", "sshkeys": []}}
    assert netusers._expand_users(users, None) == users


def test_managed_refuses_to_wipe_all_users():
    """
    #62170 safety guard: when neither ``users`` nor ``defaults`` yields anyone
    to manage, ``managed`` must refuse instead of removing every account on the
    device (which the declarative diff would otherwise do). It must bail out
    before touching the device.
    """
    ret = netusers.managed("t", users={}, defaults=None)
    assert ret["result"] is False
    assert ret["changes"] == {}
    assert "remove every user" in ret["comment"]


def test_expand_users_merges_defaults():
    """
    When defaults are provided they are merged with the per-device users, and
    the per-device definition wins on a key collision.
    """
    defaults = {"admin": {"level": 1}, "operator": {"level": 5}}
    users = {"admin": {"level": 15}, "restricted": {"level": 1}}
    assert netusers._expand_users(users, defaults) == {
        "admin": {"level": 15},
        "operator": {"level": 5},
        "restricted": {"level": 1},
    }
