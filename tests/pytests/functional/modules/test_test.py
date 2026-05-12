import pytest


@pytest.mark.parametrize(
    "env,warn_expected",
    [
        ({"PYTHONWARNINGS": "ignore"}, False),
        ({"PYTHONWARNINGS": "test"}, True),
        ({}, True),
    ],
)
def test_deprecation_warnings(salt_call_cli, env, warn_expected):
    """
    Test to ensure when env variable PYTHONWARNINGS=ignore
    is set that we do not add warning to output.
    And when it's not set to ignore the warning will show.
    """
    ret = salt_call_cli.run("--local", "test.deprecation_warning", env=env)
    if warn_expected:
        assert "DeprecationWarning" in ret.stderr
        assert ret.stderr.count("DeprecationWarning") >= 2
    else:
        assert "DeprecationWarning" not in ret.stderr
        assert ret.data


import salt.modules.test as test


def test_raise_exception():
    """
    Add test raising an exception in test module.
    """
    msg = "message"
    with pytest.raises(Exception) as err:
        test.exception(message=msg)
    assert err.match(msg)
