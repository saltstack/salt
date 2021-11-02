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
    assert ret.result is True
    assert not ret.changes
    assert ret.comment == "onlyif condition is false"

    ret = state.single(
        fun="test.succeed_with_changes",
        name="onlyif test",
        onlyif=[{"fun": "test.retcode", "code": 0}],
    )
    assert ret.result is True
    assert ret.changes
    assert ret.comment == "Success!"
