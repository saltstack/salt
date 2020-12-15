import pytest
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
    fake_inventory.return_value.rootFolder = "fnordy folder"
    expected_mock_call = call(
        fake_inventory.return_value.rootFolder, [expected_obj_type], True
    )

    vmware.get_mor_by_moid(si="fake si", obj_type=expected_obj_type, obj_moid="fnord")

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
    fake_inventory.return_value.rootFolder = "fnordy folder"
    expected_mock_call = call(
        fake_inventory.return_value.rootFolder, [expected_obj_type], True
    )

    vmware.get_mor_by_name(si="fake si", obj_type=expected_obj_type, obj_name="fnord")

    fake_inventory.return_value.viewManager.CreateContainerView.assert_has_calls(
        [expected_mock_call]
    )
