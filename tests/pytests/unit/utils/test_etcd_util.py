"""
    Test cases for salt.utils.etcd_util

    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.utils.etcd_util as etcd_util
from tests.support.mock import MagicMock, patch

if etcd_util.HAS_ETCD_V2:
    import etcd
    from urllib3.exceptions import MaxRetryError, ReadTimeoutError


def _version_id(value):
    return "etcd-v2" if value else "etcd-v3"


@pytest.fixture(scope="module", params=(True, False), ids=_version_id)
def use_v2(request):
    if request.param and not etcd_util.HAS_ETCD_V2:
        pytest.skip("No etcd library installed")
    if not request.param and not etcd_util.HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return request.param


@pytest.fixture(scope="module")
def client_name(use_v2):
    if use_v2:
        return "etcd.Client"
    return "etcd3.Client"


def test_read(client_name, use_v2):
    """
    Test to make sure we interact with etcd correctly
    """
    with patch(client_name, autospec=True) as mock:
        etcd_client = mock.return_value
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )
        if use_v2:
            etcd_return = MagicMock(value="salt")
            etcd_client.read.return_value = etcd_return

            assert client.read("/salt") == etcd_return
            etcd_client.read.assert_called_with(
                "/salt", recursive=False, wait=False, timeout=None
            )

            client.read("salt", True, True, 10, 5)
            etcd_client.read.assert_called_with(
                "salt", recursive=True, wait=True, timeout=10, waitIndex=5
            )

            etcd_client.read.side_effect = etcd.EtcdKeyNotFound
            with pytest.raises(etcd.EtcdKeyNotFound):
                client.read("salt")

            etcd_client.read.side_effect = etcd.EtcdConnectionFailed
            with pytest.raises(etcd.EtcdConnectionFailed):
                client.read("salt")

            etcd_client.read.side_effect = etcd.EtcdValueError
            with pytest.raises(etcd.EtcdValueError):
                client.read("salt")

            etcd_client.read.side_effect = ValueError
            with pytest.raises(ValueError):
                client.read("salt")

            etcd_client.read.side_effect = ReadTimeoutError(None, None, None)
            with pytest.raises(etcd.EtcdConnectionFailed):
                client.read("salt")

            etcd_client.read.side_effect = MaxRetryError(None, None)
            with pytest.raises(etcd.EtcdConnectionFailed):
                client.read("salt")
        else:
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


def test_get(client_name, use_v2):
    """
    Test if it get a value from etcd, by direct path
    """
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )

        if use_v2:
            with patch.object(client, "read", autospec=True) as mock:
                mock.return_value = MagicMock(value="stack")
                assert client.get("salt") == "stack"
                mock.assert_called_with("salt")

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([etcd.EtcdKeyNotFound()])
                assert client.get("not-found") is None

                mock.side_effect = iter([etcd.EtcdConnectionFailed()])
                assert client.get("watching") is None

                # python 2.6 test
                mock.side_effect = ValueError
                assert client.get("not-found") is None

                mock.side_effect = Exception
                with pytest.raises(Exception):
                    client.get("some-error")
        else:
            with patch.object(client, "read", autospec=True) as mock:
                mock.return_value = [MagicMock(value="stack")]
                assert client.get("salt") == "stack"
                mock.assert_called_with("salt")

        # Get with recurse now delegates to client.tree
        with patch.object(client, "tree", autospec=True) as tree_mock:
            tree_mock.return_value = {"salt": "stack"}
            assert client.get("salt", recurse=True) == {"salt": "stack"}
            tree_mock.assert_called_with("salt")


def test_tree(use_v2, client_name):
    """
    Test recursive gets
    """
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )

        if use_v2:
            with patch.object(client, "read", autospec=True) as mock:
                c1, c2 = MagicMock(), MagicMock()
                c1.__iter__.return_value = [
                    MagicMock(key="/x/a", value="1"),
                    MagicMock(key="/x/b", value="2"),
                    MagicMock(key="/x/c", dir=True),
                ]
                c2.__iter__.return_value = [MagicMock(key="/x/c/d", value="3")]
                mock.side_effect = iter(
                    [MagicMock(children=c1), MagicMock(children=c2)]
                )
                assert client.tree("/x") == {"a": "1", "b": "2", "c": {"d": "3"}}
                mock.assert_any_call("/x")
                mock.assert_any_call("/x/c")

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([etcd.EtcdKeyNotFound()])
                assert client.tree("not-found") is None

                mock.side_effect = ValueError
                assert client.tree("/x") is None

                mock.side_effect = Exception
                with pytest.raises(Exception):
                    client.tree("some-error")
        else:
            with patch.object(client, "read", autospec=True) as mock:
                mock.return_value = [
                    MagicMock(key="/x/a", value="1"),
                    MagicMock(key="/x/b", value="2"),
                    MagicMock(key="/x/c/d", value="3"),
                ]
                assert client.tree("/x") == {"a": "1", "b": "2", "c": {"d": "3"}}
                mock.assert_called_with("/x", recurse=True)


def test_ls(use_v2, client_name):
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )

        if use_v2:
            with patch.object(client, "read", autospec=True) as mock:
                c1 = MagicMock()
                c1.__iter__.return_value = [
                    MagicMock(key="/x/a", value="1"),
                    MagicMock(key="/x/b", value="2"),
                    MagicMock(key="/x/c", dir=True),
                ]
                mock.return_value = MagicMock(children=c1)
                assert client.ls("/x") == {
                    "/x": {"/x/a": "1", "/x/b": "2", "/x/c/": {}}
                }
                mock.assert_called_with("/x")

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([etcd.EtcdKeyNotFound()])
                assert client.ls("/not-found") == {}

                mock.side_effect = Exception
                with pytest.raises(Exception):
                    client.tree("some-error")
        else:
            with patch.object(client, "read", autospec=True) as mock:
                mock.return_value = [
                    MagicMock(key="/x/a", value="1"),
                    MagicMock(key="/x/b", value="2"),
                    MagicMock(key="/x/c", value={"d": "3"}),
                ]
                assert client.ls("/x") == {
                    "/x": {"/x/a": "1", "/x/b": "2", "/x/c/": {}}
                }
                mock.assert_called_with("/x", recurse=True)


def test_write(use_v2, client_name):
    with patch(client_name, autospec=True) as mock:
        etcd_client = mock.return_value
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )

        if use_v2:
            etcd_client.write.return_value = MagicMock(value="salt")
            assert client.write("/some-key", "salt") == "salt"
            etcd_client.write.assert_called_with(
                "/some-key", "salt", ttl=None, dir=False
            )

            assert client.write("/some-key", "salt", ttl=5) == "salt"
            etcd_client.write.assert_called_with("/some-key", "salt", ttl=5, dir=False)

            etcd_client.write.return_value = MagicMock(dir=True)
            assert client.write("/some-dir", "salt", ttl=0, directory=True)
            etcd_client.write.assert_called_with("/some-dir", None, ttl=0, dir=True)

            # Check when a file is attempted to be written to a read-only root
            etcd_client.write.side_effect = etcd.EtcdRootReadOnly()
            assert client.write("/", "some-val", directory=False) is None

            # Check when a directory is attempted to be written to a read-only root
            etcd_client.write.side_effect = etcd.EtcdRootReadOnly()
            assert client.write("/", None, directory=True) is None

            # Check when a file is attempted to be written when unable to connect to the service
            etcd_client.write.side_effect = MaxRetryError(None, None)
            assert client.write("/some-key", "some-val", directory=False) is None

            # Check when a directory is attempted to be written when unable to connect to the service
            etcd_client.write.side_effect = MaxRetryError(None, None)
            assert client.write("/some-dir", None, directory=True) is None

            # Check when a file is attempted to be written to a directory that already exists (name-collision)
            etcd_client.write.side_effect = etcd.EtcdNotFile()
            assert client.write("/some-dir", "some-val", directory=False) is None

            # Check when a directory is attempted to be written to a file that already exists (name-collision)
            etcd_client.write.side_effect = etcd.EtcdNotDir()
            assert client.write("/some-key", None, directory=True) is None

            # Check when a directory is attempted to be written to a directory that already exists (update-ttl)
            etcd_client.write.side_effect = etcd.EtcdNotFile()
            assert client.write("/some-dir", None, directory=True)

            etcd_client.write.side_effect = ValueError
            assert client.write("/some-key", "some-val") is None

            etcd_client.write.side_effect = Exception
            with pytest.raises(Exception):
                client.set("some-key", "some-val")
        else:
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


def test_flatten(use_v2, client_name):
    with patch(client_name, autospec=True) as mock:
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )
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


def test_update(use_v2, client_name):
    with patch(client_name, autospec=True) as mock:
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )
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
            if not use_v2:
                result.pop("/test/d")
            assert client.update(some_data, path="/test") == result
            client._flatten.assert_called_with(some_data, "/test")
            assert write_mock.call_count == 5 if use_v2 else 4


def test_rm(use_v2, client_name):
    with patch(client_name, autospec=True) as mock:
        etcd_client = mock.return_value
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )

        if use_v2:
            etcd_client.delete.return_value = True
            assert client.rm("/some-key")
            etcd_client.delete.assert_called_with("/some-key", recursive=False)
            assert client.rm("/some-dir", recurse=True)
            etcd_client.delete.assert_called_with("/some-dir", recursive=True)

            etcd_client.delete.side_effect = etcd.EtcdNotFile()
            assert client.rm("/some-dir") is None

            etcd_client.delete.side_effect = etcd.EtcdDirNotEmpty()
            assert client.rm("/some-key") is None

            etcd_client.delete.side_effect = etcd.EtcdRootReadOnly()
            assert client.rm("/") is None

            etcd_client.delete.side_effect = ValueError
            assert client.rm("/some-dir") is None

            etcd_client.delete.side_effect = Exception
            with pytest.raises(Exception):
                client.rm("some-dir")
        else:
            etcd_client.delete_range.return_value = MagicMock(deleted=1)
            assert client.rm("/some-key")
            etcd_client.delete_range.assert_called_with("/some-key", prefix=False)

            etcd_client.delete_range.return_value = MagicMock(deleted=0)
            assert client.rm("/some-key", recurse=True) is None
            etcd_client.delete_range.assert_called_with("/some-key", prefix=True)

            delattr(etcd_client.delete_range.return_value, "deleted")
            assert not client.rm("/some-key")
            etcd_client.delete_range.assert_called_with("/some-key", prefix=False)


def test_watch(use_v2, client_name):
    with patch(client_name, autospec=True):
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )

        if use_v2:
            with patch.object(client, "read", autospec=True) as mock:
                mock.return_value = MagicMock(
                    value="stack", key="/some-key", modifiedIndex=1, dir=False
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

                mock.side_effect = iter(
                    [etcd_util.EtcdUtilWatchTimeout, mock.return_value]
                )
                assert client.watch("/some-key") == {
                    "value": "stack",
                    "changed": False,
                    "mIndex": 1,
                    "key": "/some-key",
                    "dir": False,
                }

                mock.side_effect = iter(
                    [etcd_util.EtcdUtilWatchTimeout, etcd.EtcdKeyNotFound]
                )
                assert client.watch("/some-key") == {
                    "value": None,
                    "changed": False,
                    "mIndex": 0,
                    "key": "/some-key",
                    "dir": False,
                }

                mock.side_effect = iter([etcd_util.EtcdUtilWatchTimeout, ValueError])
                assert client.watch("/some-key") == {}

                mock.side_effect = None
                mock.return_value = MagicMock(
                    value="stack", key="/some-key", modifiedIndex=1, dir=True
                )
                assert client.watch(
                    "/some-dir", recurse=True, timeout=5, start_revision=10
                ) == {
                    "value": "stack",
                    "key": "/some-key",
                    "mIndex": 1,
                    "changed": True,
                    "dir": True,
                }
                mock.assert_called_with(
                    "/some-dir", wait=True, recurse=True, timeout=5, start_revision=10
                )

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([MaxRetryError(None, None)])
                assert client.watch("/some-key") == {}

                mock.side_effect = iter([etcd.EtcdConnectionFailed()])
                assert client.watch("/some-key") is None

                mock.side_effect = None
                mock.return_value = None
                assert client.watch("/some-key") == {}
        else:
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


def test_expand(use_v2, client_name):
    if use_v2:
        pytest.skip("No expand in etcd v2 adapter")

    with patch(client_name, autospec=True) as mock:
        client = etcd_util.get_conn(
            {"etcd.require_v2": use_v2, "etcd.encode_values": False}
        )

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
