import pytest
import salt.states.service as service
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {service: {}}


def test_when_service_available_in_dunder_salt_then_it_should_be_used():
    expected_ret = {}
    with patch.dict(service.__salt__, {"service.available": lambda x: True}):
        ret = {}
        assert service._available(name="fnord", ret=ret)
        assert ret == expected_ret


def test_when_service_get_all_in_dunder_salt_it_should_be_used_as_fallback():
    avail_services = ["fnord", "foo", "bar"]
    expected_ret = {}
    with patch.dict(service.__salt__, {"service.get_all": lambda: avail_services}):
        ret = {}
        assert service._available(name=avail_services[0], ret=ret)
        assert ret == expected_ret


def test_when_neither_available_or_get_all_in_dunder_salt_then_result_should_be_False():
    expected_ret = {
        "result": False,
        "comment": "The named service fnord is not available",
    }
    ret = {}
    assert not service._available(name="fnord", ret=ret)
    assert ret == expected_ret


@pytest.mark.parametrize(
    "test_func", [service._enable, service._disable],
)
def test_when_skip_verify_enable_should_ignore_if_service_is_available(test_func):
    with patch(
        "salt.states.service._available", side_effect=Exception("Should not be raised")
    ):
        test_func("fnord", "fnord", skip_verify=True)


@pytest.mark.parametrize(
    "test_func", [service._enable, service._disable],
)
def test_when_not_skip_verify_and_available_raises_CommandExecutionError_result_should_be_false_with_exec_strerror(
    test_func,
):
    expected_comment = "This is the raised error message"
    expected_result = {"result": False, "comment": expected_comment}
    with patch(
        "salt.states.service._available",
        side_effect=CommandExecutionError(expected_comment),
    ):
        actual_result = test_func("fnord", "fnord", skip_verify=False)

    assert actual_result == expected_result


@pytest.mark.parametrize(
    "result,test_func", [(False, service._enable), (True, service._disable)]
)
@pytest.mark.parametrize("mod_name", ["service.available", "service.get_all"])
def test_when_not_skip_verify_and_service_not_available_result_should_be_correct_with_informative_comment(
    mod_name, result, test_func,
):
    expected_result = {
        "result": result,
        "comment": "The named service fnord is not available",
    }
    # Returning [] is not, strictly speaking, a requirement. That just
    # simplifiesthis test. If _available needs to change for some reason, then
    # this test will need to be updated.
    with patch.dict(service.__salt__, {mod_name: lambda *args, **kwargs: []}):
        actual_result = test_func("fnord", "fnord", skip_verify=False)

    assert actual_result == expected_result


def test_when_enable_skip_verify_and_test_and_service_not_available_then_result_should_be_None():
    expected_result = {"result": None, "comment": "Service fnord set to be enabled"}
    patch_salt = patch.dict(
        service.__salt__,
        {"service.enabled": lambda name, **kwargs: False, "service.enable": None},
    )
    patch_opts = patch.dict(service.__opts__, {"test": True})
    with patch_salt, patch_opts:
        actual_result = service._enable("fnord", "fnord", skip_verify=True)

    assert actual_result == expected_result


def test_when_enable_skip_verify_and_available_would_have_errored_then_test_result_should_be_none():
    expected_result = {"result": None, "comment": "Service fnord set to be enabled"}
    patch_salt = patch.dict(
        service.__salt__,
        {"service.enabled": lambda name, **kwargs: False, "service.enable": None},
    )
    patch_opts = patch.dict(service.__opts__, {"test": True})
    patch_available = patch(
        "salt.states.service._available",
        side_effect=CommandExecutionError("This should not be raised"),
    )
    with patch_salt, patch_opts, patch_available:
        actual_result = service._enable("fnord", "fnord", skip_verify=True)

    assert actual_result == expected_result


def test_when_disable_skip_verify_and_test_and_service_not_available_then_result_should_be_None():
    expected_result = {"result": None, "comment": "Service fnord set to be disabled"}
    patch_salt = patch.dict(
        service.__salt__,
        {"service.disabled": lambda name, **kwargs: False, "service.disable": None},
    )
    patch_opts = patch.dict(service.__opts__, {"test": True})
    with patch_salt, patch_opts:
        actual_result = service._disable("fnord", "fnord", skip_verify=True)

    assert actual_result == expected_result


def test_when_disable_skip_verify_and_available_would_have_errored_then_test_result_should_be_none():
    expected_result = {"result": None, "comment": "Service fnord set to be disabled"}
    patch_salt = patch.dict(
        service.__salt__,
        {"service.disabled": lambda name, **kwargs: False, "service.disable": None},
    )
    patch_opts = patch.dict(service.__opts__, {"test": True})
    patch_available = patch(
        "salt.states.service._available",
        side_effect=CommandExecutionError("This should not be raised"),
    )
    with patch_salt, patch_opts, patch_available:
        actual_result = service._disable("fnord", "fnord", skip_verify=True)

    assert actual_result == expected_result


@pytest.fixture(
    params=[
        (service.enabled, "service._enable"),
        (service.disabled, "service._disable"),
    ]
)
def test_funcs(request):
    pub_func, patch_name = request.param
    with patch("salt.states." + patch_name, autospec=True) as fake_func:
        yield fake_func, pub_func


@pytest.mark.parametrize("skip", [True, False])
def test_skip_verify_should_be_passed_on_to_private_functions(test_funcs, skip):
    priv_func, pub_func = test_funcs
    pub_func(name="fnord", skip_verify=skip)

    priv_func.assert_called_with("fnord", None, skip_verify=skip)
