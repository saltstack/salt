"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    TestCase for salt.modules.serverdensity_device
"""

import pytest

import salt.modules.serverdensity_device as serverdensity_device
import salt.utils.json
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


class MockRequests:
    """
    Mock smtplib class
    """

    flag = None
    content = """{"message": "Invalid token", "errors": [{"type": "invalid_token", "subject": "token"}]}"""
    status_code = None

    def __init__(self):
        self.url = None
        self.data = None
        self.kwargs = None

    def return_request(self, url, data=None, **kwargs):
        """
        Mock request method.
        """
        self.url = url
        self.data = data
        self.kwargs = kwargs
        requests = MockRequests()
        if self.flag == 1:
            requests.status_code = 401
        else:
            requests.status_code = 200
        return requests

    def post(self, url, data=None, **kwargs):
        """
        Mock post method.
        """
        return self.return_request(url, data, **kwargs)

    def delete(self, url, **kwargs):
        """
        Mock delete method.
        """
        return self.return_request(url, **kwargs)

    def get(self, url, **kwargs):
        """
        Mock get method.
        """
        return self.return_request(url, **kwargs)

    def put(self, url, data=None, **kwargs):
        """
        Mock put method.
        """
        return self.return_request(url, data, **kwargs)


@pytest.fixture
def configure_loader_modules():
    return {serverdensity_device: {"requests": MockRequests()}}


@pytest.fixture
def mock_json_loads():
    return MagicMock(side_effect=ValueError())


def test_get_sd_auth():
    """
    Tests if it returns requested Server Density
    authentication value from pillar.
    """
    with patch.dict(serverdensity_device.__pillar__, {"serverdensity": False}):
        pytest.raises(CommandExecutionError, serverdensity_device.get_sd_auth, "1")

    with patch.dict(serverdensity_device.__pillar__, {"serverdensity": {"1": "salt"}}):
        assert serverdensity_device.get_sd_auth("1") == "salt"

        pytest.raises(CommandExecutionError, serverdensity_device.get_sd_auth, "2")


def test_create(mock_json_loads):
    """
    Tests if it create device in Server Density.
    """
    with patch.dict(
        serverdensity_device.__pillar__, {"serverdensity": {"api_token": "salt"}}
    ):
        assert serverdensity_device.create("rich_lama", group="lama_band")

        with patch.object(salt.utils.json, "loads", mock_json_loads):
            pytest.raises(
                CommandExecutionError,
                serverdensity_device.create,
                "rich_lama",
                group="lama_band",
            )

        MockRequests.flag = 1
        assert serverdensity_device.create("rich_lama", group="lama_band") is None


def test_delete(mock_json_loads):
    """
    Tests if it delete a device from Server Density.
    """
    with patch.dict(
        serverdensity_device.__pillar__, {"serverdensity": {"api_token": "salt"}}
    ):
        MockRequests.flag = 0
        assert serverdensity_device.delete("51f7eaf")

        with patch.object(salt.utils.json, "loads", mock_json_loads):
            pytest.raises(CommandExecutionError, serverdensity_device.delete, "51f7eaf")

        MockRequests.flag = 1
        assert serverdensity_device.delete("51f7eaf") is None


def test_ls(mock_json_loads):
    """
    Tests if it list devices in Server Density.
    """
    with patch.dict(
        serverdensity_device.__pillar__, {"serverdensity": {"api_token": "salt"}}
    ):
        MockRequests.flag = 0
        assert serverdensity_device.ls(name="lama")

        with patch.object(salt.utils.json, "loads", mock_json_loads):
            pytest.raises(CommandExecutionError, serverdensity_device.ls, name="lama")

        MockRequests.flag = 1
        assert serverdensity_device.ls(name="lama") is None


def test_update(mock_json_loads):
    """
    Tests if it updates device information in Server Density.
    """
    with patch.dict(
        serverdensity_device.__pillar__, {"serverdensity": {"api_token": "salt"}}
    ):
        MockRequests.flag = 0
        assert serverdensity_device.update("51f7eaf", name="lama")

        with patch.object(salt.utils.json, "loads", mock_json_loads):
            pytest.raises(
                CommandExecutionError,
                serverdensity_device.update,
                "51f7eaf",
                name="lama",
            )

        MockRequests.flag = 1
        assert serverdensity_device.update("51f7eaf", name="lama") is None


def test_install_agent():
    """
    Tests if it downloads Server Density installation agent,
    and installs sd-agent with agent_key.
    """
    mock = MagicMock(return_value=True)
    with patch.dict(
        serverdensity_device.__pillar__, {"serverdensity": {"account_url": "salt"}}
    ):
        with patch.dict(serverdensity_device.__salt__, {"cmd.run": mock}):
            with patch.dict(serverdensity_device.__opts__, {"cachedir": "/"}):
                assert serverdensity_device.install_agent("51f7e")


def test_install_agent_v2():
    """
    Tests if it downloads Server Density installation agent,
    and installs sd-agent with agent_key.
    """
    mock = MagicMock(return_value=True)
    with patch.dict(
        serverdensity_device.__pillar__, {"serverdensity": {"account_name": "salt"}}
    ):
        with patch.dict(serverdensity_device.__salt__, {"cmd.run": mock}):
            with patch.dict(serverdensity_device.__opts__, {"cachedir": "/"}):
                assert serverdensity_device.install_agent("51f7e", agent_version=2)
