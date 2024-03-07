import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.core_test,
]


@pytest.mark.timeout(120)
def test_unless_req(state):
    ret = state.single(fun="test.succeed_with_changes", name="unless test", unless=[{}])
    assert ret.result is True
    assert ret.comment == "Success!"

    ret = state.single(
        fun="test.fail_with_changes", name="unless test", unless=[{"fun": "test.true"}]
    )
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "unless condition is true"

    ret = state.single(
        fun="test.fail_with_changes", name="unless test", unless=[{"fun": "test.false"}]
    )
    assert ret.result is False
    assert ret.changes
    assert ret.comment == "Failure!"

    ret = state.single(
        fun="test.succeed_without_changes",
        name="unless test",
        unless=[{"fun": "test.false"}],
    )
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "Success!"


@pytest.mark.timeout(120)
def test_unless_req_retcode(state):
    ret = state.single(
        fun="test.succeed_with_changes",
        name="unless test",
        unless=[{"fun": "test.retcode"}],
    )
    assert ret.result is True
    assert ret.changes
    assert ret.comment == "Success!"

    ret = state.single(
        fun="test.succeed_with_changes",
        name="unless test",
        unless=[{"fun": "test.retcode", "code": 0}],
    )
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "unless condition is true"
