import salt.utils.vmware as vmware
from tests.support.mock import MagicMock, call, patch


def test_when_getting_mor_by_moid_if_nothing_in_view_then_None_should_be_result():
    with patch("salt.utils.vmware.get_inventory", autospec=True) as fake_gi:
        fake_gi.return_value.inventory.viewManager.CreateContainerView.view = []
        actual_result = vmware.get_mor_by_moid(
            si="fake si", obj_type="fake_obj_type", obj_moid="fnord"
        )

        assert actual_result is None


def test_when_getting_mor_by_moid_if_no_matches_in_view_then_None_should_be_result():
    fake_view = [
        MagicMock(_moId=42),
        MagicMock(_moId=99),
    ]
    absent_moid = "fnord"  # Does not belong to anything in the fake view
    fake_container = MagicMock(view=fake_view)
    with patch("salt.utils.vmware.get_inventory", autospec=True) as fake_gi:
        fake_gi.return_value.viewManager.CreateContainerView.return_value = (
            fake_container
        )

        actual_result = vmware.get_mor_by_moid(
            si="fake si", obj_type="fake_obj_type", obj_moid=absent_moid
        )

        assert actual_result is None


def test_when_getting_mor_by_moid_the_first_item_that_matches_should_be_returned():
    expected_result = MagicMock(_moId=42)
    view_with_duplicate_ids = [
        expected_result,
        MagicMock(_moId=99),
        MagicMock(_moId=expected_result._moId),
    ]
    fake_container = MagicMock(view=view_with_duplicate_ids)
    with patch("salt.utils.vmware.get_inventory", autospec=True) as fake_gi:
        fake_gi.return_value.viewManager.CreateContainerView.return_value = (
            fake_container
        )

        actual_result = vmware.get_mor_by_moid(
            si="fake si", obj_type="fake_obj_type", obj_moid=expected_result._moId
        )

        assert actual_result is expected_result


def test_correct_args_should_be_passed_to_CreateContainerView():
    expected_obj_type = "some obj type"
    fake_container = MagicMock(view=[])
    with patch("salt.utils.vmware.get_inventory", autospec=True) as fake_gi:
        fake_gi.return_value.viewManager.CreateContainerView.return_value = (
            fake_container
        )
        fake_gi.return_value.rootFolder = "fnordy folder"
        expected_mock_call = call(
            fake_gi.return_value.rootFolder, [expected_obj_type], True
        )

        vmware.get_mor_by_moid(
            si="fake si", obj_type=expected_obj_type, obj_moid="fnord"
        )

        fake_gi.return_value.viewManager.CreateContainerView.assert_has_calls(
            [expected_mock_call]
        )
