import pytest
from saltfactories.utils.functional import MultiStateResult


@pytest.mark.skip_on_windows(reason="Linux test only")
def test_services(install_salt, salt_cli, salt_minion):
    """
    Check if Services are enabled/disabled
    """
    if install_salt.compressed:
        pytest.skip("Skip test on single binary and onedir package")

    ret = salt_cli.run("grains.get", "os_family", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data

    state_name = desired_state = None
    os_family = ret.data

    if os_family == "Debian":
        state_name = "debianbased"
        desired_state = "enabled"
    elif os_family == "RedHat":
        state_name = "redhatbased"
        desired_state = "disabled"
    else:
        pytest.fail(f"Don't know how to handle os_family={os_family}")

    ret = salt_cli.run("state.apply", state_name, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data

    expected_in_comment = f"is already {desired_state}, and is in the desired state"

    result = MultiStateResult(raw=ret.data)
    for state_ret in result:
        assert state_ret.result is True
        if "__id__" not in state_ret.full_return:
            # This is a state requirement
            # For example:
            #  State was not run because none of the onchanges reqs changed
            continue
        assert expected_in_comment in state_ret.comment
