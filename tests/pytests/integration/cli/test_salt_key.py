import ast
import copy
import os
import re
import shutil
import textwrap

import pytest
from saltfactories.utils import random_string

import salt.utils.files
import salt.utils.platform
import salt.utils.pycrypto
import salt.utils.yaml

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]

PUB_KEY = textwrap.dedent(
    """\
        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoqIZDtcQtqUNs0wC7qQz
        JwFhXAVNT5C8M8zhI+pFtF/63KoN5k1WwAqP2j3LquTG68WpxcBwLtKfd7FVA/Kr
        OF3kXDWFnDi+HDchW2lJObgfzLckWNRFaF8SBvFM2dys3CGSgCV0S/qxnRAjrJQb
        B3uQwtZ64ncJAlkYpArv3GwsfRJ5UUQnYPDEJwGzMskZ0pHd60WwM1gMlfYmNX5O
        RBEjybyNpYDzpda6e6Ypsn6ePGLkP/tuwUf+q9wpbRE3ZwqERC2XRPux+HX2rGP+
        mkzpmuHkyi2wV33A9pDfMgRHdln2CLX0KgfRGixUQhW1o+Kmfv2rq4sGwpCgLbTh
        NwIDAQAB
        -----END PUBLIC KEY-----
        """
)


def test_remove_key(salt_master, salt_key_cli):
    """
    test salt-key -d usage
    """
    min_name = random_string("minibar-")
    pki_dir = salt_master.config["pki_dir"]
    key = os.path.join(pki_dir, "minions", min_name)

    with salt.utils.files.fopen(key, "w") as fp:
        fp.write(PUB_KEY)

    try:
        # Check Key
        ret = salt_key_cli.run("-p", min_name)
        assert ret.returncode == 0
        assert "minions" in ret.data
        assert min_name in ret.data["minions"]
        assert "-----BEGIN PUBLIC KEY-----" in ret.data["minions"][min_name]
        # Remove Key
        ret = salt_key_cli.run("-d", min_name, "-y")
        assert ret.returncode == 0
        # We can't load JSON because we print to stdout!
        # >>>>> STDOUT >>>>>
        # The following keys are going to be deleted:
        # {
        #     "minions": [
        #         "minibar"
        #     ]
        # }
        # Key for minion minibar deleted.
        # <<<<< STDOUT <<<<<
        assert "minions" in ret.stdout
        assert min_name in ret.stdout
        # Check Key
        ret = salt_key_cli.run("-p", min_name)
        assert ret.returncode == 0
        assert ret.data == {}
    finally:
        if os.path.exists(key):
            os.unlink(key)


@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_remove_key_eauth(salt_key_cli, salt_master, salt_eauth_account):
    """
    test salt-key -d usage
    """
    min_name = random_string("minibar-")
    pki_dir = salt_master.config["pki_dir"]
    key = os.path.join(pki_dir, "minions", min_name)

    with salt.utils.files.fopen(key, "w") as fp:
        fp.write(PUB_KEY)

    try:
        # Check Key
        ret = salt_key_cli.run("-p", min_name)
        assert ret.returncode == 0
        assert "minions" in ret.data
        assert min_name in ret.data["minions"]
        assert "-----BEGIN PUBLIC KEY-----" in ret.data["minions"][min_name]
        # Remove Key
        ret = salt_key_cli.run(
            "-d",
            min_name,
            "-y",
            "--eauth",
            "pam",
            "--username",
            salt_eauth_account.username,
            "--password",
            salt_eauth_account.password,
        )
        assert ret.returncode == 0
        # We can't load JSON because we print to stdout!
        # >>>>> STDOUT >>>>>
        # The following keys are going to be deleted:
        # {
        #     "minions": [
        #         "minibar"
        #     ]
        # }
        # Key for minion minibar deleted.
        # <<<<< STDOUT <<<<<
        assert "minions" in ret.stdout
        assert min_name in ret.stdout
        # Check Key
        ret = salt_key_cli.run("-p", min_name)
        assert ret.returncode == 0
        assert ret.data == {}
    finally:
        if os.path.exists(key):
            os.unlink(key)


@pytest.mark.parametrize("key_type", ("acc", "pre", "den", "un", "rej"))
def test_list_accepted_args(salt_key_cli, key_type):
    """
    test salt-key -l for accepted arguments
    """
    # Should not trigger any error
    ret = salt_key_cli.run("-l", key_type)
    assert ret.returncode == 0
    assert "error:" not in ret.stdout
    # Should throw an error now
    ret = salt_key_cli.run("-l", f"foo-{key_type}")
    assert ret.returncode != 0
    assert "error:" in ret.stderr


def test_list_all(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -L
    """
    ret = salt_key_cli.run("-L")
    assert ret.returncode == 0
    expected = {
        "minions_rejected": [],
        "minions_denied": [],
        "minions_pre": [],
        "minions": [salt_minion.id, salt_sub_minion.id],
    }
    assert ret.data == expected


def test_list_all_no_check_files(
    salt_key_cli, salt_minion, salt_sub_minion, tmp_path, salt_master
):
    """
    test salt-key -L
    """
    config_dir = tmp_path / "key_no_check_files"
    config_dir.mkdir()
    pki_dir = config_dir / "pki_dir"
    shutil.copytree(salt_master.config["pki_dir"], str(pki_dir))
    with pytest.helpers.change_cwd(str(config_dir)):
        master_config = copy.deepcopy(salt_master.config)
        master_config["pki_check_files"] = False
        master_config["pki_dir"] = "pki_dir"
        master_config["root_dir"] = str(config_dir)
        with salt.utils.files.fopen(str(config_dir / "master"), "w") as fh_:
            fh_.write(salt.utils.yaml.dump(master_config, default_flow_style=False))
        ret = salt_key_cli.run(
            f"--config-dir={config_dir}",
            "-L",
        )
        assert ret.returncode == 0
        expected = {
            "minions_rejected": [],
            "minions_denied": [],
            "minions_pre": [],
            "minions": [salt_minion.id, salt_sub_minion.id],
        }
        assert ret.data == expected

        bad_key = pki_dir / "minions" / "dir1"
        bad_key.mkdir()

        ret = salt_key_cli.run(
            f"--config-dir={config_dir}",
            "-L",
        )
        assert ret.returncode == 0
        # The directory will show up since there is no file check
        expected["minions"].insert(0, "dir1")
        assert ret.data == expected


def test_list_all_yaml_out(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -L --out=yaml
    """
    ret = salt_key_cli.run("-L", "--out=yaml")
    assert ret.returncode == 0
    output = salt.utils.yaml.safe_load(str(ret.stdout))
    expected = {
        "minions_rejected": [],
        "minions_denied": [],
        "minions_pre": [],
        "minions": [salt_minion.id, salt_sub_minion.id],
    }
    assert output == expected


def test_list_all_raw_out(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -L --out=raw
    """
    ret = salt_key_cli.run("-L", "--out=raw")
    assert ret.returncode == 0
    output = ast.literal_eval(ret.stdout)
    expected = {
        "minions_rejected": [],
        "minions_denied": [],
        "minions_pre": [],
        "minions": [salt_minion.id, salt_sub_minion.id],
    }
    assert output == expected


def test_list_acc(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -l acc
    """
    ret = salt_key_cli.run("-l", "acc")
    assert ret.returncode == 0
    expected = {"minions": [salt_minion.id, salt_sub_minion.id]}
    assert ret.data == expected


@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_list_acc_eauth(salt_key_cli, salt_minion, salt_sub_minion, salt_eauth_account):
    """
    test salt-key -l with eauth
    """
    ret = salt_key_cli.run(
        "-l",
        "acc",
        "--eauth",
        "pam",
        "--username",
        salt_eauth_account.username,
        "--password",
        salt_eauth_account.password,
    )
    assert ret.returncode == 0
    expected = {"minions": [salt_minion.id, salt_sub_minion.id]}
    assert ret.data == expected


@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_list_acc_eauth_bad_creds(salt_key_cli, salt_eauth_account):
    """
    test salt-key -l with eauth and bad creds
    """
    ret = salt_key_cli.run(
        "-l",
        "acc",
        "--eauth",
        "pam",
        "--username",
        salt_eauth_account.username,
        "--password",
        "wrongpassword",
    )
    assert (
        ret.stdout
        == 'Authentication failure of type "eauth" occurred for user {}.'.format(
            salt_eauth_account.username
        )
    )


def test_list_acc_wrong_eauth(salt_key_cli, salt_eauth_account):
    """
    test salt-key -l with wrong eauth
    """
    ret = salt_key_cli.run(
        "-l",
        "acc",
        "--eauth",
        "wrongeauth",
        "--username",
        salt_eauth_account.username,
        "--password",
        salt_eauth_account.password,
    )
    assert ret.returncode == 0, ret
    assert re.search(
        r"^The specified external authentication system \"wrongeauth\" is not"
        r" available\nAvailable eauth types: auto, .*",
        ret.stdout.replace("\r\n", "\n"),
    )


def test_list_un(salt_key_cli):
    """
    test salt-key -l un
    """
    ret = salt_key_cli.run("-l", "un")
    assert ret.returncode == 0
    expected = {"minions_pre": []}
    assert ret.data == expected


def test_keys_generation(salt_key_cli, tmp_path):
    ret = salt_key_cli.run("--gen-keys", "minibar", "--gen-keys-dir", str(tmp_path))
    assert ret.returncode == 0
    try:
        key_names = ("minibar.pub", "minibar.pem")
        for fname in key_names:
            fpath = tmp_path / fname
            assert fpath.is_file()
    finally:
        for filename in tmp_path.iterdir():
            filename.chmod(0o700)


def test_gen_keys_dir_without_gen_keys(salt_key_cli, tmp_path):
    gen_keys_path = tmp_path / "temp-gen-keys-path"
    ret = salt_key_cli.run("--gen-keys-dir", str(gen_keys_path))
    assert ret.returncode == 0
    assert not gen_keys_path.exists()


def test_keys_generation_keysize_min(salt_key_cli, tmp_path):
    ret = salt_key_cli.run(
        "--gen-keys", "minibar", "--gen-keys-dir", str(tmp_path), "--keysize", "1024"
    )
    assert ret.returncode != 0
    assert "error: The minimum value for keysize is 2048" in ret.stderr


def test_keys_generation_keysize_max(salt_key_cli, tmp_path):
    ret = salt_key_cli.run(
        "--gen-keys", "minibar", "--gen-keys-dir", str(tmp_path), "--keysize", "32769"
    )
    assert ret.returncode != 0
    assert "error: The maximum value for keysize is 32768" in ret.stderr


def test_accept_bad_key(salt_master, salt_key_cli):
    """
    test salt-key -d usage
    """
    min_name = random_string("minibar-")
    pki_dir = salt_master.config["pki_dir"]
    key = os.path.join(pki_dir, "minions_pre", min_name)

    with salt.utils.files.fopen(key, "w") as fp:
        fp.write("")

    try:
        # Check Key
        ret = salt_key_cli.run("-y", "-a", min_name)
        assert ret.returncode == 0
        assert f"invalid key for {min_name}" in ret.stderr
    finally:
        if os.path.exists(key):
            os.remove(key)
