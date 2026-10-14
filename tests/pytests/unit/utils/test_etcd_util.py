"""
    Test cases for salt.utils.etcd_util

    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.utils.etcd_util as etcd_util
from tests.support.mock import MagicMock, patch


@pytest.fixture(scope="module")
def client_name():
    if not etcd_util.HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return "etcd3.Client"


def test_read(client_name):
    """
    Test to make sure we interact with etcd correctly
    """
    with patch(client_name, autospec=True) as mock:
        etcd_client = mock.return_value
        client = etcd_util.get_conn({"etcd.encode_values": False})
        etcd_return = MagicMock(kvs=[MagicMock(value="salt")])
        etcd_client.range.return_value = etcd_return
        assert client.read("/salt") == etcd_return.kvs
        etcd_client.range.assert_called_with("/salt", prefix=False)

        etcd_client.range.side_effect = Exception
        assert client.read("/salt") is None

        watcher_mock = MagicMock()
        with patch.object(etcd_client, "Watcher", return_value=watcher_mock):
            client.read("salt", True, True, 10, 5)
            etcd_client.range.assert_called_with("/salt", prefix=False)
            watcher_mock.watch_once.assert_called_with(timeout=10)

            watcher_mock.watch_once.side_effect = Exception
            assert client.read("salt", True, True, 10, 5) is None


def test_get(client_name):
    """
    Test if it get a value from etcd, by direct path
    """
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn({"etcd.encode_values": False})

        with patch.object(client, "read", autospec=True) as mock:
            mock.return_value = [MagicMock(value="stack")]
            assert client.get("salt") == "stack"
            mock.assert_called_with("salt")

        # Get with recurse now delegates to client.tree
        with patch.object(client, "tree", autospec=True) as tree_mock:
            tree_mock.return_value = {"salt": "stack"}
            assert client.get("salt", recurse=True) == {"salt": "stack"}
            tree_mock.assert_called_with("salt")


def test_tree(client_name):
    """
    Test recursive gets
    """
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn({"etcd.encode_values": False})

        with patch.object(client, "read", autospec=True) as mock:
            mock.return_value = [
                MagicMock(key="/x/a", value="1"),
                MagicMock(key="/x/b", value="2"),
                MagicMock(key="/x/c/d", value="3"),
            ]
            assert client.tree("/x") == {"a": "1", "b": "2", "c": {"d": "3"}}
            mock.assert_called_with("/x", recurse=True)


def test_ls(client_name):
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn({"etcd.encode_values": False})

        with patch.object(client, "read", autospec=True) as mock:
            mock.return_value = [
                MagicMock(key="/x/a", value="1"),
                MagicMock(key="/x/b", value="2"),
                MagicMock(key="/x/c", value={"d": "3"}),
            ]
            assert client.ls("/x") == {"/x": {"/x/a": "1", "/x/b": "2", "/x/c/": {}}}
            mock.assert_called_with("/x", recurse=True)


def test_write(client_name):
    with patch(client_name, autospec=True) as mock:
        etcd_client = mock.return_value
        client = etcd_util.get_conn({"etcd.encode_values": False})

        with pytest.raises(etcd_util.Etcd3DirectoryException):
            client.write("key", None, directory=True)

        with patch.object(client, "get", autospec=True) as get_mock:
            get_mock.return_value = "stack"
            assert client.write("salt", "stack") == "stack"
            etcd_client.put.assert_called_with("salt", "stack")

            lease_mock = MagicMock(ID=1)
            with patch.object(etcd_client, "Lease", return_value=lease_mock):
                assert client.write("salt", "stack", ttl=5) == "stack"
                etcd_client.put.assert_called_with("salt", "stack", lease=1)


def test_flatten(client_name):
    with patch(client_name, autospec=True) as mock:
        client = etcd_util.get_conn({"etcd.encode_values": False})
        some_data = {
            "/x/y/a": "1",
            "x": {"y": {"b": "2"}},
            "m/j/": "3",
            "z": "4",
            "d": {},
        }

        result_path = {
            "/test/x/y/a": "1",
            "/test/x/y/b": "2",
            "/test/m/j": "3",
            "/test/z": "4",
            "/test/d": {},
        }

        result_nopath = {
            "/x/y/a": "1",
            "/x/y/b": "2",
            "/m/j": "3",
            "/z": "4",
            "/d": {},
        }

        result_root = {
            "/x/y/a": "1",
            "/x/y/b": "2",
            "/m/j": "3",
            "/z": "4",
            "/d": {},
        }

        assert client._flatten(some_data, path="/test") == result_path
        assert client._flatten(some_data, path="/") == result_root
        assert client._flatten(some_data) == result_nopath


def test_update(client_name):
    with patch(client_name, autospec=True) as mock:
        client = etcd_util.get_conn({"etcd.encode_values": False})
        some_data = {
            "/x/y/a": "1",
            "x": {"y": {"b": "3"}},
            "m/j/": "3",
            "z": "4",
            "d": {},
        }

        result = {
            "/test/x/y/a": "1",
            "/test/x/y/b": "2",
            "/test/m/j": "3",
            "/test/z": "4",
            "/test/d": True,
        }

        flatten_result = {
            "/test/x/y/a": "1",
            "/test/x/y/b": "2",
            "/test/m/j": "3",
            "/test/z": "4",
            "/test/d": {},
        }
        client._flatten = MagicMock(return_value=flatten_result)

        assert client.update("/some/key", path="/blah") is None

        with patch.object(client, "write", autospec=True) as write_mock:

            def write_return(key, val, ttl=None, directory=None):
                return result.get(key, None)

            write_mock.side_effect = write_return
            result.pop("/test/d")
            assert client.update(some_data, path="/test") == result
            client._flatten.assert_called_with(some_data, "/test")
            assert write_mock.call_count == 4


def test_rm(client_name):
    with patch(client_name, autospec=True) as mock:
        etcd_client = mock.return_value
        client = etcd_util.get_conn({"etcd.encode_values": False})

        etcd_client.delete_range.return_value = MagicMock(deleted=1)
        assert client.rm("/some-key")
        etcd_client.delete_range.assert_called_with("/some-key", prefix=False)

        etcd_client.delete_range.return_value = MagicMock(deleted=0)
        assert client.rm("/some-key", recurse=True) is None
        etcd_client.delete_range.assert_called_with("/some-key", prefix=True)

        delattr(etcd_client.delete_range.return_value, "deleted")
        assert not client.rm("/some-key")
        etcd_client.delete_range.assert_called_with("/some-key", prefix=False)


def test_watch(client_name):
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn({"etcd.encode_values": False})

        with patch.object(client, "read", autospec=True) as mock:
            mock.return_value = MagicMock(
                value="stack", key="/some-key", mod_revision=1
            )
            assert client.watch("/some-key") == {
                "value": "stack",
                "key": "/some-key",
                "mIndex": 1,
                "changed": True,
                "dir": False,
            }
            mock.assert_called_with(
                "/some-key",
                wait=True,
                recurse=False,
                timeout=0,
                start_revision=None,
            )
            mock.return_value = MagicMock(
                value="stack", key="/some-key", mod_revision=1
            )
            assert client.watch(
                "/some-key", recurse=True, timeout=5, start_revision=10
            ) == {
                "value": "stack",
                "key": "/some-key",
                "mIndex": 1,
                "changed": True,
                "dir": False,
            }
            mock.assert_called_with(
                "/some-key", wait=True, recurse=True, timeout=5, start_revision=10
            )

            mock.side_effect = None
            mock.return_value = None
            assert client.watch("/some-key") is None


def test_expand(client_name):

    with patch(client_name, autospec=True) as mock:
        client = etcd_util.get_conn({"etcd.encode_values": False})

        some_data = {
            "/test/x/y/a": "1",
            "/test/x/y/b": "2",
            "/test/m/j": "3",
            "/test/z": "4",
        }

        result = {
            "test": {
                "x": {"y": {"a": "1", "b": "2"}},
                "m": {"j": "3"},
                "z": "4",
            },
        }

        assert client._expand(some_data) == result


def test_get_conn_defaults_to_v3():
    with patch.object(etcd_util, "EtcdClientV3") as client_class:
        assert etcd_util.get_conn({}) is client_class.return_value
        client_class.assert_called_once_with({}, has_etcd_opts=True)


def test_get_conn_accepts_explicit_v3_profile():
    profile = {"etcd.require_v2": False, "etcd.host": "etcd.example"}
    with patch.object(etcd_util, "EtcdClientV3") as client_class:
        client = etcd_util.get_conn({"cluster": profile}, profile="cluster")
        assert client is client_class.return_value
        client_class.assert_called_once_with(profile, has_etcd_opts=True)


@pytest.mark.parametrize("profile", [None, "cluster"])
def test_get_conn_rejects_v2(profile):
    config = {"etcd.require_v2": True}
    opts = config if profile is None else {profile: config}
    with patch.object(etcd_util, "EtcdClientV3") as client_class:
        with pytest.raises(
            etcd_util.IncompatibleEtcdRequirements, match="removed in Salt 3009"
        ):
            etcd_util.get_conn(opts, profile=profile)
        client_class.assert_not_called()


def test_v3_constructor_defaults_to_v3():
    with patch.object(etcd_util, "HAS_ETCD_V3", True), patch.object(
        etcd_util, "etcd3", create=True
    ) as library:
        client = etcd_util.EtcdClientV3({})
        assert client.client is library.Client.return_value
        library.Client.assert_called_once_with(host="127.0.0.1", port=2379, verify=None)


def test_v3_constructor_rejects_v2():
    with patch.object(etcd_util, "HAS_ETCD_V3", True), patch.object(
        etcd_util, "etcd3", create=True
    ) as library:
        with pytest.raises(
            etcd_util.IncompatibleEtcdRequirements, match="removed in Salt 3009"
        ):
            etcd_util.EtcdClientV3({"etcd.require_v2": True})
        library.Client.assert_not_called()
