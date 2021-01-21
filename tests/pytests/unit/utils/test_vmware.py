import pytest
import salt.exceptions
import salt.utils.vmware as vmware
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def empty_inventory():
    with patch("salt.utils.vmware.get_inventory", autospec=True) as fake_gi:
        fake_gi.return_value.inventory.viewManager.CreateContainerView.view = []
        yield


@pytest.fixture
def patched_inventory():
    # It is important that the name and _moId have a duplicate entry in
    # this fake view. It's not necessary that one later one is identical
    # to the first element, but the first element is the one that will
    # be the expected value in all of the tests.
    dupe_id = 42
    dupe_name = "roscivs"
    fake_view = [
        MagicMock(_moId=dupe_id, name=dupe_name),
        MagicMock(_moId=99, name=dupe_name),
        MagicMock(_moId=dupe_id, name="fnord"),
    ]
    fake_container = MagicMock(view=fake_view)
    with patch("salt.utils.vmware.get_inventory", autospec=True) as fake_gi:
        fake_gi.return_value.viewManager.CreateContainerView.return_value = (
            fake_container
        )
        yield fake_gi, fake_view


def test_when_getting_mor_by_moid_if_nothing_in_view_then_None_should_be_result(
    empty_inventory,
):
    actual_result = vmware.get_mor_by_moid(
        si="fake si", obj_type="fake_obj_type", obj_moid="fnord"
    )

    assert actual_result is None


def test_when_getting_mor_by_moid_if_no_matches_in_view_then_None_should_be_result(
    patched_inventory,
):
    absent_moid = "fnord"  # Does not belong to anything in the fake view

    actual_result = vmware.get_mor_by_moid(
        si="fake si", obj_type="fake_obj_type", obj_moid=absent_moid
    )

    assert actual_result is None


def test_when_getting_mor_by_moid_the_first_item_that_matches_should_be_returned(
    patched_inventory,
):
    _, fake_view = patched_inventory
    expected_result = fake_view[0]

    actual_result = vmware.get_mor_by_moid(
        si="fake si", obj_type="fake_obj_type", obj_moid=expected_result._moId
    )

    assert actual_result is expected_result


def test_correct_args_should_be_passed_to_CreateContainerView_from_by_moid(
    patched_inventory,
):
    fake_inventory = patched_inventory[0]
    expected_obj_type = "some obj type"
    expected_si = "this is not a real si"
    fake_inventory.return_value.rootFolder = "fnordy folder"
    expected_mock_call = call(
        fake_inventory.return_value.rootFolder, [expected_obj_type], True
    )

    vmware.get_mor_by_moid(si=expected_si, obj_type=expected_obj_type, obj_moid="fnord")

    fake_inventory.assert_has_calls([call(expected_si)])
    fake_inventory.return_value.viewManager.CreateContainerView.assert_has_calls(
        [expected_mock_call]
    )


def test_when_getting_mor_by_name_if_nothing_in_view_then_None_should_be_result(
    empty_inventory,
):
    actual_result = vmware.get_mor_by_name(
        si="fake si", obj_type="fake_obj_type", obj_name="fnord"
    )

    assert actual_result is None


def test_when_getting_mor_by_name_if_no_matches_in_view_then_None_should_be_result(
    patched_inventory,
):
    absent_name = "fnord"  # Does not belong to anything in the fake view

    actual_result = vmware.get_mor_by_name(
        si="fake si", obj_type="fake_obj_type", obj_name=absent_name
    )

    assert actual_result is None


def test_when_getting_mor_by_name_the_first_item_that_matches_should_be_returned(
    patched_inventory,
):
    _, fake_view = patched_inventory
    expected_result = fake_view[0]

    actual_result = vmware.get_mor_by_name(
        si="fake si", obj_type="fake_obj_type", obj_name=expected_result.name
    )

    assert actual_result is expected_result


def test_correct_args_should_be_passed_to_CreateContainerView_from_by_name(
    patched_inventory,
):
    fake_inventory = patched_inventory[0]
    expected_obj_type = "some obj type"
    expected_si = "this is some other fake si"
    fake_inventory.return_value.rootFolder = "fnordy folder"
    expected_mock_call = call(
        fake_inventory.return_value.rootFolder, [expected_obj_type], True
    )

    vmware.get_mor_by_name(si=expected_si, obj_type=expected_obj_type, obj_name="fnord")

    fake_inventory.assert_has_calls([call(expected_si)])
    fake_inventory.return_value.viewManager.CreateContainerView.assert_has_calls(
        [expected_mock_call]
    )


def test_when_no_datastore_matches_by_name_VMwareObjectRetrievalError_should_be_raised():
    datastore = "whatever"
    expected_message = "Datastore '{}' does not exist.".format(datastore)
    patch_get_mor = patch(
        "salt.utils.vmware.get_mor_by_name", autospec=True, return_value=None
    )
    with patch_get_mor, pytest.raises(salt.exceptions.VMwareObjectRetrievalError) as e:
        vmware.list_datastore_full(service_instance="blarp", datastore=datastore)

    assert e.value.args[0] == expected_message


def test_when_no_host_exists_items_should_be_correctly_returned_from_datastore_object():
    expected_items = {
        "name": "roscivs",
        "type": "bottia",
        "url": "of sandwich",
        "capacity": 42,
        "free": 13,
        "used": 42 - 13,  # capacity-free
        "usage": (29 / 42) * 100,  # (used / capacity) * 100
        "hosts": [],
    }
    gigabytes = 1024 * 1024
    fake_do = MagicMock()
    fake_do.summary.name = expected_items["name"]
    fake_do.summary.type = expected_items["type"]
    fake_do.summary.url = expected_items["url"]
    fake_do.summary.capacity = expected_items["capacity"] * gigabytes
    fake_do.summary.freeSpace = expected_items["free"] * gigabytes
    fake_do.summary.host = []

    with patch(
        "salt.utils.vmware.get_mor_by_name", autospec=True, return_value=fake_do
    ):
        actual_items = vmware.list_datastore_full(
            service_instance="fnord", datastore="also fnord"
        )

    assert actual_items == expected_items


def test_text_values_should_have_single_quotes_removed():
    expected_name = "roscivs"
    expected_type = "bottia"
    expected_url = "of sandwich"
    fake_do = MagicMock()
    fake_do.summary.name = "'''''{}''".format(expected_name)
    fake_do.summary.type = "'''{}''''''''''".format(expected_type)
    fake_do.summary.url = "{}''''''''''".format(expected_url)
    fake_do.summary.capacity = 42
    fake_do.summary.freeSpace = 13
    fake_do.summary.host = []

    with patch(
        "salt.utils.vmware.get_mor_by_name", autospec=True, return_value=fake_do
    ):
        actual_items = vmware.list_datastore_full(
            service_instance="fnord", datastore="also fnord"
        )

    assert actual_items["name"] == expected_name
    assert actual_items["type"] == expected_type
    assert actual_items["url"] == expected_url


def test_host_keys_are_correctly_processed_before_searching_by_moid():
    expected_keys = [
        "quoty mcquoteface",
        "sir quotesalot",
        "all the quotes",
        "sans quotes:but:more:colons",
    ]
    fake_do = MagicMock()
    fake_do.summary.name = "fnord"
    fake_do.summary.type = "fnord"
    fake_do.summary.url = "fnord"
    fake_do.summary.capacity = 4  # IEEE random number
    fake_do.summary.freeSpace = 4
    fake_do.host = [
        MagicMock(key="''''something fnordy:{}".format(expected_keys[0])),
        MagicMock(key="'''':{}'''''".format(expected_keys[1])),
        MagicMock(key="'''''''''''':{}'''''''''''".format(expected_keys[2])),
        MagicMock(key="ignore me:{}".format(expected_keys[3])),
    ]

    patch_by_name = patch(
        "salt.utils.vmware.get_mor_by_name", autospec=True, return_value=fake_do
    )
    patch_by_moid = patch("salt.utils.vmware.get_mor_by_moid", autospec=True)

    with patch_by_name, patch_by_moid as fake_moid:
        vmware.list_datastore_full(service_instance="fnord", datastore="also fnord")

        fake_moid.assert_has_calls(
            [
                call("fnord", vmware.vim.HostSystem, expected_keys[0]),
                call("fnord", vmware.vim.HostSystem, expected_keys[1]),
                call("fnord", vmware.vim.HostSystem, expected_keys[2]),
                call("fnord", vmware.vim.HostSystem, expected_keys[3]),
            ]
        )


def test_host_names_should_be_correctly_returned():
    expected_hosts = ["hosty mchostface", "roscivs bottia", "whatever", "cool times"]
    fake_do = MagicMock()
    fake_do.summary.name = "fnord"
    fake_do.summary.type = "fnord"
    fake_do.summary.url = "fnord"
    fake_do.summary.capacity = 4  # IEEE random number
    fake_do.summary.freeSpace = 4
    fake_do.host = [
        MagicMock(key="fnord:fnord"),
        MagicMock(key="fnord:fnord:fnord"),
        MagicMock(key="fnord:fnord:fnord:fnord"),
        MagicMock(key="fnord:fnord:fnord:fnord"),
    ]
    fake_hosts = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    fake_hosts[0].name = expected_hosts[0]
    fake_hosts[1].name = expected_hosts[1]
    fake_hosts[2].name = expected_hosts[2]
    fake_hosts[3].name = expected_hosts[3]

    patch_by_name = patch(
        "salt.utils.vmware.get_mor_by_name", autospec=True, return_value=fake_do
    )
    m1 = MagicMock()
    m1.name = expected_hosts[0]
    patch_by_moid = patch(
        "salt.utils.vmware.get_mor_by_moid", autospec=True, side_effect=fake_hosts
    )

    with patch_by_name, patch_by_moid as fake_moid:
        actual_items = vmware.list_datastore_full(
            service_instance="fnord", datastore="also fnord"
        )

        assert actual_items["hosts"] == expected_hosts


def test_when_no_datastores_are_found_then_list_datastores_full_should_be_empty_dict():
    expected_datastores = {}
    with patch("salt.utils.vmware.list_objects", return_value=[]):
        actual_datastores = vmware.list_datastores_full("fnord")

        assert actual_datastores == expected_datastores


def test_when_datastores_are_found_then_list_datastore_full_should_get_correct_args():
    expected_server_instance = "fnord"
    expected_datastores = ["different fnord", "more different fnord"]
    expected_calls = [
        call(expected_server_instance, expected_datastores[0]),
        call(expected_server_instance, expected_datastores[1]),
    ]
    patch_list_obj = patch(
        "salt.utils.vmware.list_objects", return_value=expected_datastores
    )
    patch_list_datastore = patch("salt.utils.vmware.list_datastore_full")
    with patch_list_obj, patch_list_datastore as fake_list_dsf:
        vmware.list_datastores_full(expected_server_instance)

        fake_list_dsf.assert_has_calls(expected_calls)


def test_when_datastores_are_found_then_list__datastores_full_should_return_all_the_datastores_from_list_datastore_full():
    datastore_names = ["different fnord", "more different fnord"]
    datastores = [
        "this is a fnord datastore",
        "this is a more different fnord datastore",
    ]
    expected_datastores = {
        "different fnord": "this is a fnord datastore",
        "more different fnord": "this is a more different fnord datastore",
    }
    patch_list_obj = patch(
        "salt.utils.vmware.list_objects", return_value=datastore_names,
    )
    patch_list_datastore = patch(
        "salt.utils.vmware.list_datastore_full", side_effect=datastores
    )
    with patch_list_obj, patch_list_datastore:
        actual_datastores = vmware.list_datastores_full("some server instance")

    assert actual_datastores == expected_datastores
