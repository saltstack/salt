"""
    Test cases for salt.pillar.etcd_pillar

    :codeauthor: Caleb Beard <calebb@vmware.com>
"""

import pytest

import salt.pillar.etcd_pillar as etcd_pillar
import salt.utils.etcd_util as etcd_util
from tests.support.mock import MagicMock, create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {etcd_pillar: {}}


@pytest.fixture
def instance():
    return create_autospec(etcd_util.EtcdBase)


@pytest.fixture
def etcd_client_mock(instance):
    mocked_client = MagicMock()
    mocked_client.return_value = instance
    return mocked_client


def test_ext_pillar(etcd_client_mock, instance):
    """
    Test ext_pillar functionality
    """
    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock):
        # Test pillar with no root given
        instance.tree.return_value = {"key": "value"}
        assert etcd_pillar.ext_pillar("test-id", {}, "etcd_profile") == {"key": "value"}
        instance.tree.assert_called_with("/")

        # Test pillar with a root given
        instance.tree.return_value = {"key": "value"}
        assert etcd_pillar.ext_pillar("test-id", {}, "etcd_profile root=/salt") == {
            "key": "value"
        }
        instance.tree.assert_called_with("/salt")

        # Test pillar with a root given that uses the minion id
        instance.tree.return_value = {"key": "value"}
        assert etcd_pillar.ext_pillar(
            "test-id", {}, "etcd_profile root=/salt/%(minion_id)s"
        ) == {"key": "value"}
        instance.tree.assert_called_with("/salt/test-id")

        # Test pillar with a root given that uses the minion id
        instance.tree.side_effect = KeyError
        assert etcd_pillar.ext_pillar("test-id", {"key": "value"}, "etcd_profile") == {}
