import os

import pytest
import salt.returners.prometheus_textfile as prometheus_textfile
import salt.utils.files
from tests.support.mock import patch


@pytest.fixture
def root_dir(tmp_path):
    return str(tmp_path / "root_dir")


@pytest.fixture
def cache_dir(root_dir):
    return os.path.join(root_dir, "cachedir")


def test_basic_prometheus_output_with_default_options(cache_dir, temp_salt_minion):
    ret = {
        "jid": "20211109174620871797",
        "return": {
            "cmd_|-echo includeme_|-echo includeme_|-run": {
                "name": "echo includeme",
                "changes": {
                    "pid": 10549,
                    "retcode": 0,
                    "stdout": "includeme",
                    "stderr": "",
                },
                "result": True,
                "comment": 'Command "echo includeme" run',
                "__sls__": "includeme",
                "__run_num__": 0,
                "start_time": "17:46:21.013878",
                "duration": 7.688,
                "__id__": "echo includeme",
            },
            "cmd_|-echo applyme_|-echo applyme_|-run": {
                "name": "echo applyme",
                "changes": {
                    "pid": 10550,
                    "retcode": 0,
                    "stdout": "applyme",
                    "stderr": "",
                },
                "result": True,
                "comment": 'Command "echo applyme" run',
                "__sls__": "applyme",
                "__run_num__": 1,
                "start_time": "17:46:21.021948",
                "duration": 6.007,
                "__id__": "echo applyme",
            },
        },
        "retcode": 0,
        "out": "highstate",
        "id": "d10-master-01.example.local",
        "fun": "state.apply",
        "fun_args": ["applyme"],
        "success": True,
    }

    expected = "\n".join(
        [
            "# HELP salt_procs Number of salt minion processes running",
            "# TYPE salt_procs gauge",
            "salt_procs 0",
            "# HELP salt_states_succeeded Number of successful states in the run",
            "# TYPE salt_states_succeeded gauge",
            "salt_states_succeeded 2",
            "# HELP salt_states_failed Number of failed states in the run",
            "# TYPE salt_states_failed gauge",
            "salt_states_failed 0",
            "# HELP salt_states_changed Number of changed states in the run",
            "# TYPE salt_states_changed gauge",
            "salt_states_changed 2",
            "# HELP salt_states_total Total states in the run",
            "# TYPE salt_states_total gauge",
            "salt_states_total 2",
            "# HELP salt_states_success_pct Percent of successful states in the run",
            "# TYPE salt_states_success_pct gauge",
            "salt_states_success_pct 100.0",
            "# HELP salt_states_failure_pct Percent of failed states in the run",
            "# TYPE salt_states_failure_pct gauge",
            "salt_states_failure_pct 0.0",
            "# HELP salt_states_changed_pct Percent of changed states in the run",
            "# TYPE salt_states_changed_pct gauge",
            "salt_states_changed_pct 100.0",
            "# HELP salt_elapsed_time Time spent for all operations during the state run",
            "# TYPE salt_elapsed_time gauge",
            "salt_elapsed_time 13.695",
            "# HELP salt_last_started Estimated time the state run started",
            "# TYPE salt_last_started gauge",
            "# HELP salt_last_completed Time of last state run completion",
            "# TYPE salt_last_completed gauge",
            "",
        ]
    )

    opts = temp_salt_minion.config.copy()
    opts["cachedir"] = cache_dir
    with patch("salt.returners.prometheus_textfile.__opts__", opts, create=True), patch(
        "salt.returners.prometheus_textfile.__salt__", {}, create=True
    ):
        prometheus_textfile.returner(ret)

        with salt.utils.files.fopen(
            os.path.join(cache_dir, "prometheus_textfile", "salt.prom")
        ) as prom_file:
            salt_prom = prom_file.read()

        # Drop time-based fields for comparison
        salt_prom = "\n".join(
            [
                line
                for line in salt_prom.split("\n")
                if not line.startswith("salt_last_started")
                and not line.startswith("salt_last_completed")
            ]
        )
        assert salt_prom == expected
