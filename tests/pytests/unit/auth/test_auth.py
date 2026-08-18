import time

import salt.auth
import salt.config
import salt.exceptions
from tests.support.mock import MagicMock


def test_cve_2021_3244(tmp_path):
    token_dir = tmp_path / "tokens"
    token_dir.mkdir()
    opts = {
        "extension_modules": "",
        "optimization_order": [0, 1, 2],
        "token_expire": 1,
        "keep_acl_in_token": False,
        "eauth_tokens": "localfs",
        "token_dir": str(token_dir),
        "token_expire_user_override": True,
        "external_auth": {"auto": {"foo": []}},
    }
    auth = salt.auth.LoadAuth(opts)
    load = {
        "eauth": "auto",
        "username": "foo",
        "password": "foo",
        "token_expire": -1,
    }
    t_data = auth.mk_token(load)
    assert t_data["expire"] < time.time()
    token_file = token_dir / t_data["token"]
    assert token_file.exists()
    t_data = auth.get_tok(t_data["token"])
    assert not t_data
    assert not token_file.exists()


# ---------------------------------------------------------------------------
# ``LoadAuth.get_tok`` exception handling.
#
# A backend read failure must be classified by *cause*, not collapsed to
# "delete the token":
#
# * ``SaltDeserializationError`` — the stored blob cannot be parsed. The
#   token is permanently unusable; remove it so subsequent reads do not
#   keep failing on the same corrupt entry.
# * ``OSError`` / ``IOError`` — transient (Redis connection drop, NFS
#   hang, full disk). The token itself is fine. Returning ``{}`` while
#   leaving the token in place makes this request not-authenticated and
#   lets the next request retry once the backend recovers. **Deleting on
#   transient I/O errors logs every authenticated user out on every
#   backend hiccup**, which is the regression these tests guard against.
# * Expired (deserialized successfully but past ``expire``) — remove.
# ---------------------------------------------------------------------------


def _make_auth(tmp_path, get_token_side_effect):
    """Build a ``LoadAuth`` whose ``localfs.get_token`` is replaced by
    ``get_token_side_effect``. ``rm_token`` is wrapped with a
    ``MagicMock`` so the test can assert on whether the production code
    chose to delete the token. The backing token directory is real so
    ``rm_token`` would not blow up if it were called -- we are checking
    *intent*, not state."""
    token_dir = tmp_path / "tokens"
    token_dir.mkdir()
    opts = {
        "extension_modules": "",
        "optimization_order": [0, 1, 2],
        "token_expire": 60,
        "keep_acl_in_token": False,
        "eauth_tokens": "localfs",
        "token_dir": str(token_dir),
        "token_expire_user_override": False,
        "external_auth": {"auto": {"foo": []}},
    }
    auth = salt.auth.LoadAuth(opts)

    if callable(get_token_side_effect):
        auth.tokens["localfs.get_token"] = get_token_side_effect
    else:
        auth.tokens["localfs.get_token"] = MagicMock(side_effect=get_token_side_effect)

    auth.tokens["localfs.rm_token"] = MagicMock()
    return auth


def test_get_tok_returns_empty_and_keeps_token_on_io_error(tmp_path):
    """Headline regression: a transient backend error (e.g. Redis
    connection drop) must NOT cause the token to be deleted. The
    previous implementation either propagated the exception or deleted
    the token -- both wrong. Correct behaviour is to return ``{}`` and
    leave the token alone so the next request can retry."""
    auth = _make_auth(tmp_path, OSError("redis connection reset"))

    result = auth.get_tok("any-token-id")

    assert result == {}
    auth.tokens["localfs.rm_token"].assert_not_called()


def test_get_tok_removes_token_on_deserialization_error(tmp_path):
    """A corrupt token blob is permanently unusable; removing it is
    correct because every subsequent read would fail the same way."""
    auth = _make_auth(
        tmp_path,
        salt.exceptions.SaltDeserializationError("bad msgpack"),
    )

    result = auth.get_tok("corrupt-token-id")

    assert result == {}
    auth.tokens["localfs.rm_token"].assert_called_once_with(
        auth.opts, "corrupt-token-id"
    )


def test_get_tok_removes_expired_token(tmp_path):
    """Expired tokens are deserializable but past their ``expire``
    timestamp. They must be removed so the store does not accumulate
    dead entries."""
    expired_blob = {
        "token": "expired-token-id",
        "expire": time.time() - 60,
        "name": "foo",
        "eauth": "auto",
    }
    auth = _make_auth(tmp_path, lambda opts, tok: expired_blob)

    result = auth.get_tok("expired-token-id")

    assert result == {}
    auth.tokens["localfs.rm_token"].assert_called_once_with(
        auth.opts, "expired-token-id"
    )
