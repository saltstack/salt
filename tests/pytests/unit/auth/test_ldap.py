"""
Unit tests for salt.auth.ldap
"""

import pytest

import salt.auth.ldap
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        not salt.auth.ldap.HAS_LDAP, reason="Install python-ldap for this test"
    ),
]


class Bind:
    """
    fake search_s return
    """

    @staticmethod
    def search_s(*args, **kwargs):
        return [
            (
                "cn=saltusers,cn=groups,cn=compat,dc=saltstack,dc=com",
                {"memberUid": [b"saltuser"], "cn": [b"saltusers"]},
            ),
        ]


@pytest.fixture
def configure_loader_modules():
    return {
        salt.auth.ldap: {
            "__opts__": {
                "auth.ldap.binddn": (
                    "uid={{username}},cn=users,cn=compat,dc=saltstack,dc=com"
                ),
                "auth.ldap.port": 389,
                "auth.ldap.tls": False,
                "auth.ldap.server": "172.18.0.2",
                "auth.ldap.accountattributename": "memberUid",
                "auth.ldap.groupattribute": "memberOf",
                "auth.ldap.group_basedn": "cn=groups,cn=compat,dc=saltstack,dc=com",
                "auth.ldap.basedn": "dc=saltstack,dc=com",
                "auth.ldap.group_filter": (
                    "(&(memberUid={{ username }})(objectClass=posixgroup))"
                ),
            },
        },
    }


def test_config():
    """
    Test that the _config function works correctly
    """
    assert salt.auth.ldap._config("basedn") == "dc=saltstack,dc=com"
    assert (
        salt.auth.ldap._config("group_filter")
        == "(&(memberUid={{ username }})(objectClass=posixgroup))"
    )
    assert salt.auth.ldap._config("accountattributename") == "memberUid"
    assert salt.auth.ldap._config("groupattribute") == "memberOf"


def test_config_default_returned_when_not_set():
    """
    A non-mandatory config option that is not set returns the module default
    """
    assert salt.auth.ldap._config("freeipa", mandatory=False) is False
    assert salt.auth.ldap._config("activedirectory", mandatory=False) is False


def test_groups():
    """
    test groups in ldap
    """
    with patch("salt.auth.ldap._bind", return_value=Bind):
        assert "saltusers" in salt.auth.ldap.groups("saltuser", password="password")


def test_groups_freeipa():
    """
    test groups in freeipa
    """
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.freeipa": True}):
        with patch("salt.auth.ldap._bind", return_value=Bind):
            assert "saltusers" in salt.auth.ldap.groups("saltuser", password="password")


def test_groups_activedirectory():
    """
    test groups in activedirectory
    """
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.activedirectory": True}):
        with patch("salt.auth.ldap._bind", return_value=Bind):
            assert "saltusers" in salt.auth.ldap.groups("saltuser", password="password")


def test_groups_empty_when_bind_fails():
    """
    When the search bind fails, no groups are returned
    """
    with patch("salt.auth.ldap._bind", return_value=False):
        assert salt.auth.ldap.groups("saltuser", password="password") == []


# --- Group-membership re-check: standard (non-IPA) LDAP branch ---------------
#
# When a separate bind account (binddn + bindpw) is configured, the search uses
# _bind_for_search, and the user's credentials are re-checked with _bind. That
# re-check must only happen on the first payload of a job (when show_jid is
# present), so single-use 2FA credentials are not consumed more than once.


def test_groups_recheck_first_call_success():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            mock_bind = MagicMock(return_value=Bind)
            with patch("salt.auth.ldap._bind", mock_bind):
                result = salt.auth.ldap.groups(
                    "saltuser", password="password", show_jid="20240101000000000000"
                )
    assert "saltusers" in result
    mock_bind.assert_called_once()


def test_groups_recheck_first_call_failure():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            with patch("salt.auth.ldap._bind", MagicMock(return_value=False)):
                result = salt.auth.ldap.groups(
                    "saltuser", password="badpassword", show_jid="20240101000000000000"
                )
    assert result == []


def test_groups_recheck_skipped_without_show_jid():
    """
    Subsequent payloads (no show_jid) must not re-bind the user, even if the
    password would now fail - this is what makes single-use 2FA work.
    """
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            mock_bind = MagicMock(return_value=False)
            with patch("salt.auth.ldap._bind", mock_bind):
                result = salt.auth.ldap.groups("saltuser", password="password")
    assert "saltusers" in result
    mock_bind.assert_not_called()


# --- Group-membership re-check: FreeIPA branch (the fix) ---------------------
#
# These mirror the standard-LDAP cases above; the FreeIPA branch must behave
# identically so that 2FA works the same way it already does for plain LDAP.


def test_groups_freeipa_recheck_first_call_success():
    with patch.dict(
        salt.auth.ldap.__opts__,
        {"auth.ldap.freeipa": True, "auth.ldap.bindpw": "p@ssw0rd!"},
    ):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            mock_bind = MagicMock(return_value=Bind)
            with patch("salt.auth.ldap._bind", mock_bind):
                result = salt.auth.ldap.groups(
                    "saltuser", password="password", show_jid="20240101000000000000"
                )
    assert "saltusers" in result
    mock_bind.assert_called_once()


def test_groups_freeipa_recheck_first_call_failure():
    with patch.dict(
        salt.auth.ldap.__opts__,
        {"auth.ldap.freeipa": True, "auth.ldap.bindpw": "p@ssw0rd!"},
    ):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            with patch("salt.auth.ldap._bind", MagicMock(return_value=False)):
                result = salt.auth.ldap.groups(
                    "saltuser", password="badpassword", show_jid="20240101000000000000"
                )
    assert result == []


def test_groups_freeipa_recheck_skipped_without_show_jid():
    """
    The core fix for #61974: with FreeIPA, subsequent payloads (no show_jid)
    must not re-bind the user, so a single-use OTP is not consumed twice.
    """
    with patch.dict(
        salt.auth.ldap.__opts__,
        {"auth.ldap.freeipa": True, "auth.ldap.bindpw": "p@ssw0rd!"},
    ):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            mock_bind = MagicMock(return_value=False)
            with patch("salt.auth.ldap._bind", mock_bind):
                result = salt.auth.ldap.groups("saltuser", password="password")
    assert "saltusers" in result
    mock_bind.assert_not_called()


def test_groups_freeipa_recheck_anonymous_default_false():
    """
    Without auth_by_group_membership_only/anonymous set, the re-check binds as
    the user (anonymous is falsy) - i.e. current behavior is retained.
    """
    with patch.dict(
        salt.auth.ldap.__opts__,
        {"auth.ldap.freeipa": True, "auth.ldap.bindpw": "p@ssw0rd!"},
    ):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            mock_bind = MagicMock(return_value=Bind)
            with patch("salt.auth.ldap._bind", mock_bind):
                salt.auth.ldap.groups(
                    "saltuser", password="password", show_jid="20240101000000000000"
                )
    assert not mock_bind.call_args.kwargs["anonymous"]


def test_groups_freeipa_recheck_anonymous_when_flags_set():
    """
    With auth_by_group_membership_only and anonymous both set, the re-check
    binds anonymously.
    """
    with patch.dict(
        salt.auth.ldap.__opts__,
        {
            "auth.ldap.freeipa": True,
            "auth.ldap.bindpw": "p@ssw0rd!",
            "auth.ldap.auth_by_group_membership_only": True,
            "auth.ldap.anonymous": True,
        },
    ):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            mock_bind = MagicMock(return_value=Bind)
            with patch("salt.auth.ldap._bind", mock_bind):
                salt.auth.ldap.groups(
                    "saltuser", password="password", show_jid="20240101000000000000"
                )
    assert mock_bind.call_args.kwargs["anonymous"] is True


def test_groups_activedirectory_no_recheck():
    """
    The Active Directory branch never re-binds the user for group membership,
    regardless of show_jid; this must remain unchanged.
    """
    with patch.dict(
        salt.auth.ldap.__opts__,
        {"auth.ldap.activedirectory": True, "auth.ldap.bindpw": "p@ssw0rd!"},
    ):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            mock_bind = MagicMock(return_value=False)
            with patch("salt.auth.ldap._bind", mock_bind):
                result = salt.auth.ldap.groups(
                    "saltuser", password="password", show_jid="20240101000000000000"
                )
    assert "saltusers" in result
    mock_bind.assert_not_called()


# --- auth() ------------------------------------------------------------------


def test_auth_nopass():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            assert not salt.auth.ldap.auth("foo", None)


def test_auth_nouser():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            assert not salt.auth.ldap.auth(None, "foo")


def test_auth_nouserandpass():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            assert not salt.auth.ldap.auth(None, None)


def test_auth_success_with_search_bind():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            with patch("salt.auth.ldap._bind", return_value=Bind):
                assert salt.auth.ldap.auth("saltuser", "password")


def test_auth_fails_when_search_bind_fails():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=False):
            with patch("salt.auth.ldap._bind", return_value=Bind):
                assert not salt.auth.ldap.auth("saltuser", "password")


def test_auth_fails_when_user_bind_fails():
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.bindpw": "p@ssw0rd!"}):
        with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
            with patch("salt.auth.ldap._bind", return_value=False):
                assert not salt.auth.ldap.auth("saltuser", "password")


def test_auth_without_bind_account_uses_bind_directly():
    """
    With no separate bind account configured, auth binds as the user directly.
    """
    with patch.dict(salt.auth.ldap.__opts__, {"auth.ldap.binddn": ""}):
        with patch("salt.auth.ldap._bind", return_value=Bind) as mock_bind:
            assert salt.auth.ldap.auth("saltuser", "password")
    mock_bind.assert_called_once()
