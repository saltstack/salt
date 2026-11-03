"""
    Test cases for salt.utils.etcd_util

    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import json

import pytest
import requests.exceptions

import salt.exceptions
import salt.utils.etcd_util as etcd_util
from tests.support.mock import MagicMock, patch

try:
    import etcd3gw.exceptions
except ImportError:
    pass


@pytest.fixture(autouse=True)
def _skip_without_etcd3gw():
    if not etcd_util.HAS_ETCD_V3:
        pytest.skip("etcd3gw is not installed")


@pytest.fixture
def etcd_client():
    """
    The etcd3gw client instance that ``EtcdClientV3`` builds.
    """
    with patch.object(etcd_util, "_client_class") as client_class:
        yield client_class.return_value.return_value


def test_get_conn_rejects_require_v2():
    """
    ``etcd.require_v2: True`` was supported until 3009.0. It must now raise
    rather than silently fall back to v3.
    """
    with pytest.raises(salt.exceptions.CommandExecutionError, match="3009.0"):
        etcd_util.get_conn({"etcd.require_v2": True})


def test_read(etcd_client):
    """
    Test to make sure we interact with etcd correctly
    """
    client = etcd_util.get_conn({"etcd.encode_values": False})

    etcd_client.get.return_value = [
        (b"salt", {"key": b"/salt", "mod_revision": "3", "version": "1"})
    ]
    result = client.read("/salt")
    assert [(kv.key, kv.value, kv.mod_revision, kv.version) for kv in result] == [
        ("/salt", "salt", 3, 1)
    ]
    etcd_client.get.assert_called_with("/salt", metadata=True)

    client.read("/salt", recurse=True)
    etcd_client.get.assert_called_with("/salt", metadata=True, range_end=b"/salu")

    etcd_client.get.return_value = []
    assert client.read("/salt") is None

    etcd_client.get.side_effect = Exception
    assert client.read("/salt") is None


def test_read_wait(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})

    etcd_client.watch_once.return_value = {
        "kv": {"key": b"salt", "value": b"stack", "mod_revision": "7"}
    }
    result = client.read("salt", True, True, 10, 5)
    assert (result.key, result.value, result.mod_revision) == ("salt", "stack", 7)
    etcd_client.watch_once.assert_called_with(
        "salt", timeout=10, range_end=b"salu", start_revision=5
    )

    client.read("salt", wait=True, timeout=10)
    etcd_client.watch_once.assert_called_with("salt", timeout=10)

    # A delete event carries no value.
    etcd_client.watch_once.return_value = {"kv": {"key": b"salt", "mod_revision": "8"}}
    result = client.read("salt", wait=True, timeout=10)
    assert (result.key, result.value) == ("salt", None)

    etcd_client.watch_once.side_effect = Exception
    assert client.read("salt", True, True, 10, 5) is None


def test_read_rejects_recursive_kwarg(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})
    with pytest.raises(
        salt.exceptions.SaltInvocationError, match="was removed in 3009.0"
    ):
        client.read("/salt", recursive=True)


def test_read_rejects_waitindex_kwarg(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})
    with pytest.raises(
        salt.exceptions.SaltInvocationError, match="was removed in 3009.0"
    ):
        client.read("/salt", waitIndex=5)


def test_watch_rejects_index_kwarg(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})
    with pytest.raises(
        salt.exceptions.SaltInvocationError, match="was removed in 3009.0"
    ):
        client.watch("/salt", index=5)


def test_delete_rejects_recursive_kwarg(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})
    with pytest.raises(
        salt.exceptions.SaltInvocationError, match="was removed in 3009.0"
    ):
        client.delete("/salt", recursive=True)


def test_get(etcd_client):
    """
    Test if it get a value from etcd, by direct path
    """
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


def test_tree(etcd_client):
    """
    Test recursive gets
    """
    client = etcd_util.get_conn({"etcd.encode_values": False})

    with patch.object(client, "read", autospec=True) as mock:
        mock.return_value = [
            MagicMock(key="/x/a", value="1"),
            MagicMock(key="/x/b", value="2"),
            MagicMock(key="/x/c/d", value="3"),
        ]
        assert client.tree("/x") == {"a": "1", "b": "2", "c": {"d": "3"}}
        mock.assert_called_with("/x", recurse=True)


def test_ls(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})

    with patch.object(client, "read", autospec=True) as mock:
        mock.return_value = [
            MagicMock(key="/x/a", value="1"),
            MagicMock(key="/x/b", value="2"),
            MagicMock(key="/x/c", value={"d": "3"}),
        ]
        assert client.ls("/x") == {"/x": {"/x/a": "1", "/x/b": "2", "/x/c/": {}}}
        mock.assert_called_with("/x", recurse=True)


def test_write(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})

    with pytest.raises(etcd_util.Etcd3DirectoryException):
        client.write("key", None, directory=True)

    with patch.object(client, "get", autospec=True) as get_mock:
        get_mock.return_value = "stack"
        assert client.write("salt", "stack") == "stack"
        etcd_client.put.assert_called_with("salt", "stack")

        assert client.write("salt", "stack", ttl=5) == "stack"
        etcd_client.lease.assert_called_with(ttl=5)
        etcd_client.put.assert_called_with(
            "salt", "stack", lease=etcd_client.lease.return_value
        )


def test_flatten(etcd_client):
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


def test_update(etcd_client):
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
        # v3 skips directory entries (they don't exist in v3), so we pop
        # the directory entry from the expected result.
        result.pop("/test/d")
        assert client.update(some_data, path="/test") == result
        client._flatten.assert_called_with(some_data, "/test")
        assert write_mock.call_count == 4


def test_rm(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})

    etcd_client.delete.return_value = True
    assert client.rm("/some-key") is True
    etcd_client.delete.assert_called_with("/some-key")

    etcd_client.delete.return_value = False
    assert client.rm("/some-key", recurse=True) is None
    etcd_client.delete.assert_called_with("/some-key", range_end=b"/some-kez")


def test_watch(etcd_client):
    client = etcd_util.get_conn({"etcd.encode_values": False})

    with patch.object(client, "read", autospec=True) as mock:
        mock.return_value = MagicMock(value="stack", key="/some-key", mod_revision=1)
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
        mock.return_value = MagicMock(value="stack", key="/some-key", mod_revision=1)
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


def test_expand(etcd_client):
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
            salt.exceptions.CommandExecutionError, match="removed in 3009.0"
        ):
            etcd_util.get_conn(opts, profile=profile)
        client_class.assert_not_called()


def test_v3_constructor_builds_etcd3gw_client():
    with patch.object(etcd_util, "_client_class") as client_class:
        client = etcd_util.EtcdClientV3({})
        assert client.client is client_class.return_value.return_value
        client_class.return_value.assert_called_once_with(host="127.0.0.1", port=2379)


def test_v3_constructor_passes_tls_and_credentials():
    opts = {
        "etcd.host": "etcd.example",
        "etcd.port": "2379",
        "etcd.username": "alice",
        "etcd.password": "secret",
        "etcd.ca": "/ca.pem",
        "etcd.client_cert": "/client.pem",
        "etcd.client_key": "/client-key.pem",
    }
    with patch.object(etcd_util, "_client_class") as client_class:
        etcd_util.EtcdClientV3(opts)
        client_class.return_value.assert_called_once_with(
            host="etcd.example",
            port=2379,
            protocol="https",
            ca_cert="/ca.pem",
            cert_cert="/client.pem",
            cert_key="/client-key.pem",
            username="alice",
            password="secret",
        )


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("/salt", b"/salu"),
        (b"/salt", b"/salu"),
        (b"/a\xff", b"/b"),
        (b"\xff\xff", b"\0"),
        ("", b"\0"),
    ],
)
def test_prefix_range_end(prefix, expected):
    assert etcd_util.prefix_range_end(prefix) == expected


def test_client_class_uses_native_auth_when_available():
    class NativeAuthClient:
        def __init__(self, host="localhost", username=None, password=None):
            pass

    with patch.object(etcd_util, "Etcd3Client", NativeAuthClient):
        assert etcd_util._client_class() is NativeAuthClient


def test_client_class_falls_back_to_auth_subclass():
    class OldClient:
        def __init__(self, host="localhost"):
            pass

    with patch.object(etcd_util, "Etcd3Client", OldClient):
        assert etcd_util._client_class() is etcd_util._AuthEtcd3Client


AUTH_URL = "http://127.0.0.1:2379/v3/auth/authenticate"
PUT_URL = "http://127.0.0.1:2379/v3/kv/put"
RANGE_URL = "http://127.0.0.1:2379/v3/kv/range"


def _response(status_code=200, body=None, reason="OK"):
    response = MagicMock(status_code=status_code, reason=reason)
    response.json.return_value = body if body is not None else {}
    response.text = json.dumps(body if body is not None else {})
    return response


def _unauthorized():
    return _response(
        401, {"code": 16, "message": "etcdserver: invalid auth token"}, "Unauthorized"
    )


@pytest.fixture
def auth_client():
    """
    An ``_AuthEtcd3Client`` whose session answers each URL from a queue.
    """
    client = etcd_util._AuthEtcd3Client(
        host="127.0.0.1", api_path="/v3/", username="alice", password="secret"
    )
    session = MagicMock()
    session.headers = {}
    session.queues = {}
    session.sent_tokens = []

    def post(url, *args, **kwargs):
        session.sent_tokens.append((url, session.headers.get("Authorization")))
        return session.queues[url].pop(0)

    session.post.side_effect = post
    client.session = session
    return client


def test_auth_client_authenticates_once(auth_client):
    session = auth_client.session
    session.queues = {
        AUTH_URL: [_response(body={"token": "tok1"})],
        PUT_URL: [_response(), _response()],
    }
    auth_client.put("/a", "1")
    auth_client.put("/a", "2")

    auth_calls = [c for c in session.post.call_args_list if c.args[0] == AUTH_URL]
    assert len(auth_calls) == 1
    assert auth_calls[0].kwargs["json"] == {"name": "alice", "password": "secret"}
    # No token, not even a stale one, is sent with the authenticate request.
    assert auth_calls[0].kwargs["headers"] == {"Authorization": None}
    assert [t for url, t in session.sent_tokens if url == PUT_URL] == ["tok1", "tok1"]


def test_auth_client_replaces_rejected_token(auth_client):
    session = auth_client.session
    session.queues = {
        AUTH_URL: [
            _response(body={"token": "tok1"}),
            _response(body={"token": "tok2"}),
        ],
        PUT_URL: [_unauthorized(), _response()],
    }
    assert auth_client.put("/a", "1") is True
    assert [t for url, t in session.sent_tokens if url == PUT_URL] == ["tok1", "tok2"]


def test_auth_client_retries_rejected_token_once(auth_client):
    session = auth_client.session
    session.queues = {
        AUTH_URL: [
            _response(body={"token": "tok1"}),
            _response(body={"token": "tok2"}),
        ],
        PUT_URL: [_unauthorized(), _unauthorized()],
    }
    with pytest.raises(etcd3gw.exceptions.Etcd3Exception):
        auth_client.put("/a", "1")
    assert len([u for u, _ in session.sent_tokens if u == PUT_URL]) == 2


def test_auth_client_does_not_retry_permission_denied(auth_client):
    session = auth_client.session
    session.queues = {
        AUTH_URL: [_response(body={"token": "tok1"})],
        PUT_URL: [
            _response(
                403,
                {"code": 7, "message": "etcdserver: permission denied"},
                "Forbidden",
            )
        ],
    }
    with pytest.raises(etcd3gw.exceptions.Etcd3Exception):
        auth_client.put("/b", "1")
    assert len([u for u, _ in session.sent_tokens if u == AUTH_URL]) == 1


def test_auth_client_bad_credentials(auth_client):
    auth_client.session.queues = {
        AUTH_URL: [
            _response(
                400,
                {
                    "code": 3,
                    "message": "etcdserver: authentication failed, invalid user ID or password",
                },
                "Bad Request",
            )
        ]
    }
    with pytest.raises(etcd3gw.exceptions.Etcd3Exception) as exc:
        auth_client.put("/a", "1")
    assert "invalid user ID or password" in exc.value.detail_text


def test_auth_client_connection_error_while_authenticating(auth_client):
    auth_client.session.post.side_effect = requests.exceptions.ConnectionError()
    with pytest.raises(etcd3gw.exceptions.ConnectionFailedError):
        auth_client.put("/a", "1")


def test_auth_client_skips_token_another_thread_replaced(auth_client):
    session = auth_client.session
    session.queues = {AUTH_URL: [_response(body={"token": "tok1"})]}
    auth_client._salt_authenticate()
    auth_client._salt_token = "tok2"
    session.headers["Authorization"] = "tok2"
    auth_client._salt_authenticate(rejected_token="tok1")
    assert len([u for u, _ in session.sent_tokens if u == AUTH_URL]) == 1


def test_auth_client_checks_token_before_watching(auth_client):
    with patch.object(auth_client, "get") as get, patch.object(
        etcd_util.Etcd3Client, "watch_once", return_value="event"
    ) as watch_once:
        assert auth_client.watch_once("/a", timeout=5) == "event"
    get.assert_called_once_with("/a", count_only=True)
    watch_once.assert_called_once_with("/a", timeout=5)


def test_auth_client_without_credentials_sends_no_token():
    client = etcd_util._AuthEtcd3Client(host="127.0.0.1", api_path="/v3/")
    with patch.object(client, "session") as session:
        session.headers = {}
        session.post.return_value = _response()
        client.put("/a", "1")
        assert session.post.call_count == 1
        assert "Authorization" not in session.headers
