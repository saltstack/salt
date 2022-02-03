import pytest
import salt.config
import salt.output.highstate as highstate


@pytest.fixture
def configure_loader_modules():
    minion_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    minion_opts.update({"color": False, "state_output_pct": True})
    return {highstate: {"__opts__": minion_opts}}


@pytest.mark.parametrize("data", [None, {"return": None}, {"return": {"data": None}}])
def test_when_data_result_is_None_output_should_be_string_None(data):
    expected_output = "None"

    actual_output = highstate.output(data=data)

    assert actual_output == expected_output


def test_when_data_is_dict_with_return_key_and_return_value_has_data_key_and_data_dict_has_one_dict_element_with_jid_and_fun_keys_and_return_value_is_None_then_output_should_return_literal_None_string():

    expected_output = "None"
    data = {
        "return": {
            "data": {
                "foo bar quux fnord": {
                    "jid": "fnordy fnordy fnordy",
                    "fun": "fnordy fnordy fnord",
                    "return": {"data": None},
                },
            }
        },
    }

    actual_output = highstate.output(data=data)

    assert actual_output == expected_output


@pytest.mark.parametrize(
    "return_value",
    [42, "fnord"],
)
def test_when_data_is_dict_with_return_key_and_return_value_has_data_key_and_data_dict_has_one_dict_element_with_jid_and_fun_keys_and_return_value_is_int_or_str_that_value_should_be_returned(
    return_value,
):

    expected_output = return_value
    data = {
        "return": {
            "data": {
                "foo bar quux fnord": {
                    "jid": "fnordy fnordy fnordy",
                    "fun": "fnordy fnordy fnord",
                    "return": {"data": return_value},
                },
            }
        },
    }

    actual_output = highstate.output(data=data)

    assert actual_output == expected_output


def test_when_orchestrator_output_retcode_in_data_the_retcode_should_be_removed():
    data = {"something_master": None, "retcode": 42}

    actual_output = highstate.output(data)

    assert "retcode" not in data


def test_when_more_than_one_local_master_retcode_should_not_be_removed():
    expected_retcode = 42
    data = {
        "something_master": None,
        "another_master": None,
        "retcode": expected_retcode,
    }

    actual_output = highstate.output(data)

    assert data["retcode"] == expected_retcode


def test_pct_summary_output():
    data = {
        "data": {
            "master": {
                "salt_|-call_sleep_state_|-call_sleep_state_|-state": {
                    "__id__": "call_sleep_state",
                    "__jid__": "20170418153529810135",
                    "__run_num__": 0,
                    "__sls__": "orch.simple",
                    "changes": {
                        "out": "highstate",
                        "ret": {
                            "minion": {
                                "module_|-simple-ping_|-test.ping_|-run": {
                                    "__id__": "simple-ping",
                                    "__run_num__": 0,
                                    "__sls__": "simple-ping",
                                    "changes": {"ret": True},
                                    "comment": "Module function test.ping executed",
                                    "duration": 56.179,
                                    "name": "test.ping",
                                    "result": True,
                                    "start_time": "15:35:31.282099",
                                }
                            },
                            "sub_minion": {
                                "module_|-simple-ping_|-test.ping_|-run": {
                                    "__id__": "simple-ping",
                                    "__run_num__": 0,
                                    "__sls__": "simple-ping",
                                    "changes": {"ret": True},
                                    "comment": "Module function test.ping executed",
                                    "duration": 54.103,
                                    "name": "test.ping",
                                    "result": True,
                                    "start_time": "15:35:31.005606",
                                }
                            },
                        },
                    },
                    "comment": (
                        "States ran successfully. Updating sub_minion, minion."
                    ),
                    "duration": 1638.047,
                    "name": "call_sleep_state",
                    "result": True,
                    "start_time": "15:35:29.762657",
                },
                "salt_|-cmd_run_example_|-cmd.run_|-function": {
                    "__id__": "cmd_run_example",
                    "__jid__": "20200411195112288850",
                    "__run_num__": 1,
                    "__sls__": "orch.simple",
                    "changes": {
                        "out": "highstate",
                        "ret": {"minion": "file1\nfile2\nfile3"},
                    },
                    "comment": (
                        "Function ran successfully. Function cmd.run ran on minion."
                    ),
                    "duration": 412.397,
                    "name": "cmd.run",
                    "result": True,
                    "start_time": "21:51:12.185868",
                },
            }
        },
        "outputter": "highstate",
        "retcode": 0,
    }

    actual_output = highstate.output(data)
    assert "Succeeded: 1 (changed=1)" in actual_output
    assert "Failed:    0" in actual_output
    assert "Success %: 100.0" in actual_output
    assert "Failure %: 0.0" in actual_output
    assert "Total states run:     1" in actual_output
    assert "                  file2" in actual_output
