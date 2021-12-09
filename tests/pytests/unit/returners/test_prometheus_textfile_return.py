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


@pytest.fixture
def job_ret():
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
    return ret


@pytest.fixture
def patch_dunders(cache_dir, temp_salt_minion):
    opts = temp_salt_minion.config.copy()
    opts["cachedir"] = cache_dir
    with patch("salt.returners.prometheus_textfile.__opts__", opts, create=True), patch(
        "salt.returners.prometheus_textfile.__salt__", {}, create=True
    ):
        yield


def test_basic_prometheus_output_with_default_options(
    patch_dunders, job_ret, cache_dir, temp_salt_minion
):
    expected = "\n".join(
        sorted(
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
            ]
        )
    )

    prometheus_textfile.returner(job_ret)

    with salt.utils.files.fopen(
        os.path.join(cache_dir, "prometheus_textfile", "salt.prom")
    ) as prom_file:
        # Drop time-based fields for comparison
        salt_prom = "\n".join(
            sorted(
                [
                    line[:-1]
                    for line in prom_file
                    if not line.startswith("salt_last_started")
                    and not line.startswith("salt_last_completed")
                ]
            )
        )
    assert salt_prom == expected


@pytest.mark.parametrize(
    "state_name,filename,expected_filename",
    [
        ("aaa", "one", "one-aaa"),
        ("bbb", "one.two", "one-bbb.two"),
        ("ccc", "one.two.three", "one.two-ccc.three"),
        ("ddd", "one.two.three.four", "one.two.three-ddd.four"),
    ],
)
def test_when_add_state_name_is_set_then_correct_output_should_be_in_correct_file(
    patch_dunders,
    state_name,
    filename,
    expected_filename,
    temp_salt_minion,
    cache_dir,
    job_ret,
):
    job_ret["fun_args"][0] = state_name
    prometheus_textfile.__opts__.update(
        {"add_state_name": True, "filename": os.path.join(cache_dir, filename)}
    )

    expected = "\n".join(
        sorted(
            [
                "# HELP salt_procs Number of salt minion processes running",
                "# TYPE salt_procs gauge",
                f'salt_procs{{state="{state_name}"}} 0',
                "# HELP salt_states_succeeded Number of successful states in the run",
                "# TYPE salt_states_succeeded gauge",
                f'salt_states_succeeded{{state="{state_name}"}} 2',
                "# HELP salt_states_failed Number of failed states in the run",
                "# TYPE salt_states_failed gauge",
                f'salt_states_failed{{state="{state_name}"}} 0',
                "# HELP salt_states_changed Number of changed states in the run",
                "# TYPE salt_states_changed gauge",
                f'salt_states_changed{{state="{state_name}"}} 2',
                "# HELP salt_states_total Total states in the run",
                "# TYPE salt_states_total gauge",
                f'salt_states_total{{state="{state_name}"}} 2',
                "# HELP salt_states_success_pct Percent of successful states in the run",
                "# TYPE salt_states_success_pct gauge",
                f'salt_states_success_pct{{state="{state_name}"}} 100.0',
                "# HELP salt_states_failure_pct Percent of failed states in the run",
                "# TYPE salt_states_failure_pct gauge",
                f'salt_states_failure_pct{{state="{state_name}"}} 0.0',
                "# HELP salt_states_changed_pct Percent of changed states in the run",
                "# TYPE salt_states_changed_pct gauge",
                f'salt_states_changed_pct{{state="{state_name}"}} 100.0',
                "# HELP salt_elapsed_time Time spent for all operations during the state run",
                "# TYPE salt_elapsed_time gauge",
                f'salt_elapsed_time{{state="{state_name}"}} 13.695',
                "# HELP salt_last_started Estimated time the state run started",
                "# TYPE salt_last_started gauge",
                "# HELP salt_last_completed Time of last state run completion",
                "# TYPE salt_last_completed gauge",
            ]
        )
    )
    prometheus_textfile.returner(job_ret)

    with salt.utils.files.fopen(
        os.path.join(cache_dir, expected_filename)
    ) as prom_file:
        # use line[:-1] to strip off the newline, but only one. It may be extra
        # paranoid due to how Python file iteration works, but...
        salt_prom = "\n".join(
            sorted(
                line[:-1]
                for line in prom_file
                if not line.startswith("salt_last_started")
                and not line.startswith("salt_last_completed")
            )
        )
    assert salt_prom == expected
