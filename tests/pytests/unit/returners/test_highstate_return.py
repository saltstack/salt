"""
Unit tests for the Highstate Returner Cache.
"""

import io
import json

import pytest

import salt.returners.highstate_return as highstate
import salt.utils.files


@pytest.fixture
def output_file(tmp_path):
    return tmp_path / "output-file"


@pytest.fixture
def configure_loader_modules(output_file):
    return {
        highstate: {
            "__opts__": {
                "highstate.report_everything": True,
                "highstate.report_format": "json",
                "highstate.report_delivery": "file",
                "highstate.file_output": str(output_file),
            }
        }
    }


def test_generate_table_should_correctly_escape_html_characters_when_data_contains_both_list_and_dict():
    unescaped_fnord = "&fnord&"
    unescaped_dronf = "<dronf>"
    expected_escaped_fnord = "&amp;fnord&amp;"
    expected_escaped_dronf = "&lt;dronf&gt;"
    data = [["something", "or", "another", unescaped_fnord, {"cool": unescaped_dronf}]]

    out = io.StringIO()
    highstate._generate_html_table(data=data, out=out)
    out.seek(0)
    actual_table = out.read()

    assert expected_escaped_fnord in actual_table
    assert expected_escaped_dronf in actual_table


def test_pipe_in_name(output_file):
    ret = {
        "fun_args": ["test"],
        "jid": "20180308201402941603",
        "return": {
            "cmd_|-test_|-echo hi | grep h\n_|-run": {
                "comment": 'Command "echo hi | grep h\n" run',
                "name": "echo hi | grep h\n",
                "start_time": "20:14:03.053612",
                "result": True,
                "duration": 75.198,
                "__run_num__": 0,
                "__sls__": "test",
                "changes": {
                    "pid": 1429,
                    "retcode": 0,
                    "stderr": "",
                    "stdout": "hi",
                },
                "__id__": "test",
            }
        },
        "retcode": 0,
        "success": True,
        "fun": "state.apply",
        "id": "salt",
        "out": "highstate",
    }
    expected = [
        {
            "stats": [
                {"total": 1},
                {"failed": 0, "__style__": "failed"},
                {"unchanged": 0, "__style__": "unchanged"},
                {"changed": 1, "__style__": "changed"},
                {"duration": 75.198},
            ],
        },
        {
            "job": [
                {"function": "state.apply"},
                {"arguments": ["test"]},
                {"jid": "20180308201402941603"},
                {"success": True},
                {"retcode": 0},
            ],
        },
        {
            "states": [
                {
                    "test": [
                        {"function": "cmd.run"},
                        {"name": "echo hi | grep h\n"},
                        {"result": True},
                        {"duration": 75.198},
                        {"comment": 'Command "echo hi | grep h\n" run'},
                        {
                            "changes": [
                                {"pid": 1429},
                                {"retcode": 0},
                                {"stderr": ""},
                                {"stdout": "hi"},
                            ]
                        },
                        {"started": "20:14:03.053612"},
                    ],
                    "__style__": "changed",
                }
            ]
        },
    ]
    highstate.returner(ret)
    with salt.utils.files.fopen(str(output_file)) as fh_:
        assert json.load(fh_) == expected
