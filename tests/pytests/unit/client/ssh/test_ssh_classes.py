import logging

import pytest
from saltfactories.utils.tempfiles import temp_directory

import salt.client.ssh.__init__ as dunder_ssh
from salt.exceptions import SaltClientError, SaltSystemExit
from tests.support.mock import MagicMock, patch

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
