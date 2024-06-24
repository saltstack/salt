import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_api(salt_master, api_request):
    """
    Test running a command against the salt api
    """
    assert salt_master.is_running()

    ret = api_request.post(
        "/run",
        data={
            "client": "local",
            "tgt": "*",
            "fun": "test.arg",
            "arg": ["foo", "bar"],
        },
    )
    assert ret["args"] == ["foo", "bar"]
