import pytest
import salt.modules.mount
import salt.states.mount as mount
from tests.support.mock import call, create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {
        mount: {
            "__opts__": {"test": False},
            "__salt__": {
                "mount.set_fstab": create_autospec(salt.modules.mount.set_fstab),
                "mount.set_vfstab": create_autospec(
                    salt.modules.mount.set_vfstab, return_value="new"
                ),
                "mount.vfstab": create_autospec(salt.modules.mount.vfstab),
                "mount.active": create_autospec(salt.modules.mount.active),
                "mount.mount": create_autospec(salt.modules.mount.mount),
                "mount.write_mount_cache": create_autospec(
                    salt.modules.mount.write_mount_cache
                ),
            },
        }
    }


def test_when_os_is_solaris_and_opts_is_defaults_then_opts_should_be_replaced_with_hyphen():
    expected_opts = ["-"]
    expected_name = "fnord"
    expected_device = "fnordevice"
    expected_fstype = "fnordfs"
    expected_config = {"some": "config"}
    expected_match_on = "diamond"
    expected_calls = [
        call(
            expected_name,
            expected_device,
            expected_fstype,
            expected_opts,
            config=expected_config,
            match_on=expected_match_on,
        )
    ]

    with patch.dict(mount.__grains__, {"os": "Solaris"}), patch.dict(
        mount.__salt__,
        {"mount.active": create_autospec(salt.modules.mount.active, return_value=[])},
    ):
        mount.mounted(
            opts="defaults",  # This arg must be "defaults"
            name=expected_name,
            device=expected_device,
            fstype=expected_fstype,
            config=expected_config,
            match_on=expected_match_on,
        )

    mount.__salt__["mount.set_vfstab"].assert_has_calls(expected_calls)
    mount.__salt__["mount.set_fstab"].assert_not_called()


def test_when_os_is_not_solaris_and_opts_is_defaults_then_opts_should_be_defaults():
    expected_opts = ["defaults"]
    expected_name = "fnord"
    expected_device = "fnordevice"
    expected_fstype = "fnordfs"
    expected_dump = "tada"
    expected_pass_num = 13
    expected_config = {"some": "config"}
    expected_match_on = "diamond"

    with patch.dict(mount.__grains__, {"os": "Blarp"}), patch.dict(
        mount.__salt__,
        {"mount.active": create_autospec(salt.modules.mount.active, return_value=[])},
    ):
        mount.mounted(
            opts="defaults",  # This arg must be "defaults"
            name=expected_name,
            device=expected_device,
            fstype=expected_fstype,
            dump=expected_dump,
            pass_num=expected_pass_num,
            config=expected_config,
            match_on=expected_match_on,
        )

    mount.__salt__["mount.set_fstab"].assert_called_with(
        expected_name,
        expected_device,
        expected_fstype,
        expected_opts,
        expected_dump,
        expected_pass_num,
        expected_config,
        match_on=expected_match_on,
    )


def test_if_test_mode_and_solaris_in_os_grains_then_set_vfstab_should_be_used():

    with patch.dict(mount.__grains__, {"os": "Fun Solaris"}), patch.dict(
        mount.__salt__,
        {
            "mount.active": create_autospec(
                salt.modules.mount.active, return_value={"/foo/blarp": {}}
            )
        },
    ), patch.dict(mount.__opts__, {"test": True}), patch(
        "os.path.realpath", autospec=True, return_value="/foo/blarp"
    ):
        ret = mount.mounted(name="blarp", device="fnord", fstype="fnordfs", mount=False)

    mount.__salt__["mount.set_vfstab"].assert_called_with(
        "blarp",
        "fnord",
        "fnordfs",
        ["-"],
        config="/etc/fstab",
        match_on="auto",
        test=True,
    )
    assert ret["result"] is None
    assert (
        ret["comment"]
        == "blarp needs to be written to the fstab in order to be made persistent."
    )


def test_unmounted_with_persist_on_solaris_should_use_vfstab_if_config_is_fstab():
    with patch.dict(mount.__grains__, {"os": "Solaris"}):
        mount.unmounted(name="fnord", persist=True)

    mount.__salt__["mount.vfstab"].assert_called_with("/etc/vfstab")


def test_unmounted_with_persist_on_solaris_should_correctly_try_to_remove_mount_if_exits():
    mount_name = "fnord"
    device = None
    expected_ret = {
        "changes": {"persist": "purged"},
        "comment": "Target was already unmounted. Removed target from fstab",
        "name": mount_name,
        "result": True,
    }
    with patch.dict(mount.__grains__, {"os": "Solaris"}), patch.dict(
        mount.__salt__,
        {
            "mount.vfstab": create_autospec(
                salt.modules.mount.vfstab, return_value={mount_name: {}}
            ),
            "mount.rm_vfstab": create_autospec(
                salt.modules.mount.rm_vfstab, return_value=True
            ),
        },
    ):
        ret = mount.unmounted(name=mount_name, device=device, persist=True)

        mount.__salt__["mount.rm_vfstab"].assert_called_with(
            mount_name, device, "/etc/vfstab"
        )
        assert ret == expected_ret
