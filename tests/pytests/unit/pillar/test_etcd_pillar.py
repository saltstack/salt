"""
Test cases for salt.pillar.etcd_pillar
"""

import pytest

import salt.pillar.etcd_pillar as etcd_pillar
import salt.utils.etcd_util
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {etcd_pillar: {"__opts__": {"my_etcd": {"etcd.port": 2379}}}}


@pytest.fixture
def get_conn():
    with patch("salt.utils.etcd_util.get_conn") as get_conn:
        yield get_conn


def test_virtual():
    with patch.object(salt.utils.etcd_util, "HAS_ETCD_V3", True):
        assert etcd_pillar.__virtual__() == "etcd"
    with patch.object(salt.utils.etcd_util, "HAS_ETCD_V3", False):
        assert etcd_pillar.__virtual__()[0] is False


def test_ext_pillar_defaults_to_root(get_conn):
    get_conn.return_value.tree.return_value = {"salt": {"key": "value"}}
    assert etcd_pillar.ext_pillar("minion1", {}, "my_etcd") == {
        "salt": {"key": "value"}
    }
    get_conn.assert_called_once_with(etcd_pillar.__opts__, "my_etcd")
    get_conn.return_value.tree.assert_called_once_with("/")


def test_ext_pillar_root_with_minion_id(get_conn):
    get_conn.return_value.tree.return_value = {"key": "value"}
    assert etcd_pillar.ext_pillar(
        "minion1", {}, "my_etcd root=/salt-private/%(minion_id)s"
    ) == {"key": "value"}
    get_conn.return_value.tree.assert_called_once_with("/salt-private/minion1")


def test_ext_pillar_missing_root(get_conn):
    get_conn.return_value.tree.return_value = None
    assert etcd_pillar.ext_pillar("minion1", {}, "my_etcd root=/nothing") == {}


def test_ext_pillar_errors_raise(get_conn):
    get_conn.return_value.tree.side_effect = CommandExecutionError(
        "etcd3: cannot read /: connection refused"
    )
    with pytest.raises(CommandExecutionError):
        etcd_pillar.ext_pillar("minion1", {}, "my_etcd")
