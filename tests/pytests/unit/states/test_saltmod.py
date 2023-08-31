import pytest

import salt.modules.saltutil as saltutil
import salt.states.saltmod as saltmod
from tests.support.mock import create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {saltmod: {"__opts__": {"__role": "testsuite"}}}


@pytest.fixture
def fake_cmd():
    fake_cmd = create_autospec(saltutil.cmd)
    with patch.dict(saltmod.__salt__, {"saltutil.cmd": fake_cmd}):
        yield fake_cmd


@pytest.mark.parametrize(
    "exclude",
    [True, False],
)
def test_exclude_parameter_gets_passed(exclude, fake_cmd):
    """
    Smoke test for for salt.states.statemod.state().  Ensures that we
    don't take an exception if optional parameters are not specified in
    __opts__ or __env__.
    """
    args = ("webserver_setup", "webserver2")
    expected_exclude = exclude
    kwargs = {
        "tgt_type": "glob",
        "exclude": expected_exclude,
        "highstate": True,
    }

    saltmod.state(*args, **kwargs)

    call = fake_cmd.call_args[1]
    assert call["kwarg"]["exclude"] == expected_exclude


def test_exclude_parameter_is_not_passed_if_not_provided(fake_cmd):
    # Make sure we don't barf on existing behavior
    args = ("webserver_setup", "webserver2")
    kwargs_without_exclude = {
        "tgt_type": "glob",
        "highstate": True,
    }

    saltmod.state(*args, **kwargs_without_exclude)

    call = fake_cmd.call_args[1]
    assert "exclude" not in call["kwarg"]
