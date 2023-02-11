import logging
import re

import pytest

import salt.output.highstate as highstate

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts.update(
        {
            "extension_modules": "",
            "optimization_order": [0, 1, 2],
            "color": False,
            "state_output_pct": True,
            "state_output": "terse",
        }
    )
    return {highstate: {"__opts__": minion_opts}}


def test_terse_output():
    nested_data = {
        "outputter": "highstate",
        "state_output": "terse",
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
                                    }
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
    # test whether we have at least the normal output
    assert "Succeeded: 1 (changed=1)" in ret
    # test whether the TERSE output is correct
    assert (
        re.search(
            "Name: state[.]orchestrate - Function: salt[.]runner - Result: Changed - Started: [0-2][0-9]:[0-5][0-9]:[0-5][0-9]([.][0-9][0-9]*)? - Duration: [1-9][0-9]*([.][0-9][0-9]*)? ms",
            ret,
        )
        is not None
    )
