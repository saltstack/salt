import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_unless_req(state):
    ret = state.single(fun="test.succeed_with_changes", name="unless test", unless=[{}])
    state_id = "test_|-unless test_|-unless test_|-succeed_with_changes"
    assert ret[state_id]["result"] is True
    assert ret[state_id]["comment"] == "Success!"

    ret = state.single(
        fun="test.fail_with_changes", name="unless test", unless=[{"fun": "test.true"}]
    )
    state_id = "test_|-unless test_|-unless test_|-fail_with_changes"
    assert ret[state_id]["result"] is True
    assert not ret[state_id]["changes"]
    assert ret[state_id]["comment"] == "unless condition is true"

    ret = state.single(
        fun="test.fail_with_changes", name="unless test", unless=[{"fun": "test.false"}]
    )
    state_id = "test_|-unless test_|-unless test_|-fail_with_changes"
    assert ret[state_id]["result"] is False
    assert ret[state_id]["changes"]
    assert ret[state_id]["comment"] == "Failure!"

    ret = state.single(
        fun="test.succeed_without_changes",
        name="unless test",
        unless=[{"fun": "test.false"}],
    )
    state_id = "test_|-unless test_|-unless test_|-succeed_without_changes"
    assert ret[state_id]["result"] is True
    assert not ret[state_id]["changes"]
    assert ret[state_id]["comment"] == "Success!"


def test_unless_req_retcode(state):
    ret = state.single(
        fun="test.succeed_with_changes",
        name="unless test",
        unless=[{"fun": "test.retcode"}],
    )
    state_id = "test_|-unless test_|-unless test_|-succeed_with_changes"
    assert ret[state_id]["result"] is True
    assert ret[state_id]["changes"]
    assert ret[state_id]["comment"] == "Success!"

    ret = state.single(
        fun="test.succeed_with_changes",
        name="unless test",
        unless=[{"fun": "test.retcode", "code": 0}],
    )
    state_id = "test_|-unless test_|-unless test_|-succeed_with_changes"
    assert ret[state_id]["result"] is True
    assert not ret[state_id]["changes"]
    assert ret[state_id]["comment"] == "unless condition is true"
