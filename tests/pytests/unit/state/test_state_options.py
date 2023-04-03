import itertools

import pytest

import salt.state

pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def master_opts(master_opts):
    """
    Return a subset of master options to the minion
    """
    opts = master_opts.copy()
    mopts = {}
    mopts["file_roots"] = opts["file_roots"]
    mopts["top_file_merging_strategy"] = opts["top_file_merging_strategy"]
    mopts["env_order"] = opts["env_order"]
    mopts["default_top"] = opts["default_top"]
    mopts["renderer"] = opts["renderer"]
    mopts["failhard"] = opts["failhard"]
    mopts["state_top"] = opts["state_top"]
    mopts["state_top_saltenv"] = opts["state_top_saltenv"]
    mopts["nodegroups"] = opts["nodegroups"]
    mopts["state_auto_order"] = opts["state_auto_order"]
    mopts["state_events"] = opts["state_events"]
    mopts["state_aggregate"] = opts["state_aggregate"]
    mopts["jinja_env"] = opts["jinja_env"]
    mopts["jinja_sls_env"] = opts["jinja_sls_env"]
    mopts["jinja_lstrip_blocks"] = opts["jinja_lstrip_blocks"]
    mopts["jinja_trim_blocks"] = opts["jinja_trim_blocks"]
    return mopts


class MockBaseHighStateClient:
    def __init__(self, opts):
        self.opts = opts

    def master_opts(self):
        return self.opts


def test_state_aggregate_option_behavior(master_opts, minion_opts):
    """
    Ensure state_aggregate can be overridden on the minion
    """
    possible = [None, True, False, ["pkg"]]
    expected_result = [
        True,
        False,
        ["pkg"],
        True,
        True,
        ["pkg"],
        False,
        True,
        ["pkg"],
        ["pkg"],
        True,
        ["pkg"],
    ]

    for idx, combo in enumerate(itertools.permutations(possible, 2)):
        master_opts["state_aggregate"], minion_opts["state_aggregate"] = combo
        state_obj = salt.state.BaseHighState
        state_obj.client = MockBaseHighStateClient(master_opts)
        return_result = state_obj(minion_opts)._BaseHighState__gen_opts(minion_opts)
        assert expected_result[idx] == return_result["state_aggregate"]
