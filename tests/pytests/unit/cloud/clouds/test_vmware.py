import pytest
import salt.cloud.clouds.vmware as vmware
from salt.exceptions import SaltCloudSystemExit
from tests.support.mock import call, patch


def test_list_datastores_full_should_raise_SaltCloudSystemExit_if_call_is_not_function():
    expected_message = (
        "The list_datastores_full function must be called with -f or --function."
    )
    with pytest.raises(SaltCloudSystemExit) as err:
        # This can be anything except "function"
        vmware.list_datastores_full(call="not function")
    actual_message = err.value.message

    assert actual_message == expected_message


def test_list_datastores_full_should_call_utils_with_service_instance():
    expected_si = object()
    expected_calls = [call(expected_si)]
    with patch("salt.cloud.clouds.vmware._get_si", return_value=expected_si), patch(
        "salt.utils.vmware.list_datastores_full"
    ) as fake_dsf:
        vmware.list_datastores_full(call="function")
        fake_dsf.assert_has_calls(expected_calls)


def test_list_datastores_full_should_return_datastores_output_in_dict():
    expected_datastores = [
        "whatever",
        "this is not really a datastore",
        "but that is not important for this test",
    ]
    expected_result = {"Datastores": expected_datastores}

    with patch("salt.cloud.clouds.vmware._get_si", return_value="fnord"), patch(
        "salt.utils.vmware.list_datastores_full", return_value=expected_datastores
    ):
        actual_result = vmware.list_datastores_full(call="function")

    assert actual_result == expected_result


def test_list_datastore_full_should_raise_SaltCloudSystemExit_if_call_is_not_function():
    expected_message = (
        "The list_datastore_full function must be called with -f or --function."
    )
    with pytest.raises(SaltCloudSystemExit) as err:
        # This can be anything except "function"
        vmware.list_datastore_full(call="not function")
    actual_message = err.value.message

    assert actual_message == expected_message


def test_list_datastore_full_should_raise_SaltCloudSystemExit_if_datastore_is_not():
    expected_message = "The list_datastore_full function requires a datastore."
    with pytest.raises(SaltCloudSystemExit) as err:
        # This can be anything except "function"
        vmware.list_datastore_full(
            call="function", datastore=None, kwargs={"datastore": None}
        )
    actual_message = err.value.message

    assert actual_message == expected_message


def test_list_datastore_full_should_override_provided_datastore_with_kwargs_datastore():
    unexpected_datastore = "fnord datastore"
    expected_datastore = "kwargs datastore"
    expected_si = "some service instance"
    expected_calls = [call(expected_si, expected_datastore)]
    with patch("salt.cloud.clouds.vmware._get_si", return_value=expected_si), patch(
        "salt.utils.vmware.list_datastore_full"
    ) as fake_dsf:
        vmware.list_datastore_full(
            call="function",
            datastore=unexpected_datastore,
            kwargs={"datastore": expected_datastore},
        )

    fake_dsf.assert_has_calls(expected_calls)


@pytest.mark.parametrize("kwargs", [{}, {"datastore": None}, None])
def test_list_datastore_full_should_use_provided_datastore_if_kwargs_are_provided_without_datastore(
    kwargs,
):
    expected_datastore = "regular datastore"
    expected_si = "some service instance"
    expected_calls = [call(expected_si, expected_datastore)]
    with patch("salt.cloud.clouds.vmware._get_si", return_value=expected_si), patch(
        "salt.utils.vmware.list_datastore_full"
    ) as fake_dsf:
        vmware.list_datastore_full(
            call="function", datastore=expected_datastore, kwargs=kwargs
        )

    fake_dsf.assert_has_calls(expected_calls)


@pytest.mark.parametrize(
    "expected_datastore_name,expected_datastore",
    [("fnord", "blarp"), ("bob", "tennis ball"), ("roscivs", "bottia")],
)
def test_list_datastore_full_should_return_utils_result_in_dict_with_datastore_name(
    expected_datastore_name, expected_datastore
):
    expected_result = {expected_datastore_name: expected_datastore}
    with patch("salt.cloud.clouds.vmware._get_si"), patch(
        "salt.utils.vmware.list_datastore_full", return_value=expected_datastore
    ) as fake_dsf:
        actual_result = vmware.list_datastore_full(
            call="function", datastore=expected_datastore_name
        )
    assert actual_result == expected_result
