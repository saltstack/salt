"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import copy
import logging

import pytest
from saltfactories.utils import random_string

import salt.proxy.ssh_sample as ssh_sample_proxy
from salt.utils.vt import TerminalException
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def proxy_minion_config_module(salt_master_factory):
    factory = salt_master_factory.salt_proxy_minion_daemon(
        random_string("proxy-minion-"),
    )
    return factory.config


@pytest.fixture
def proxy_minion_config(proxy_minion_config_module):

    minion_config = copy.deepcopy(proxy_minion_config_module)
    minion_config["proxy"]["proxytype"] = "ssh_sample"
    minion_config["proxy"]["host"] = "localhost"
    minion_config["proxy"]["username"] = "username"
    minion_config["proxy"]["password"] = "password"
    return minion_config


@pytest.fixture
def configure_loader_modules():
    return {ssh_sample_proxy: {}}


class MockSSHConnection:
    def __init__(self, *args, **kwargs):
        return None

    def sendline(self, *args, **kwargs):
        return "", ""


def test_init(proxy_minion_config):
    """
    check ssh_sample_proxy init method
    """

    with patch(
        "salt.utils.vt_helper.SSHConnection",
        MagicMock(autospec=True, return_value=MockSSHConnection()),
    ):
        with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
            ssh_sample_proxy.init(proxy_minion_config)
            assert "server" in ssh_sample_proxy.__context__
            assert "initialized" in ssh_sample_proxy.__context__
            assert ssh_sample_proxy.__context__["initialized"]


def test_initialized(proxy_minion_config):
    """
    check ssh_sample_proxy initialized method
    """

    with patch(
        "salt.utils.vt_helper.SSHConnection",
        MagicMock(autospec=True, return_value=MockSSHConnection()),
    ):
        with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
            ssh_sample_proxy.init(proxy_minion_config)

            ret = ssh_sample_proxy.initialized()
            assert ret


def test_grains(proxy_minion_config):
    """
    check ssh_sample_proxy grains method
    """

    GRAINS_INFO = """{
  "os": "SshExampleOS",
  "kernel": "0.0000001",
  "housecat": "Are you kidding?"
}
"""
    mock_sendline = MagicMock(autospec=True, side_effect=[("", ""), (GRAINS_INFO, "")])
    with patch.object(MockSSHConnection, "sendline", mock_sendline):
        with patch(
            "salt.utils.vt_helper.SSHConnection",
            MagicMock(autospec=True, return_value=MockSSHConnection()),
        ):
            with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
                ssh_sample_proxy.init(proxy_minion_config)

                ret = ssh_sample_proxy.grains()
                assert "os" in ret
                assert "kernel" in ret
                assert "housecat" in ret

                assert ret["os"] == "SshExampleOS"
                assert ret["kernel"] == "0.0000001"
                assert ret["housecat"] == "Are you kidding?"

    # Read from __context__ cache
    mock_sendline = MagicMock(autospec=True, side_effect=[("", ""), (GRAINS_INFO, "")])
    mock_context = {
        "grains_cache": {
            "os": "SSH-ExampleOS",
            "kernel": "0.0000002",
            "dog": "Not kidding.",
        }
    }

    with patch.object(MockSSHConnection, "sendline", mock_sendline):
        with patch(
            "salt.utils.vt_helper.SSHConnection",
            MagicMock(autospec=True, return_value=MockSSHConnection()),
        ):
            with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
                with patch.dict(ssh_sample_proxy.__context__, mock_context):
                    ssh_sample_proxy.init(proxy_minion_config)

                    ret = ssh_sample_proxy.grains()
                    assert "os" in ret
                    assert "kernel" in ret
                    assert "dog" in ret

                    assert ret["os"] == "SSH-ExampleOS"
                    assert ret["kernel"] == "0.0000002"
                    assert ret["dog"] == "Not kidding."


def test_grains_refresh(proxy_minion_config):
    """
    check ssh_sample_proxy grains_refresh method
    """

    GRAINS_INFO = """{
  "os": "SshExampleOS",
  "kernel": "0.0000001",
  "housecat": "Are you kidding?"
}
"""

    mock_sendline = MagicMock(autospec=True, side_effect=[("", ""), (GRAINS_INFO, "")])
    mock_context = {
        "grains_cache": {
            "os": "SSH-ExampleOS",
            "kernel": "0.0000002",
            "dog": "Not kidding.",
        }
    }

    with patch.object(MockSSHConnection, "sendline", mock_sendline):
        with patch(
            "salt.utils.vt_helper.SSHConnection",
            MagicMock(autospec=True, return_value=MockSSHConnection()),
        ):
            with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
                with patch.dict(ssh_sample_proxy.__context__, mock_context):
                    ssh_sample_proxy.init(proxy_minion_config)

                    ret = ssh_sample_proxy.grains_refresh()
                    assert "os" in ret
                    assert "kernel" in ret
                    assert "housecat" in ret

                    assert ret["os"] == "SshExampleOS"
                    assert ret["kernel"] == "0.0000001"
                    assert ret["housecat"] == "Are you kidding?"


def test_fns():
    """
    check ssh_sample_proxy fns method
    """

    ret = ssh_sample_proxy.fns()

    assert "details" in ret
    assert ret["details"] == (
        "This key is here because a function in "
        "grains/ssh_sample.py called fns() here in the proxymodule."
    )


def test_ping(proxy_minion_config):
    """
    check ssh_sample_proxy ping method
    """

    mock_sendline = MagicMock(autospec=True, side_effect=[("", ""), ("", "")])
    with patch.object(MockSSHConnection, "sendline", mock_sendline):
        with patch(
            "salt.utils.vt_helper.SSHConnection",
            MagicMock(autospec=True, return_value=MockSSHConnection()),
        ):
            with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
                ssh_sample_proxy.init(proxy_minion_config)

                ret = ssh_sample_proxy.ping()
                assert ret

    mock_sendline = MagicMock(autospec=True, side_effect=[("", ""), TerminalException])
    with patch.object(MockSSHConnection, "sendline", mock_sendline):
        with patch(
            "salt.utils.vt_helper.SSHConnection",
            MagicMock(autospec=True, return_value=MockSSHConnection()),
        ):
            with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
                ssh_sample_proxy.init(proxy_minion_config)
                ret = ssh_sample_proxy.ping()
                assert not ret


def test_package_list(proxy_minion_config):
    """
    check ssh_sample_proxy package_list method
    """

    PKG_LIST = """{
  "coreutils": "1.05"
}
"""

    mock_sendline = MagicMock(autospec=True, side_effect=[("", ""), (PKG_LIST, "")])
    with patch.object(MockSSHConnection, "sendline", mock_sendline):
        with patch(
            "salt.utils.vt_helper.SSHConnection",
            MagicMock(autospec=True, return_value=MockSSHConnection()),
        ):
            with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
                ssh_sample_proxy.init(proxy_minion_config)

                ret = ssh_sample_proxy.package_list()
                assert ret
                assert "coreutils" in ret
                assert ret["coreutils"] == "1.05"


def test_package_install(proxy_minion_config):
    """
    check ssh_sample_proxy package_list method
    """
    PKG_INSTALL = """{
  "redbull": "1.0"
}
"""

    mock_sendline = MagicMock(autospec=True, side_effect=[("", ""), (PKG_INSTALL, "")])
    with patch.object(MockSSHConnection, "sendline", mock_sendline):
        with patch(
            "salt.utils.vt_helper.SSHConnection",
            MagicMock(autospec=True, return_value=MockSSHConnection()),
        ):
            with patch.dict(ssh_sample_proxy.__opts__, proxy_minion_config):
                ssh_sample_proxy.init(proxy_minion_config)

                ret = ssh_sample_proxy.package_install("redbull")
                assert ret
                assert "redbull" in ret
                assert ret["redbull"] == "1.0"
