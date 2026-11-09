from types import SimpleNamespace

import salt.daemons.masterapi as masterapi
from tests.support.mock import patch


def test_access_keys_reads_keyfile_for_each_user_matching_acl_pattern(tmp_path):
    user_pattern = r"^(alice|bob)$"
    key_contents = {
        user_pattern: "pattern-key",
        "master": "master-key",
        "alice": "alice-key",
        "bob": "bob-key",
    }
    for user, key in key_contents.items():
        (tmp_path / f".{user}_key").write_text(key)

    opts = {
        "cachedir": str(tmp_path),
        "client_acl_verify": True,
        "publisher_acl": {user_pattern: ["test.ping"]},
        "user": "master",
    }
    system_users = [
        SimpleNamespace(pw_name="alice"),
        SimpleNamespace(pw_name="bob"),
    ]

    with patch.object(masterapi, "HAS_PWD", True), patch.object(
        masterapi.pwd, "getpwall", return_value=system_users
    ), patch("salt.utils.user.get_user", return_value="master"):
        keys = masterapi.access_keys(opts)

    assert keys["alice"] == "alice-key"
    assert keys["bob"] == "bob-key"
