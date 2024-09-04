import time

import salt.auth
import salt.config
from tests.support.mock import patch


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


def test_static_external_auth_with_eauth_in_token_but_not_in_load():
    """
    During token-based authorization, we may see the `load` dictionary without
    an "eauth" key. If the "eauth" key is present in the `token` dictionary, we
    can still look up an ACL, via the static "external_auth" option, if it is
    defined.
    """
    _auth_list = [".*", "@wheel", "@runner"]
    # The static "external_auth" option is defined.
    opts = {"external_auth": {"auto": {"foo": _auth_list}}, "keep_acl_in_token": False}
    auth = salt.auth.LoadAuth(opts)
    # No "eauth" key is defined in the load...
    load = {
        "username": "foo",
        "password": "foo",
    }
    # ...but an "eauth" key is defined in the token.
    token = {
        "start": 1718656266.9965827,
        "expire": 1718699466.996583,
        "name": "foo",
        "eauth": "auto",
        "token": "bbbc12ab06aa9e9acf9747127858ee6756377c2edcf8c8176c8fcbc2307e40aa",
    }

    # Mock __get_acl() as if the `auto` module has not "acl" member.
    # This will force get_auth_list() to check the static "external_auth"
    # option.
    with patch.object(auth, "_LoadAuth__get_acl") as mocked_get_acl:
        mocked_get_acl.return_value = None
        auth_list = auth.get_auth_list(load, token)
        assert auth_list == _auth_list


def test_eauth_acl_module_with_eauth_in_token_but_not_in_load():
    """
    In the case a server is configured to look up ACLs via an external source
    (e.g. "eauth_acl_module" is defined), "eauth" is defined in the `token`
    dictionary and not in the `load` dictionary, token["eauth"] will be used as
    the value of load["eauth"], thereby engaging the external ACL lookup code in
    __get_acl().
    """
    _auth_list = ["@jobs", "@runner"]
    # The static "external_auth" option is undefined because the server contains
    # a module to perform ACL lookups from an external source.
    opts = {"external_auth": {}, "keep_acl_in_token": False}
    auth = salt.auth.LoadAuth(opts)
    # No "eauth" key is defined in the load...
    load = {
        "username": "foo",
        "password": "foo",
    }
    # ...but an "eauth" key is defined in the token.
    token = {
        "start": 1718656266.9965827,
        "expire": 1718699466.996583,
        "name": "foo",
        "eauth": "auto",
        "token": "bbbc12ab06aa9e9acf9747127858ee6756377c2edcf8c8176c8fcbc2307e40aa",
    }

    # Mock __get_acl() as if it has successfully looked up an ACL from an
    # external source.
    with patch.object(auth, "_LoadAuth__get_acl") as mocked_get_acl:
        mocked_get_acl.return_value = _auth_list
        auth_list = auth.get_auth_list(load, token)
        assert auth_list == _auth_list
