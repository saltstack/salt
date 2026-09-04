import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_api(api_request, install_salt, salt_master, salt_minion):
    """
    Test running a command against the salt api
    """
    if install_salt.distro_id in ("ubuntu", "debian"):
        pytest.skip(
            "Package test are getting reworked in https://github.com/saltstack/salt/issues/66672"
        )

    assert salt_master.is_running()
    # The local-client fan-out below needs at least one minion to respond.
    # Without ``salt_minion`` in the fixture chain the auto-installed
    # launchctl-managed daemon is the only candidate, and on macOS its
    # default config (``master: salt``) does not resolve to the test master.
    assert salt_minion.is_running()

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
