import time

import pytest

import salt.master
import salt.utils.platform
from tests.support.mock import patch


@pytest.fixture
def encrypted_requests(tmp_path):
    # To honor the comment on AESFuncs
    return salt.master.AESFuncs(
        opts={
            "cachedir": str(tmp_path / "cache"),
            "sock_dir": str(tmp_path / "sock_drawer"),
            "conf_file": str(tmp_path / "config.conf"),
            "fileserver_backend": "local",
            "master_job_cache": False,
        }
    )


def test_fileserver_duration():
    with patch("salt.master.FileserverUpdate._do_update") as update:
        start = time.time()
        salt.master.FileserverUpdate.update(1, {}, 1)
        end = time.time()
        # Interval is equal to timeout so the _do_update method will be called
        # one time.
        update.called_once()
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
