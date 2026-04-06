import logging

import pytest
from saltfactories.utils.tempfiles import temp_directory

import salt.client.ssh.__init__ as dunder_ssh
from salt.exceptions import SaltClientError, SaltSystemExit
from tests.support.mock import MagicMock, patch

# Minimal opts that look like a Salt minion config.
# Intentionally omits ``ext_pillar`` — it is a master-only key
# (DEFAULT_MASTER_OPTS) and is absent from DEFAULT_MINION_OPTS.
# salt-ssh's Single.__init__ must not crash when constructed from
# minion opts (as it is when invoked by the SSH resource driver).
_MINION_OPTS = {
    "relenv": True,
    "cachedir": "/tmp",
    "thin_dir": "/tmp/_salt_relenv_test",
    "ssh_wipe": False,
    "file_roots": {"base": ["/srv/salt"]},
    "pillar_roots": {"base": ["/srv/pillar"]},
    "module_dirs": [],
    # ext_pillar is deliberately absent
}

pytestmark = [pytest.mark.skip_unless_on_linux(reason="Test ssh only run on Linux")]


log = logging.getLogger(__name__)


def test_salt_refs():
    data_strg_cats = "cats"
    ret = dunder_ssh.salt_refs(data_strg_cats)
    assert ret == []

    data_strg_proto = "salt://test_salt_ref"
    ret = dunder_ssh.salt_refs(data_strg_proto)
    assert ret == [data_strg_proto]

    data_list_no_proto = ["cats"]
    ret = dunder_ssh.salt_refs(data_list_no_proto)
    assert ret == []

    data_list_proto = ["salt://test_salt_ref1", "salt://test_salt_ref2", "cats"]
    ret = dunder_ssh.salt_refs(data_list_proto)
    assert ret == ["salt://test_salt_ref1", "salt://test_salt_ref2"]


def test_convert_args():
    test_args = [
        "arg1",
        {"key1": "value1", "key2": "value2", "__kwarg__": "kwords"},
        "dog1",
    ]
    expected = ["arg1", "key1=value1", "key2=value2", "dog1"]
    ret = dunder_ssh._convert_args(test_args)
    assert ret == expected


def test_ssh_class():

    with temp_directory() as temp_dir:
        assert temp_dir.is_dir()
        opts = {
            "sock_dir": temp_dir,
            "regen_thin": False,
            "__master_opts__": {"pki_dir": "pki"},
            "selected_target_option": None,
            "tgt": "*",
            "tgt_type": "glob",
            "fileserver_backend": ["roots"],
            "cachedir": "/tmp",
            "thin_extra_mods": "",
            "ssh_ext_alternatives": None,
        }

        with patch("salt.utils.path.which", return_value=""), pytest.raises(
            SaltSystemExit
        ) as err:
            test_ssh = dunder_ssh.SSH(opts)
            assert (
                "salt-ssh could not be run because it could not generate keys."
                in str(err.value)
            )

        with patch("salt.utils.path.which", return_value="/usr/bin/ssh"), patch(
            "os.path.isfile", return_value=False
        ), patch(
            "salt.client.ssh.shell.gen_key", MagicMock(side_effect=OSError())
        ), pytest.raises(
            SaltClientError
        ) as err:
            test_ssh = dunder_ssh.SSH(opts)
            assert (
                "salt-ssh could not be run because it could not generate keys."
                in err.value
            )


def test_single_init_with_minion_opts_no_ext_pillar():
    """
    Single.__init__ must succeed when given minion opts that lack ``ext_pillar``.

    salt-ssh normally runs on the master, where opts always contain
    ``ext_pillar: []`` (it is in DEFAULT_MASTER_OPTS).  The SSH resource
    driver builds Single from inside a minion process using ``dict(__opts__)``,
    which produces minion opts.  ``ext_pillar`` is absent from
    DEFAULT_MINION_OPTS, so a direct ``opts["ext_pillar"]`` access raises
    KeyError.  The fix uses ``opts.get("ext_pillar", [])``; this test pins
    that behaviour so the regression is immediately obvious if the .get() is
    ever reverted.
    """
    with patch("salt.loader.ssh_wrapper", return_value=MagicMock()), patch(
        "salt.client.ssh.shell.gen_shell", return_value=MagicMock()
    ):
        single = dunder_ssh.Single(
            _MINION_OPTS.copy(),
            "test.ping",
            "target-host",
            host="192.0.2.1",
            thin="/fake/salt-relenv.tar.xz",
            thin_dir="/tmp/_salt_relenv_test",
        )

    assert (
        single.minion_opts["ext_pillar"] == []
    ), "ext_pillar should default to [] when absent from minion opts"
