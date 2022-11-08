import time

import salt.auth
import salt.config


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
