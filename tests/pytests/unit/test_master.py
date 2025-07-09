import pathlib
import time

import pytest

import salt.config
import salt.crypt
import salt.master
import salt.utils.files
import salt.utils.platform
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS

try:
    import pygit2  # pylint: disable=unused-import

    HAS_PYGIT2 = True
except ImportError:
    HAS_PYGIT2 = False


skipif_no_pygit2 = pytest.mark.skipif(not HAS_PYGIT2, reason="Missing pygit2")


@pytest.fixture
def encrypted_requests(tmp_path):
    # To honor the comment on AESFuncs
    (tmp_path / "pki").mkdir()
    return salt.master.AESFuncs(
        opts={
            "pki_dir": str(tmp_path / "pki"),
            "cachedir": str(tmp_path / "cache"),
            "sock_dir": str(tmp_path / "sock_drawer"),
            "conf_file": str(tmp_path / "config.conf"),
            "fileserver_backend": ["local"],
            "master_job_cache": False,
        }
    )


def test_maintenance_duration():
    """
    Validate Maintenance process duration.
    """
    opts = {
        "loop_interval": 10,
        "maintenance_interval": 1,
        "cachedir": "/tmp",
        "sock_dir": "/tmp",
        "maintenance_niceness": 1,
        "key_cache": "sched",
        "conf_file": "",
        "master_job_cache": "",
        "pki_dir": "/tmp",
        "eauth_tokens": "",
    }
    mp = salt.master.Maintenance(opts)
    with patch("salt.utils.verify.check_max_open_files") as check_files, patch.object(
        mp, "handle_key_cache"
    ) as handle_key_cache, patch("salt.daemons") as salt_daemons, patch.object(
        mp, "handle_git_pillar"
    ) as handle_git_pillar:
        mp.run()
    assert salt_daemons.masterapi.clean_old_jobs.called
    assert salt_daemons.masterapi.clean_expired_tokens.called
    assert salt_daemons.masterapi.clean_pub_auth.called
    assert handle_git_pillar.called


def test_fileserver_duration():
    """
    Validate Fileserver process duration.
    """
    with patch("salt.master.FileserverUpdate._do_update") as update:
        start = time.time()
        salt.master.FileserverUpdate.update(1, {}, 1)
        end = time.time()
        # Interval is equal to timeout so the _do_update method will be called
        # one time.
        update.assert_called_once()
        # Timeout is 1 second
        duration = end - start
        if duration > 2 and salt.utils.platform.spawning_platform():
            # Give spawning platforms some slack
            duration = round(duration, 1)
        assert 2 > duration > 1


@pytest.mark.parametrize(
    "expected_return, payload",
    (
        (
            {
                "jid": "20221107162714826470",
                "id": "example-minion",
                "return": {
                    "pkg_|-linux-install-utils_|-curl_|-installed": {
                        "name": "curl",
                        "changes": {},
                        "result": True,
                        "comment": "All specified packages are already installed",
                        "__sls__": "base-linux.base",
                        "__run_num__": 0,
                        "start_time": "08:27:17.594038",
                        "duration": 32.963,
                        "__id__": "linux-install-utils",
                    },
                },
                "retcode": 0,
                "success": True,
                "fun_args": ["base-linux", {"pillar": {"test": "value"}}],
                "fun": "state.sls",
                "out": "highstate",
            },
            {
                "cmd": "_syndic_return",
                "load": [
                    {
                        "id": "aws.us-east-1.salt-syndic",
                        "jid": "20221107162714826470",
                        "fun": "state.sls",
                        "arg": None,
                        "tgt": None,
                        "tgt_type": None,
                        "load": {
                            "arg": [
                                "base-linux",
                                {"pillar": {"test": "value"}, "__kwarg__": True},
                            ],
                            "cmd": "publish",
                            "fun": "state.sls",
                            "jid": "20221107162714826470",
                            "ret": "",
                            "tgt": "example-minion",
                            "user": "sudo_ubuntu",
                            "kwargs": {
                                "show_jid": False,
                                "delimiter": ":",
                                "show_timeout": True,
                            },
                            "tgt_type": "glob",
                        },
                        "return": {
                            "example-minion": {
                                "return": {
                                    "pkg_|-linux-install-utils_|-curl_|-installed": {
                                        "name": "curl",
                                        "changes": {},
                                        "result": True,
                                        "comment": "All specified packages are already installed",
                                        "__sls__": "base-linux.base",
                                        "__run_num__": 0,
                                        "start_time": "08:27:17.594038",
                                        "duration": 32.963,
                                        "__id__": "linux-install-utils",
                                    },
                                },
                                "retcode": 0,
                                "success": True,
                                "fun_args": [
                                    "base-linux",
                                    {"pillar": {"test": "value"}},
                                ],
                            }
                        },
                        "out": "highstate",
                    }
                ],
                "_stamp": "2022-11-07T16:27:17.965404",
            },
        ),
    ),
)
def test_when_syndic_return_processes_load_then_correct_values_should_be_returned(
    expected_return, payload, encrypted_requests
):
    with patch.object(encrypted_requests, "_return", autospec=True) as fake_return:
        encrypted_requests._syndic_return(payload)
        fake_return.assert_called_with(expected_return)


def test_syndic_return_cache_dir_creation(encrypted_requests):
    """master's cachedir for a syndic will be created by AESFuncs._syndic_return method"""
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    encrypted_requests._syndic_return(
        {
            "id": "mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert (cachedir / "syndics").exists()
    assert (cachedir / "syndics" / "mamajama").exists()


def test_syndic_return_cache_dir_creation_traversal(encrypted_requests):
    """
    master's  AESFuncs._syndic_return method cachdir creation is not vulnerable to a directory traversal
    """
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    encrypted_requests._syndic_return(
        {
            "id": "../mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert not (cachedir / "syndics").exists()
    assert not (cachedir / "mamajama").exists()


def test_pub_ret_traversal(encrypted_requests, tmp_path):
    """
    master's  AESFuncs._syndic_return method cachdir creation is not vulnerable to a directory traversal
    """
    salt.crypt.gen_keys(tmp_path, "minion", 2048)

    minions = pathlib.Path(encrypted_requests.opts["pki_dir"]) / "minions"
    minions.mkdir()

    with salt.utils.files.fopen(minions / "minion", "wb") as wfp:
        with salt.utils.files.fopen(tmp_path / "minion.pub", "rb") as rfp:
            wfp.write(rfp.read())

    priv = salt.crypt.PrivateKey(tmp_path / "minion.pem")
    with pytest.raises(salt.exceptions.SaltValidationError):
        encrypted_requests.pub_ret(
            {
                "tok": priv.encrypt(b"salt"),
                "id": "minion",
                "jid": "asdf/../../../sdf",
                "return": {},
            }
        )


def _git_pillar_base_config(tmp_path):
    return {
        "__role": "master",
        "pki_dir": str(tmp_path / "pki"),
        "cachedir": str(tmp_path / "cache"),
        "sock_dir": str(tmp_path / "sock_drawer"),
        "conf_file": str(tmp_path / "config.conf"),
        "fileserver_backend": ["local"],
        "master_job_cache": False,
        "file_client": "local",
        "pillar_cache": False,
        "state_top": "top.sls",
        "pillar_roots": {
            "base": [str(tmp_path / "pillar")],
        },
        "render_dirs": [str(pathlib.Path(RUNTIME_VARS.SALT_CODE_DIR) / "renderer")],
        "renderer": "jinja|yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "optimization_order": [0, 1, 2],
        "on_demand_ext_pillar": [],
        "git_pillar_user": "",
        "git_pillar_password": "",
        "git_pillar_pubkey": "",
        "git_pillar_privkey": "",
        "git_pillar_passphrase": "",
        "git_pillar_insecure_auth": False,
        "git_pillar_refspecs": salt.config._DFLT_REFSPECS,
        "git_pillar_ssl_verify": True,
        "git_pillar_branch": "master",
        "git_pillar_base": "master",
        "git_pillar_root": "",
        "git_pillar_env": "",
        "git_pillar_fallback": "",
    }


@pytest.fixture
def allowed_funcs(tmp_path):
    """
    Configuration with git on demand pillar allowed
    """
    opts = _git_pillar_base_config(tmp_path)
    opts["on_demand_ext_pillar"] = ["git"]
    salt.crypt.gen_keys(str(tmp_path), "minion", 2048)
    master_pki = tmp_path / "pki"
    master_pki.mkdir()
    accepted_pki = master_pki / "minions"
    accepted_pki.mkdir()
    (accepted_pki / "minion.pub").write_text((tmp_path / "minion.pub").read_text())

    return salt.master.AESFuncs(opts=opts)


@skipif_no_pygit2
def test_on_demand_allowed_command_injection(allowed_funcs, tmp_path, caplog):
    """
    Verify on demand pillars validate remote urls
    """
    pwnpath = tmp_path / "pwn"
    assert not pwnpath.exists()
    load = {
        "cmd": "_pillar",
        "saltenv": "base",
        "pillarenv": "base",
        "id": "carbon",
        "grains": {},
        "ver": 2,
        "ext": {
            "git": [
                f'base ssh://fake@git/repo\n[core]\nsshCommand = touch {pwnpath}\n[remote "origin"]\n'
            ]
        },
        "clean_cache": True,
    }
    with caplog.at_level(level="WARNING"):
        ret = allowed_funcs._pillar(load)
    assert not pwnpath.exists()
    assert "Found bad url data" in caplog.text


@pytest.fixture
def not_allowed_funcs(tmp_path):
    """
    Configuration with no on demand pillars allowed
    """
    opts = _git_pillar_base_config(tmp_path)
    opts["on_demand_ext_pillar"] = []
    salt.crypt.gen_keys(str(tmp_path), "minion", 2048)
    master_pki = tmp_path / "pki"
    master_pki.mkdir()
    accepted_pki = master_pki / "minions"
    accepted_pki.mkdir()
    (accepted_pki / "minion.pub").write_text((tmp_path / "minion.pub").read_text())

    return salt.master.AESFuncs(opts=opts)


def test_on_demand_not_allowed(not_allowed_funcs, tmp_path, caplog):
    """
    Verify on demand pillars do not render when not allowed
    """
    pwnpath = tmp_path / "pwn"
    assert not pwnpath.exists()
    load = {
        "cmd": "_pillar",
        "saltenv": "base",
        "pillarenv": "base",
        "id": "carbon",
        "grains": {},
        "ver": 2,
        "ext": {
            "git": [
                f'base ssh://fake@git/repo\n[core]\nsshCommand = touch {pwnpath}\n[remote "origin"]\n'
            ]
        },
        "clean_cache": True,
    }
    with caplog.at_level(level="WARNING"):
        ret = not_allowed_funcs._pillar(load)
    assert not pwnpath.exists()
    assert (
        "The following ext_pillar modules are not allowed for on-demand pillar data: git."
        in caplog.text
    )
