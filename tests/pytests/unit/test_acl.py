"""
    Unit tests for salt.acl.ClientACL
"""

import pytest

from salt import acl


@pytest.fixture
def configure_loader_modules():
    return {acl: {}}


@pytest.fixture
def blacklist():
    return {
        "users": ["joker", "penguin", "*bad_*", "blocked_.*", "^Homer$"],
        "modules": ["cmd.run", "test.fib", "rm-rf.*"],
    }


@pytest.fixture
def whitelist():
    return {
        "users": ["testuser", "saltuser"],
        "modules": ["test.ping", "grains.items"],
    }


def test_user_is_blacklisted(blacklist):
    """
    test user_is_blacklisted
    """
    client_acl = acl.PublisherACL(blacklist)

    assert client_acl.user_is_blacklisted("joker")
    assert client_acl.user_is_blacklisted("penguin")
    assert client_acl.user_is_blacklisted("bad_")
    assert client_acl.user_is_blacklisted("bad_user")
    assert client_acl.user_is_blacklisted("bad_*")
    assert client_acl.user_is_blacklisted("user_bad_")
    assert client_acl.user_is_blacklisted("blocked_")
    assert client_acl.user_is_blacklisted("blocked_user")
    assert client_acl.user_is_blacklisted("blocked_.*")
    assert client_acl.user_is_blacklisted("Homer")

    assert not client_acl.user_is_blacklisted("batman")
    assert not client_acl.user_is_blacklisted("robin")
    assert not client_acl.user_is_blacklisted("bad")
    assert not client_acl.user_is_blacklisted("blocked")
    assert not client_acl.user_is_blacklisted("NotHomer")
    assert not client_acl.user_is_blacklisted("HomerSimpson")


def test_cmd_is_blacklisted(blacklist):
    """
    test cmd_is_blacklisted
    """
    client_acl = acl.PublisherACL(blacklist)

    assert client_acl.cmd_is_blacklisted("cmd.run")
    assert client_acl.cmd_is_blacklisted("test.fib")
    assert client_acl.cmd_is_blacklisted("rm-rf.root")

    assert not client_acl.cmd_is_blacklisted("cmd.shell")
    assert not client_acl.cmd_is_blacklisted("test.versions")
    assert not client_acl.cmd_is_blacklisted("arm-rf.root")

    assert client_acl.cmd_is_blacklisted(["cmd.run", "state.sls"])
    assert not client_acl.cmd_is_blacklisted(["state.highstate", "state.sls"])


def test_user_is_whitelisted(whitelist):
    """
    test user_is_whitelisted
    """
    client_acl = acl.PublisherACL(whitelist)

    assert client_acl.user_is_whitelisted("testuser")
    assert client_acl.user_is_whitelisted("saltuser")
    assert not client_acl.user_is_whitelisted("three")
    assert not client_acl.user_is_whitelisted("hans")


def test_cmd_is_whitelisted(whitelist):
    """
    test cmd_is_whitelisted
    """
    client_acl = acl.PublisherACL(whitelist)

    assert client_acl.cmd_is_whitelisted("test.ping")
    assert client_acl.cmd_is_whitelisted("grains.items")
    assert not client_acl.cmd_is_whitelisted("cmd.run")
    assert not client_acl.cmd_is_whitelisted("test.version")
