import copy
import logging

import pytest

import salt.output.highstate as highstate
import salt.utils.stringutils
from tests.support.mock import patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts.update({"color": False, "state_output_pct": True})
    return {highstate: {"__opts__": minion_opts}}


@pytest.fixture
def json_data():
    return {
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


def test__compress_ids():
    """
    Tests for expected data return for _compress_ids
    and proper formatting using the state_compress_ids option
    """
    # raw data entering the outputter
    data = {
        "local": {
            "cmd_|-mix-matched results_|-/bin/false_|-run": {
                "__id__": "mix-matched results",
                "__run_num__": 7,
                "__sls__": "compress_test",
                "changes": {"pid": 6554, "retcode": 1, "stderr": "", "stdout": ""},
                "comment": "Command " '"/bin/false" ' "run",
                "duration": 8.57,
                "name": "/bin/false",
                "result": False,
                "start_time": "15:38:22.666578",
            },
            "cmd_|-mix-matched results_|-/bin/true_|-run": {
                "__id__": "mix-matched results",
                "__run_num__": 6,
                "__sls__": "compress_test",
                "changes": {"pid": 6553, "retcode": 0, "stderr": "", "stdout": ""},
                "comment": "Command " '"/bin/true" ' "run",
                "duration": 7.728,
                "name": "/bin/true",
                "result": True,
                "start_time": "15:38:22.658452",
            },
            "cmd_|-mix-matched results_|-false_|-run": {
                "__id__": "mix-matched results",
                "__run_num__": 5,
                "__sls__": "compress_test",
                "changes": {"pid": 6552, "retcode": 1, "stderr": "", "stdout": ""},
                "comment": "Command " '"false" run',
                "duration": 7.832,
                "name": "false",
                "result": False,
                "start_time": "15:38:22.650225",
            },
            "cmd_|-mix-matched results_|-true_|-run": {
                "__id__": "mix-matched results",
                "__run_num__": 4,
                "__sls__": "compress_test",
                "changes": {"pid": 6551, "retcode": 0, "stderr": "", "stdout": ""},
                "comment": "Command " '"true" run',
                "duration": 8.538,
                "name": "true",
                "result": True,
                "start_time": "15:38:22.641293",
            },
            "file_|-one clean one changes_|-/tmp/changes_|-managed": {
                "__id__": "one clean one changes",
                "__run_num__": 13,
                "__sls__": "compress_test",
                "changes": {"diff": "New file"},
                "comment": "File /tmp/changes updated",
                "duration": 3.17,
                "name": "/tmp/changes",
                "result": True,
                "start_time": "15:38:22.703770",
            },
            "file_|-one clean one changes_|-/tmp/clean_|-managed": {
                "__id__": "one clean one changes",
                "__run_num__": 12,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "File /tmp/clean is in the correct state",
                "duration": 20.123,
                "name": "/tmp/clean",
                "result": True,
                "start_time": "15:38:22.683450",
            },
            "test_|-succeed clean_|-bar_|-succeed_without_changes": {
                "__id__": "succeed clean",
                "__run_num__": 11,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "Success!",
                "duration": 0.759,
                "name": "bar",
                "result": True,
                "start_time": "15:38:22.678512",
            },
            "test_|-succeed clean_|-foo_|-succeed_without_changes": {
                "__id__": "succeed clean",
                "__run_num__": 10,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "Success!",
                "duration": 0.676,
                "name": "foo",
                "result": True,
                "start_time": "15:38:22.677678",
            },
            "test_|-succeed clean_|-hello_|-succeed_without_changes": {
                "__id__": "succeed clean",
                "__run_num__": 8,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "Success!",
                "duration": 1.071,
                "name": "hello",
                "result": True,
                "start_time": "15:38:22.675588",
            },
            "test_|-succeed clean_|-world_|-succeed_without_changes": {
                "__id__": "succeed clean",
                "__run_num__": 9,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "Success!",
                "duration": 0.693,
                "name": "world",
                "result": True,
                "start_time": "15:38:22.676826",
            },
            "test_|-succeed with changes_|-bar_|-succeed_with_changes": {
                "__id__": "succeed with changes",
                "__run_num__": 3,
                "__sls__": "compress_test",
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "Success!",
                "duration": 0.829,
                "name": "bar",
                "result": True,
                "start_time": "15:38:22.639625",
            },
            "test_|-succeed with changes_|-foo_|-succeed_with_changes": {
                "__id__": "succeed with changes",
                "__run_num__": 2,
                "__sls__": "compress_test",
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "Success!",
                "duration": 0.739,
                "name": "foo",
                "result": True,
                "start_time": "15:38:22.638724",
            },
            "test_|-succeed with changes_|-hello_|-succeed_with_changes": {
                "__id__": "succeed with changes",
                "__run_num__": 0,
                "__sls__": "compress_test",
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "Success!",
                "duration": 0.812,
                "name": "hello",
                "result": True,
                "start_time": "15:38:22.636883",
            },
            "test_|-succeed with changes_|-world_|-succeed_with_changes": {
                "__id__": "succeed with changes",
                "__run_num__": 1,
                "__sls__": "compress_test",
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "Success!",
                "duration": 0.694,
                "name": "world",
                "result": True,
                "start_time": "15:38:22.637872",
            },
            "test_|-single clean_|-single_|-succeed_without_changes": {
                "__id__": "single clean",
                "__run_num__": 14,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "Success!",
                "duration": 0.693,
                "name": "single",
                "result": True,
                "start_time": "15:38:22.676827",
            },
        }
    }
    # expected compressed raw data for outputter
    expected_output = {
        "local": {
            "cmd_|-mix-matched results (2)_|-state_compressed_compress_test_mix-matched results_False_|-run": {
                "__id__": "mix-matched results",
                "__run_num__": 5,
                "__sls__": "compress_test",
                "changes": {
                    "compressed changes": {
                        "/bin/false": {
                            "pid": 6554,
                            "retcode": 1,
                            "stderr": "",
                            "stdout": "",
                        },
                        "false": {
                            "pid": 6552,
                            "retcode": 1,
                            "stderr": "",
                            "stdout": "",
                        },
                    }
                },
                "comment": "Command " '"/bin/false" ' "run",
                "duration": 16.402,
                "name": "/bin/false",
                "result": False,
                "start_time": "15:38:22.650225",
            },
            "cmd_|-mix-matched results (2)_|-state_compressed_compress_test_mix-matched results_True_|-run": {
                "__id__": "mix-matched results",
                "__run_num__": 4,
                "__sls__": "compress_test",
                "changes": {
                    "compressed changes": {
                        "/bin/true": {
                            "pid": 6553,
                            "retcode": 0,
                            "stderr": "",
                            "stdout": "",
                        },
                        "true": {"pid": 6551, "retcode": 0, "stderr": "", "stdout": ""},
                    }
                },
                "comment": "Command " '"/bin/true" ' "run",
                "duration": 16.266,
                "name": "/bin/true",
                "result": True,
                "start_time": "15:38:22.641293",
            },
            "file_|-one clean one changes (2)_|-state_compressed_compress_test_one clean one changes_True_|-managed": {
                "__id__": "one clean one changes",
                "__run_num__": 12,
                "__sls__": "compress_test",
                "changes": {"diff": "New file"},
                "comment": "File /tmp/changes updated",
                "duration": 23.293,
                "name": "/tmp/changes",
                "result": True,
                "start_time": "15:38:22.683450",
            },
            "test_|-succeed clean (4)_|-state_compressed_compress_test_succeed clean_True_|-succeed_without_changes": {
                "__id__": "succeed clean",
                "__run_num__": 8,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "Success!",
                "duration": 3.199,
                "name": "bar",
                "result": True,
                "start_time": "15:38:22.675588",
            },
            "test_|-succeed with changes (4)_|-state_compressed_compress_test_succeed with changes_True_|-succeed_with_changes": {
                "__id__": "succeed with changes",
                "__run_num__": 0,
                "__sls__": "compress_test",
                "changes": {
                    "compressed changes": {
                        "bar": {
                            "testing": {
                                "new": "Something pretended to change",
                                "old": "Unchanged",
                            }
                        },
                        "foo": {
                            "testing": {
                                "new": "Something pretended to change",
                                "old": "Unchanged",
                            }
                        },
                        "hello": {
                            "testing": {
                                "new": "Something pretended to change",
                                "old": "Unchanged",
                            }
                        },
                        "world": {
                            "testing": {
                                "new": "Something pretended to change",
                                "old": "Unchanged",
                            }
                        },
                    }
                },
                "comment": "Success!",
                "duration": 3.074,
                "name": "bar",
                "result": True,
                "start_time": "15:38:22.636883",
            },
            "test_|-single clean_|-single_|-succeed_without_changes": {
                "__id__": "single clean",
                "__run_num__": 14,
                "__sls__": "compress_test",
                "changes": {},
                "comment": "Success!",
                "duration": 0.693,
                "name": "single",
                "result": True,
                "start_time": "15:38:22.676827",
            },
        }
    }
    actual_output = highstate._compress_ids(data)

    # return properly compressed data
    assert actual_output == expected_output

    # check output text for formatting
    opts = copy.deepcopy(highstate.__opts__)
    opts["state_compress_ids"] = True
    with patch("salt.output.highstate.__opts__", opts, create=True):
        actual_output = highstate.output(data)
    assert "          ID: succeed with changes (4)" in actual_output
    assert (
        "        Name: state_compressed_compress_test_succeed with changes_True"
        in actual_output
    )
    assert "              compressed changes:" in actual_output
    assert "          ID: mix-matched results (2)" in actual_output
    assert (
        "        Name: state_compressed_compress_test_mix-matched results_True"
        in actual_output
    )
    assert (
        "        Name: state_compressed_compress_test_mix-matched results_False"
        in actual_output
    )
    assert "          ID: succeed clean (4)" in actual_output
    assert (
        "        Name: state_compressed_compress_test_succeed clean_True"
        in actual_output
    )
    assert "          ID: one clean one changes (2)" in actual_output
    assert (
        "        Name: state_compressed_compress_test_one clean one changes_True"
        in actual_output
    )
    assert "              diff:" in actual_output
    assert "Succeeded: 13 (changed=9)" in actual_output
    assert "Failed:     2" in actual_output
    assert "Success %: 86.67" in actual_output
    assert "Failure %: 13.33" in actual_output
    assert "Total states run:     15" in actual_output

    # pop out a __run_num__ to break the data
    data["local"]["cmd_|-mix-matched results_|-/bin/false_|-run"].pop("__run_num__")
    actual_output = highstate._compress_ids(data)

    # expecting return of original data to let the outputter figure it out
    assert actual_output == data


def test__compress_ids_not_dict():
    """
    Simple test for returning original malformed data
    to let the outputter figure it out.
    """
    data = ["malformed"]
    actual_output = highstate._compress_ids(data)
    assert actual_output == data


def test__compress_ids_multiple_module_functions():
    """
    Tests for expected data return for _compress_ids
    when using multiple mod.fun combos under the ID
    """
    # raw data entering the outputter
    data = {
        "local": {
            "cmd_|-try_this_|-echo 'hi'_|-run": {
                "__id__": "try_this",
                "__run_num__": 1,
                "__sls__": "wayne",
                "changes": {"pid": 32615, "retcode": 0, "stderr": "", "stdout": "hi"},
                "comment": 'Command "echo ' "'hi'\" run",
                "duration": 8.218,
                "name": "echo 'hi'",
                "result": True,
                "start_time": "23:43:25.715842",
            },
            "test_|-try_this_|-asdf_|-nop": {
                "__id__": "try_this",
                "__run_num__": 0,
                "__sls__": "wayne",
                "changes": {},
                "comment": "Success!",
                "duration": 0.906,
                "name": "asdf",
                "result": True,
                "start_time": "23:43:25.714010",
            },
        }
    }

    # check output text for formatting
    opts = copy.deepcopy(highstate.__opts__)
    opts["state_compress_ids"] = True
    with patch("salt.output.highstate.__opts__", opts, create=True):
        actual_output = highstate.output(data)

    # if we only cared about the ID/SLS/Result combo, this would be 4 not 2
    assert "Succeeded: 2 (changed=1)" in actual_output
    assert "Failed:    0" in actual_output
    assert "Total states run:     2" in actual_output


def test_parallel_summary_output():
    data = {
        "local": {
            "test_|-barrier_|-barrier_|-nop": {
                "name": "barrier",
                "changes": {},
                "result": True,
                "comment": "Success!",
                "__sls__": "test.49273",
                "__run_num__": 0,
                "start_time": "15:11:31.459770",
                "duration": 0.698,
                "__id__": "barrier",
            },
            "cmd_|-blah-1_|-sleep 10_|-run": {
                "name": "sleep 10",
                "result": True,
                "changes": {"pid": 524313, "retcode": 0, "stdout": "", "stderr": ""},
                "comment": 'Command "sleep 10" run',
                "__sls__": "test.49273",
                "__run_num__": 1,
                "start_time": "15:11:31.496410",
                "duration": 10007.711,
                "__id__": "blah-1",
                "__parallel__": True,
            },
            "cmd_|-blah-2_|-sleep 10_|-run": {
                "name": "sleep 10",
                "result": True,
                "changes": {"pid": 524315, "retcode": 0, "stdout": "", "stderr": ""},
                "comment": 'Command "sleep 10" run',
                "__sls__": "test.49273",
                "__run_num__": 2,
                "start_time": "15:11:31.537001",
                "duration": 10007.264,
                "__id__": "blah-2",
                "__parallel__": True,
            },
            "cmd_|-blah-3_|-sleep 10_|-run": {
                "name": "sleep 10",
                "result": True,
                "changes": {"pid": 524317, "retcode": 0, "stdout": "", "stderr": ""},
                "comment": 'Command "sleep 10" run',
                "__sls__": "test.49273",
                "__run_num__": 3,
                "start_time": "15:11:31.577076",
                "duration": 10008.646,
                "__id__": "blah-3",
                "__parallel__": True,
            },
            "test_|-barrier2_|-barrier2_|-nop": {
                "name": "barrier2",
                "changes": {},
                "result": True,
                "comment": "Success!",
                "__sls__": "test.49273",
                "__run_num__": 4,
                "start_time": "15:11:41.619874",
                "duration": 0.762,
                "__id__": "barrier2",
            },
        }
    }

    actual_output = highstate.output(data)

    assert "Succeeded: 5 (changed=3)" in actual_output
    assert "Failed:    0" in actual_output
    assert "Total states run:     5" in actual_output

    # The three main states were run in parallel and slept for
    # 10 seconds each so the total run time should around 10 seconds
    assert "Total run time:  10.010 s" in actual_output


def test_summary_output():
    data = {
        "local": {
            "test_|-barrier_|-barrier_|-nop": {
                "name": "barrier",
                "changes": {},
                "result": True,
                "comment": "Success!",
                "__sls__": "test.49273",
                "__run_num__": 0,
                "start_time": "15:11:31.459770",
                "duration": 0.698,
                "__id__": "barrier",
            },
            "cmd_|-blah-1_|-sleep 10_|-run": {
                "name": "sleep 10",
                "result": True,
                "changes": {"pid": 524313, "retcode": 0, "stdout": "", "stderr": ""},
                "comment": 'Command "sleep 10" run',
                "__sls__": "test.49273",
                "__run_num__": 1,
                "start_time": "15:11:31.496410",
                "duration": 10007.711,
                "__id__": "blah-1",
            },
            "cmd_|-blah-2_|-sleep 10_|-run": {
                "name": "sleep 10",
                "result": True,
                "changes": {"pid": 524315, "retcode": 0, "stdout": "", "stderr": ""},
                "comment": 'Command "sleep 10" run',
                "__sls__": "test.49273",
                "__run_num__": 2,
                "start_time": "15:11:31.537001",
                "duration": 10007.264,
                "__id__": "blah-2",
            },
            "cmd_|-blah-3_|-sleep 10_|-run": {
                "name": "sleep 10",
                "result": True,
                "changes": {"pid": 524317, "retcode": 0, "stdout": "", "stderr": ""},
                "comment": 'Command "sleep 10" run',
                "__sls__": "test.49273",
                "__run_num__": 3,
                "start_time": "15:11:31.577076",
                "duration": 10008.646,
                "__id__": "blah-3",
            },
            "test_|-barrier2_|-barrier2_|-nop": {
                "name": "barrier2",
                "changes": {},
                "result": True,
                "comment": "Success!",
                "__sls__": "test.49273",
                "__run_num__": 4,
                "start_time": "15:11:41.619874",
                "duration": 0.762,
                "__id__": "barrier2",
            },
        }
    }

    actual_output = highstate.output(data)

    assert "Succeeded: 5 (changed=3)" in actual_output
    assert "Failed:    0" in actual_output
    assert "Total states run:     5" in actual_output

    # The three main states were not run in parallel and slept for
    # 10 seconds each so the total run time should around 30 seconds
    assert "Total run time:  30.025 s" in actual_output


def test_default_output(json_data):
    ret = highstate.output(json_data)
    assert "Succeeded: 1 (changed=1)" in ret
    assert "Failed:    0" in ret
    assert "Total states run:     1" in ret
    assert "                  file2" in ret


def test_output_comment_is_not_unicode(json_data):
    entry = None
    for key in (
        "data",
        "master",
        "salt_|-call_sleep_state_|-call_sleep_state_|-state",
        "changes",
        "ret",
        "minion",
        "module_|-simple-ping_|-test.ping_|-run",
    ):
        if entry is None:
            entry = json_data[key]
            continue
        entry = entry[key]
    entry["comment"] = salt.utils.stringutils.to_bytes(entry["comment"])
    ret = highstate.output(json_data)
    assert "Succeeded: 1 (changed=1)" in ret
    assert "Failed:    0" in ret
    assert "Total states run:     1" in ret
    assert "                  file2" in ret


def test_nested_output():
    nested_data = {
        "outputter": "highstate",
        "data": {
            "local_master": {
                "salt_|-nested_|-state.orchestrate_|-runner": {
                    "comment": "Runner function 'state.orchestrate' executed.",
                    "name": "state.orchestrate",
                    "start_time": "09:22:53.158742",
                    "result": True,
                    "duration": 980.694,
                    "__run_num__": 0,
                    "__jid__": "20180326092253538853",
                    "__sls__": "orch.test.nested",
                    "changes": {
                        "return": {
                            "outputter": "highstate",
                            "data": {
                                "local_master": {
                                    "test_|-always-passes-with-changes_|-oinaosf_|-succeed_with_changes": {
                                        "comment": "Success!",
                                        "name": "oinaosf",
                                        "start_time": "09:22:54.128415",
                                        "result": True,
                                        "duration": 0.437,
                                        "__run_num__": 0,
                                        "__sls__": "orch.test.changes",
                                        "changes": {
                                            "testing": {
                                                "new": (
                                                    "Something pretended to change"
                                                ),
                                                "old": "Unchanged",
                                            }
                                        },
                                        "__id__": "always-passes-with-changes",
                                    },
                                    "test_|-always-passes_|-fasdfasddfasdfoo_|-succeed_without_changes": {
                                        "comment": "Success!",
                                        "name": "fasdfasddfasdfoo",
                                        "start_time": "09:22:54.128986",
                                        "result": True,
                                        "duration": 0.25,
                                        "__run_num__": 1,
                                        "__sls__": "orch.test.changes",
                                        "changes": {},
                                        "__id__": "always-passes",
                                    },
                                }
                            },
                            "retcode": 0,
                        }
                    },
                    "__id__": "nested",
                }
            }
        },
        "retcode": 0,
    }

    ret = highstate.output(nested_data)
    assert "Succeeded: 1 (changed=1)" in ret
    assert "Failed:    0" in ret
    assert "Total states run:     1" in ret

    # the whitespace is relevant in this case, it is testing that it is nested
    assert "                        ID: always-passes-with-changes" in ret
    assert "                   Started: 09:22:54.128415" in ret
    assert "              Succeeded: 2 (changed=1)" in ret
    assert "              Failed:    0" in ret
    assert "              Total states run:     2" in ret
