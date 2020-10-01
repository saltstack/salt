import ast
import os
import re
import textwrap

import pytest
import salt.utils.files
import salt.utils.platform
import salt.utils.pycrypto
import salt.utils.yaml
from saltfactories.utils import random_string
from tests.support.helpers import slowTest

pytestmark = pytest.mark.windows_whitelisted

USERA = "saltdev-key"
USERA_PWD = "saltdev"
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


@pytest.fixture(scope="module")
def saltdev_account(sminion):
    try:
        assert sminion.functions.user.add(USERA, createhome=False)
        assert sminion.functions.shadow.set_password(
            USERA,
            USERA_PWD
            if salt.utils.platform.is_darwin()
            else salt.utils.pycrypto.gen_hash(password=USERA_PWD),
        )
        assert USERA in sminion.functions.user.list_users()
        # Run tests
        yield
    finally:
        sminion.functions.user.delete(USERA, remove=True)


@slowTest
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
        assert ret.exitcode == 0
        assert "minions" in ret.json
        assert min_name in ret.json["minions"]
        assert "-----BEGIN PUBLIC KEY-----" in ret.json["minions"][min_name]
        # Remove Key
        ret = salt_key_cli.run("-d", min_name, "-y")
        assert ret.exitcode == 0
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
        assert ret.exitcode == 0
        assert ret.json == {}
    finally:
        if os.path.exists(key):
            os.unlink(key)


@slowTest
@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_remove_key_eauth(salt_key_cli, salt_master, saltdev_account):
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
        assert ret.exitcode == 0
        assert "minions" in ret.json
        assert min_name in ret.json["minions"]
        assert "-----BEGIN PUBLIC KEY-----" in ret.json["minions"][min_name]
        # Remove Key
        ret = salt_key_cli.run(
            "-d",
            min_name,
            "-y",
            "--eauth",
            "pam",
            "--username",
            USERA,
            "--password",
            USERA_PWD,
        )
        assert ret.exitcode == 0
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
        assert ret.exitcode == 0
        assert ret.json == {}
    finally:
        if os.path.exists(key):
            os.unlink(key)


@slowTest
@pytest.mark.parametrize("key_type", ("acc", "pre", "den", "un", "rej"))
def test_list_accepted_args(salt_key_cli, key_type):
    """
    test salt-key -l for accepted arguments
    """
    # Should not trigger any error
    ret = salt_key_cli.run("-l", key_type)
    assert ret.exitcode == 0
    assert "error:" not in ret.stdout
    # Should throw an error now
    ret = salt_key_cli.run("-l", "foo-{}".format(key_type))
    assert ret.exitcode != 0
    assert "error:" in ret.stderr


@slowTest
def test_list_all(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -L
    """
    ret = salt_key_cli.run("-L")
    assert ret.exitcode == 0
    expected = {
        "minions_rejected": [],
        "minions_denied": [],
        "minions_pre": [],
        "minions": [salt_minion.id, salt_sub_minion.id],
    }
    assert ret.json == expected


@slowTest
def test_list_all_yaml_out(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -L --out=yaml
    """
    ret = salt_key_cli.run("-L", "--out=yaml")
    assert ret.exitcode == 0
    output = salt.utils.yaml.safe_load(ret.stdout)
    expected = {
        "minions_rejected": [],
        "minions_denied": [],
        "minions_pre": [],
        "minions": [salt_minion.id, salt_sub_minion.id],
    }
    assert output == expected


@slowTest
def test_list_all_raw_out(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -L --out=raw
    """
    ret = salt_key_cli.run("-L", "--out=raw")
    assert ret.exitcode == 0
    output = ast.literal_eval(ret.stdout)
    expected = {
        "minions_rejected": [],
        "minions_denied": [],
        "minions_pre": [],
        "minions": [salt_minion.id, salt_sub_minion.id],
    }
    assert output == expected


@slowTest
def test_list_acc(salt_key_cli, salt_minion, salt_sub_minion):
    """
    test salt-key -l acc
    """
    ret = salt_key_cli.run("-l", "acc")
    assert ret.exitcode == 0
    expected = {"minions": [salt_minion.id, salt_sub_minion.id]}
    assert ret.json == expected


@slowTest
@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_list_acc_eauth(salt_key_cli, saltdev_account, salt_minion, salt_sub_minion):
    """
    test salt-key -l with eauth
    """
    ret = salt_key_cli.run(
        "-l", "acc", "--eauth", "pam", "--username", USERA, "--password", USERA_PWD
    )
    assert ret.exitcode == 0
    expected = {"minions": [salt_minion.id, salt_sub_minion.id]}
    assert ret.json == expected


@slowTest
@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_list_acc_eauth_bad_creds(salt_key_cli, saltdev_account):
    """
    test salt-key -l with eauth and bad creds
    """
    ret = salt_key_cli.run(
        "-l",
        "acc",
        "--eauth",
        "pam",
        "--username",
        USERA,
        "--password",
        "wrongpassword",
    )
    assert (
        ret.stdout
        == 'Authentication failure of type "eauth" occurred for user {}.'.format(USERA)
    )


@slowTest
def test_list_acc_wrong_eauth(salt_key_cli):
    """
    test salt-key -l with wrong eauth
    """
    ret = salt_key_cli.run(
        "-l",
        "acc",
        "--eauth",
        "wrongeauth",
        "--username",
        USERA,
        "--password",
        USERA_PWD,
    )
    assert ret.exitcode == 0, ret
    assert re.search(
        r"^The specified external authentication system \"wrongeauth\" is not available\nAvailable eauth types: auto, .*",
        ret.stdout.replace("\r\n", "\n"),
    )


@slowTest
def test_list_un(salt_key_cli):
    """
    test salt-key -l un
    """
    ret = salt_key_cli.run("-l", "un")
    assert ret.exitcode == 0
    expected = {"minions_pre": []}
    assert ret.json == expected


@slowTest
def test_keys_generation(salt_key_cli):
    with pytest.helpers.temp_directory() as tempdir:
        ret = salt_key_cli.run("--gen-keys", "minibar", "--gen-keys-dir", tempdir)
        assert ret.exitcode == 0
        try:
            key_names = ("minibar.pub", "minibar.pem")
            for fname in key_names:
                assert os.path.isfile(os.path.join(tempdir, fname))
        finally:
            for filename in os.listdir(tempdir):
                os.chmod(os.path.join(tempdir, filename), 0o700)


@slowTest
def test_keys_generation_keysize_min(salt_key_cli):
    with pytest.helpers.temp_directory() as tempdir:
        ret = salt_key_cli.run(
            "--gen-keys", "minibar", "--gen-keys-dir", tempdir, "--keysize", "1024"
        )
        assert ret.exitcode != 0
        assert "error: The minimum value for keysize is 2048" in ret.stderr


@slowTest
def test_keys_generation_keysize_max(salt_key_cli):
    with pytest.helpers.temp_directory() as tempdir:
        ret = salt_key_cli.run(
            "--gen-keys", "minibar", "--gen-keys-dir", tempdir, "--keysize", "32769"
        )
        assert ret.exitcode != 0
        assert "error: The maximum value for keysize is 32768" in ret.stderr
