import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_onlyif_req_retcode(state):
    ret = state.single(
        fun="test.succeed_with_changes",
        name="onlyif test",
        onlyif=[{"fun": "test.retcode"}],
    )
    state_id = "test_|-onlyif test_|-onlyif test_|-succeed_with_changes"
    assert ret[state_id]["result"] is True
    assert not ret[state_id]["changes"]
    assert ret[state_id]["comment"] == "onlyif condition is false"

    ret = state.single(
        fun="test.succeed_with_changes",
        name="onlyif test",
        onlyif=[{"fun": "test.retcode", "code": 0}],
    )
    state_id = "test_|-onlyif test_|-onlyif test_|-succeed_with_changes"
    assert ret[state_id]["result"] is True
    assert ret[state_id]["changes"]
    assert ret[state_id]["comment"] == "Success!"
