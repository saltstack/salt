"""
    :codeauthor: `Nitin Madhok <nmadhok@g.clemson.edu>`

    tests.unit.cloud.clouds.vmware_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import pytest

from salt import config
from salt.cloud.clouds import vmware
from salt.exceptions import SaltCloudSystemExit
from tests.support.mock import MagicMock, Mock, patch

# Attempt to import pyVim and pyVmomi libs
HAS_LIBS = True
# pylint: disable=import-error,no-name-in-module,unused-import
try:
    from pyVim.connect import Disconnect, SmartConnect
    from pyVmomi import vim, vmodl
except ImportError:
    HAS_LIBS = False
# pylint: enable=import-error,no-name-in-module,unused-import


pytestmark = [
    pytest.mark.skipif(
        not HAS_LIBS, reason="Install pyVmomi to be able to run this test."
    )
]


@pytest.fixture
def vm_name():
    return "test-vm"


@pytest.fixture
def profile():
    return {
        "base-gold": {
            "provider": "vcenter01:vmware",
            "datastore": "Datastore1",
            "resourcepool": "Resources",
            "folder": "vm",
        }
    }


@pytest.fixture
def configure_loader_modules(profile):
    return {
        vmware: {
            "__active_provider_name__": "",
            "__opts__": {
                "providers": {
                    "vcenter01": {
                        "vmware": {
                            "driver": "vmware",
                            "url": "vcenter01.domain.com",
                            "user": "DOMAIN\\user",
                            "password": "verybadpass",
                            "profiles": profile,
                        }
                    }
                }
            },
        }
    }


def test_test_vcenter_connection_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call test_vcenter_connection
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.test_vcenter_connection, call="action")


def test_get_vcenter_version_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call get_vcenter_version
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.get_vcenter_version, call="action")


def test_avail_images_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call avail_images
    with --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.avail_images, call="action")


def test_avail_locations_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call avail_locations
    with --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.avail_locations, call="action")


def test_avail_sizes_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call avail_sizes
    with --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.avail_sizes, call="action")


def test_list_datacenters_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_datacenters
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_datacenters, call="action")


def test_list_clusters_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_clusters
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_clusters, call="action")


def test_list_datastore_clusters_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_datastore_clusters
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_datastore_clusters, call="action")


def test_list_datastores_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_datastores
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_datastores, call="action")


def test_list_hosts_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_hosts
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_hosts, call="action")


def test_list_resourcepools_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_resourcepools
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_resourcepools, call="action")


def test_list_networks_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_networks
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_networks, call="action")


def test_list_nodes_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_nodes
    with --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_nodes, call="action")


def test_list_nodes_min_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_min
    with --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_nodes_min, call="action")


def test_list_nodes_full_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
    with --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_nodes_full, call="action")


def test_list_nodes_select_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_nodes_full
    with --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_nodes_select, call="action")


def test_list_folders_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_folders
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_folders, call="action")


def test_list_snapshots_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_snapshots
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_snapshots, call="action")


def test_list_hosts_by_cluster_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_hosts_by_cluster
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_hosts_by_cluster, call="action")


def test_list_clusters_by_datacenter_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_clusters_by_datacenter
    with anything other than --function or -f.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.list_clusters_by_datacenter, call="action"
    )


def test_list_hosts_by_datacenter_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_hosts_by_datacenter
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_hosts_by_datacenter, call="action")


def test_list_hbas_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_hbas
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_hbas, call="action")


def test_list_dvs_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_dvs
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_dvs, call="action")


def test_list_vapps_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_vapps
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_vapps, call="action")


def test_list_templates_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_templates
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.list_templates, call="action")


def test_create_datacenter_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call create_datacenter
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.create_datacenter, call="action")


def test_create_cluster_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call create_cluster
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.create_cluster, call="action")


def test_rescan_hba_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call rescan_hba
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.rescan_hba, call="action")


def test_upgrade_tools_all_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call upgrade_tools_all
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.upgrade_tools_all, call="action")


def test_enter_maintenance_mode_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call enter_maintenance_mode
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.enter_maintenance_mode, call="action")


def test_exit_maintenance_mode_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call exit_maintenance_mode
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.exit_maintenance_mode, call="action")


def test_create_folder_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call create_folder
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.create_folder, call="action")


def test_add_host_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call add_host
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.add_host, call="action")


def test_remove_host_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call remove_host
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.remove_host, call="action")


def test_connect_host_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call connect_host
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.connect_host, call="action")


def test_disconnect_host_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call disconnect_host
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.disconnect_host, call="action")


def test_reboot_host_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call reboot_host
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.reboot_host, call="action")


def test_create_datastore_cluster_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call create_datastore_cluster
    with anything other than --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.create_datastore_cluster, call="action")


def test_show_instance_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call show_instance
    with anything other than --action or -a.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.show_instance, name=vm_name, call="function"
    )


def test_start_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call start
    with anything other than --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.start, name=vm_name, call="function")


def test_stop_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call stop
    with anything other than --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.stop, name=vm_name, call="function")


def test_suspend_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call suspend
    with anything other than --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.suspend, name=vm_name, call="function")


def test_reset_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call reset
    with anything other than --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.reset, name=vm_name, call="function")


def test_terminate_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call terminate
    with anything other than --action or -a.
    """
    pytest.raises(SaltCloudSystemExit, vmware.terminate, name=vm_name, call="function")


def test_destroy_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call destroy
    with --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, vmware.destroy, name=vm_name, call="function")


def test_shutdown_host_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call convert_to_template
    with anything other than --action or -a.
    """
    with patch.object(vmware, "_get_si", Mock()), patch(
        "salt.utils.vmware.get_mor_by_property", Mock()
    ):
        pytest.raises(
            SaltCloudSystemExit,
            vmware.shutdown_host,
            kwargs={"host": vm_name},
            call="action",
        )


def test_upgrade_tools_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call upgrade_tools
    with anything other than --action or -a.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.upgrade_tools, name=vm_name, call="function"
    )


def test_create_snapshot_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call create_snapshot
    with anything other than --action or -a.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.create_snapshot, name=vm_name, call="function"
    )


def test_revert_to_snapshot_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call revert_to_snapshot
    with anything other than --action or -a.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.revert_to_snapshot,
        name=vm_name,
        call="function",
    )


def test_remove_snapshot_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call remove_snapshot
    with anything other than --action or -a.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.remove_snapshot,
        name=vm_name,
        kwargs={"snapshot_name": "mySnapshot"},
        call="function",
    )


def test_remove_snapshot_call_no_snapshot_name_in_kwargs(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when name is not present in kwargs.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.remove_snapshot, name=vm_name, call="action"
    )


def test_remove_all_snapshots_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call remove_all_snapshots
    with anything other than --action or -a.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.remove_all_snapshots,
        name=vm_name,
        call="function",
    )


def test_convert_to_template_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call convert_to_template
    with anything other than --action or -a.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.convert_to_template,
        name=vm_name,
        call="function",
    )


def test_avail_sizes():
    """
    Tests that avail_sizes returns an empty dictionary.
    """
    assert vmware.avail_sizes(call="foo") == {}


def test_create_datacenter_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    create_datacenter.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.create_datacenter, kwargs=None, call="function"
    )


def test_create_datacenter_no_name_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when name is not present in
    kwargs that are provided to create_datacenter.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_datacenter,
        kwargs={"foo": "bar"},
        call="function",
    )


def test_create_datacenter_name_too_short():
    """
    Tests that a SaltCloudSystemExit is raised when name is present in kwargs
    that are provided to create_datacenter but is an empty string.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_datacenter,
        kwargs={"name": ""},
        call="function",
    )


def test_create_datacenter_name_too_long():
    """
    Tests that a SaltCloudSystemExit is raised when name is present in kwargs
    that are provided to create_datacenter but is a string with length <= 80.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_datacenter,
        kwargs={
            "name": "cCD2GgJGPG1DUnPeFBoPeqtdmUxIWxDoVFbA14vIG0BPoUECkgbRMnnY6gaUPBvIDCcsZ5HU48ubgQu5c"
        },
        call="function",
    )


def test_create_cluster_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    create_cluster.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.create_cluster, kwargs=None, call="function"
    )


def test_create_cluster_no_name_no_datacenter_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when neither the name nor the
    datacenter is present in kwargs that are provided to create_cluster.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_cluster,
        kwargs={"foo": "bar"},
        call="function",
    )


def test_create_cluster_no_datacenter_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when the name is present but the
    datacenter is not present in kwargs that are provided to create_cluster.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_cluster,
        kwargs={"name": "my-cluster"},
        call="function",
    )


def test_create_cluster_no_name_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when the datacenter is present
    but the name is not present in kwargs that are provided to create_cluster.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_cluster,
        kwargs={"datacenter": "my-datacenter"},
        call="function",
    )


def test_rescan_hba_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    rescan_hba.
    """
    pytest.raises(SaltCloudSystemExit, vmware.rescan_hba, kwargs=None, call="function")


def test_rescan_hba_no_host_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when host is not present in
    kwargs that are provided to rescan_hba.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.rescan_hba,
        kwargs={"foo": "bar"},
        call="function",
    )


def test_create_snapshot_no_kwargs(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    create_snapshot.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_snapshot,
        name=vm_name,
        kwargs=None,
        call="action",
    )


def test_create_snapshot_no_snapshot_name_in_kwargs(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when snapshot_name is not present
    in kwargs that are provided to create_snapshot.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_snapshot,
        name=vm_name,
        kwargs={"foo": "bar"},
        call="action",
    )


def test_add_host_no_esxi_host_user_in_config():
    """
    Tests that a SaltCloudSystemExit is raised when esxi_host_user is not
    specified in the cloud provider configuration when calling add_host.
    """
    with pytest.raises(
        SaltCloudSystemExit,
        match="You must specify the ESXi host username in your providers config.",
    ):
        vmware.add_host(kwargs=None, call="function")


def test_add_host_no_esxi_host_password_in_config():
    """
    Tests that a SaltCloudSystemExit is raised when esxi_host_password is not
    specified in the cloud provider configuration when calling add_host.
    """
    with patch.dict(
        vmware.__opts__["providers"]["vcenter01"]["vmware"],
        {"esxi_host_user": "root"},
        clean=True,
    ):
        with pytest.raises(
            SaltCloudSystemExit,
            match="You must specify the ESXi host password in your providers config.",
        ):
            vmware.add_host(kwargs=None, call="function")


def test_no_clonefrom_just_image(profile):
    """
    Tests that the profile is configured correctly when deploying using an image
    """

    profile_additions = {"image": "some-image.iso"}
    vm_ = {"profile": profile}
    with patch.dict(
        vmware.__opts__["providers"]["vcenter01"]["vmware"]["profiles"]["base-gold"],
        profile_additions,
        clean=True,
    ):
        assert (
            config.is_profile_configured(
                vmware.__opts__, "vcenter01:vmware", "base-gold", vm_=vm_
            )
            is True
        )


def test_just_clonefrom(profile):
    """
    Tests that the profile is configured correctly when deploying by cloning from a template
    """

    profile_additions = {
        "clonefrom": "test-template",
        "image": "should ignore image",
    }
    vm_ = {"profile": profile}
    with patch.dict(
        vmware.__opts__["providers"]["vcenter01"]["vmware"]["profiles"]["base-gold"],
        profile_additions,
        clean=True,
    ):
        assert (
            config.is_profile_configured(
                vmware.__opts__, "vcenter01:vmware", "base-gold", vm_=vm_
            )
            is True
        )


def test_just_Instantclonefrom(vm_name):
    """
    Tests that the profile is configured correctly when deploying by instant cloning from a running VM
    """

    profile_additions = {
        "clonefrom": vm_name,
        "instant_clone": True,
    }
    vm_ = {"profile": profile}
    with patch.dict(
        vmware.__opts__["providers"]["vcenter01"]["vmware"]["profiles"]["base-gold"],
        profile_additions,
        clean=True,
    ):
        assert (
            config.is_profile_configured(
                vmware.__opts__, "vcenter01:vmware", "base-gold", vm_=vm_
            )
            is True
        )


def test_add_new_ide_controller_helper():
    """
    Tests that creating a new controller, ensuring that it will generate a controller key
    if one is not provided
    """
    with patch("salt.cloud.clouds.vmware.randint", return_value=101) as randint_mock:
        controller_label = "Some label"
        bus_number = 1
        spec = vmware._add_new_ide_controller_helper(controller_label, None, bus_number)
        assert spec.device.key == randint_mock.return_value

        spec = vmware._add_new_ide_controller_helper(controller_label, 200, bus_number)
        assert spec.device.key == 200

        assert spec.device.busNumber == bus_number
        assert spec.device.deviceInfo.label == controller_label
        assert spec.device.deviceInfo.summary == controller_label


def test_manage_devices_just_cd():
    """
    Tests that when adding IDE/CD drives, controller keys will be in the apparent
    safe-range on ESX 5.5 but randomly generated on other versions (i.e. 6)
    """
    device_map = {
        "ide": {"IDE 0": {}, "IDE 1": {}},
        "cd": {"CD/DVD Drive 1": {"controller": "IDE 0"}},
    }
    with patch(
        "salt.cloud.clouds.vmware.get_vcenter_version",
        return_value="VMware ESXi 5.5.0",
    ):
        specs = vmware._manage_devices(device_map, vm=None)["device_specs"]

        assert specs[0].device.key == vmware.SAFE_ESX_5_5_CONTROLLER_KEY_INDEX
        assert specs[1].device.key == vmware.SAFE_ESX_5_5_CONTROLLER_KEY_INDEX + 1
        assert specs[2].device.controllerKey == vmware.SAFE_ESX_5_5_CONTROLLER_KEY_INDEX

    with patch(
        "salt.cloud.clouds.vmware.get_vcenter_version", return_value="VMware ESXi 6"
    ):
        with patch("salt.cloud.clouds.vmware.randint", return_value=100) as first_key:
            specs = vmware._manage_devices(device_map, vm=None)["device_specs"]

            assert specs[0].device.key == first_key.return_value
            assert specs[2].device.controllerKey == first_key.return_value


def test_add_host_no_host_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when host is not present in
    kwargs that are provided to add_host.
    """
    provider_config_additions = {
        "esxi_host_user": "root",
        "esxi_host_password": "myhostpassword",
    }
    with patch.dict(
        vmware.__opts__["providers"]["vcenter01"]["vmware"],
        provider_config_additions,
        clean=True,
    ):
        with pytest.raises(
            SaltCloudSystemExit,
            match="You must specify either the IP or DNS name of the host system.",
        ):
            vmware.add_host(kwargs={"foo": "bar"}, call="function")


def test_add_host_both_cluster_and_datacenter_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when both cluster and datacenter
    are present in kwargs that are provided to add_host.
    """
    provider_config_additions = {
        "esxi_host_user": "root",
        "esxi_host_password": "myhostpassword",
    }
    with patch.dict(
        vmware.__opts__["providers"]["vcenter01"]["vmware"],
        provider_config_additions,
        clean=True,
    ):
        with pytest.raises(
            SaltCloudSystemExit,
            match="You must specify either the cluster name or the datacenter name.",
        ):
            vmware.add_host(
                kwargs={
                    "host": "my-esxi-host",
                    "datacenter": "my-datacenter",
                    "cluster": "my-cluster",
                },
                call="function",
            )


def test_add_host_neither_cluster_nor_datacenter_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when neither cluster nor
    datacenter is present in kwargs that are provided to add_host.
    """
    provider_config_additions = {
        "esxi_host_user": "root",
        "esxi_host_password": "myhostpassword",
    }
    with patch.dict(
        vmware.__opts__["providers"]["vcenter01"]["vmware"],
        provider_config_additions,
        clean=True,
    ):
        with pytest.raises(
            SaltCloudSystemExit,
            match="You must specify either the cluster name or the datacenter name.",
        ):
            vmware.add_host(kwargs={"host": "my-esxi-host"}, call="function")


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_add_host_cluster_not_exists():
    """
    Tests that a SaltCloudSystemExit is raised when the specified cluster present
    in kwargs that are provided to add_host does not exist in the VMware
    environment.
    """
    with patch("salt.cloud.clouds.vmware._get_si", MagicMock(return_value=None)):
        with patch(
            "salt.utils.vmware.get_mor_by_property", MagicMock(return_value=None)
        ):
            provider_config_additions = {
                "esxi_host_user": "root",
                "esxi_host_password": "myhostpassword",
            }

            with patch.dict(
                vmware.__opts__["providers"]["vcenter01"]["vmware"],
                provider_config_additions,
                clean=True,
            ):
                with pytest.raises(
                    SaltCloudSystemExit, match="Specified cluster does not exist."
                ):
                    vmware.add_host(
                        kwargs={"host": "my-esxi-host", "cluster": "my-cluster"},
                        call="function",
                    )


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_add_host_datacenter_not_exists():
    """
    Tests that a SaltCloudSystemExit is raised when the specified datacenter
    present in kwargs that are provided to add_host does not exist in the VMware
    environment.
    """
    with patch("salt.cloud.clouds.vmware._get_si", MagicMock(return_value=None)):
        with patch(
            "salt.utils.vmware.get_mor_by_property", MagicMock(return_value=None)
        ):
            provider_config_additions = {
                "esxi_host_user": "root",
                "esxi_host_password": "myhostpassword",
            }
            with patch.dict(
                vmware.__opts__["providers"]["vcenter01"]["vmware"],
                provider_config_additions,
                clean=True,
            ):
                with pytest.raises(
                    SaltCloudSystemExit, match="Specified datacenter does not exist."
                ):
                    vmware.add_host(
                        kwargs={"host": "my-esxi-host", "datacenter": "my-datacenter"},
                        call="function",
                    )


def test_remove_host_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    remove_host.
    """
    pytest.raises(SaltCloudSystemExit, vmware.remove_host, kwargs=None, call="function")


def test_remove_host_no_host_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when host is not present in
    kwargs that are provided to remove_host.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.remove_host,
        kwargs={"foo": "bar"},
        call="function",
    )


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_remove_host_not_exists():
    """
    Tests that a SaltCloudSystemExit is raised when the specified host present
    in kwargs that are provided to remove_host does not exist in the VMware
    environment.
    """
    with patch("salt.cloud.clouds.vmware._get_si", MagicMock(return_value=None)):
        with patch(
            "salt.utils.vmware.get_mor_by_property", MagicMock(return_value=None)
        ):
            pytest.raises(
                SaltCloudSystemExit,
                vmware.remove_host,
                kwargs={"host": "my-host"},
                call="function",
            )


def test_connect_host_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    connect_host.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.connect_host, kwargs=None, call="function"
    )


def test_connect_host_no_host_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when host is not present in
    kwargs that are provided to connect_host.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.connect_host,
        kwargs={"foo": "bar"},
        call="function",
    )


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_connect_host_not_exists():
    """
    Tests that a SaltCloudSystemExit is raised when the specified host present
    in kwargs that are provided to connect_host does not exist in the VMware
    environment.
    """
    with patch("salt.cloud.clouds.vmware._get_si", MagicMock(return_value=None)):
        with patch(
            "salt.utils.vmware.get_mor_by_property", MagicMock(return_value=None)
        ):
            pytest.raises(
                SaltCloudSystemExit,
                vmware.connect_host,
                kwargs={"host": "my-host"},
                call="function",
            )


def test_disconnect_host_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    disconnect_host.
    """
    pytest.raises(
        SaltCloudSystemExit, vmware.disconnect_host, kwargs=None, call="function"
    )


def test_disconnect_host_no_host_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when host is not present in
    kwargs that are provided to disconnect_host.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.disconnect_host,
        kwargs={"foo": "bar"},
        call="function",
    )


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_disconnect_host_not_exists():
    """
    Tests that a SaltCloudSystemExit is raised when the specified host present
    in kwargs that are provided to disconnect_host does not exist in the VMware
    environment.
    """
    with patch("salt.cloud.clouds.vmware._get_si", MagicMock(return_value=None)):
        with patch(
            "salt.utils.vmware.get_mor_by_property", MagicMock(return_value=None)
        ):
            pytest.raises(
                SaltCloudSystemExit,
                vmware.disconnect_host,
                kwargs={"host": "my-host"},
                call="function",
            )


def test_reboot_host_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    reboot_host.
    """
    pytest.raises(SaltCloudSystemExit, vmware.reboot_host, kwargs=None, call="function")


def test_reboot_host_no_host_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when host is not present in
    kwargs that are provided to reboot_host.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.reboot_host,
        kwargs={"foo": "bar"},
        call="function",
    )


@pytest.mark.skipif(
    HAS_LIBS is False, reason="Install pyVmomi to be able to run this unit test."
)
def test_reboot_host_not_exists():
    """
    Tests that a SaltCloudSystemExit is raised when the specified host present
    in kwargs that are provided to connect_host does not exist in the VMware
    environment.
    """
    with patch("salt.cloud.clouds.vmware._get_si", MagicMock(return_value=None)):
        with patch(
            "salt.utils.vmware.get_mor_by_property", MagicMock(return_value=None)
        ):
            pytest.raises(
                SaltCloudSystemExit,
                vmware.reboot_host,
                kwargs={"host": "my-host"},
                call="function",
            )


def test_create_datastore_cluster_no_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when no kwargs are provided to
    create_datastore_cluster.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_datastore_cluster,
        kwargs=None,
        call="function",
    )


def test_create_datastore_cluster_no_name_in_kwargs():
    """
    Tests that a SaltCloudSystemExit is raised when name is not present in
    kwargs that are provided to create_datastore_cluster.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_datastore_cluster,
        kwargs={"foo": "bar"},
        call="function",
    )


def test_create_datastore_cluster_name_too_short():
    """
    Tests that a SaltCloudSystemExit is raised when name is present in kwargs
    that are provided to create_datastore_cluster but is an empty string.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_datastore_cluster,
        kwargs={"name": ""},
        call="function",
    )


def test_create_datastore_cluster_name_too_long():
    """
    Tests that a SaltCloudSystemExit is raised when name is present in kwargs
    that are provided to create_datastore_cluster but is a string with length <= 80.
    """
    pytest.raises(
        SaltCloudSystemExit,
        vmware.create_datastore_cluster,
        kwargs={
            "name": "cCD2GgJGPG1DUnPeFBoPeqtdmUxIWxDoVFbA14vIG0BPoUECkgbRMnnY6gaUPBvIDCcsZ5HU48ubgQu5c"
        },
        call="function",
    )


def test__add_new_hard_disk_helper():
    with patch("salt.cloud.clouds.vmware._get_si", MagicMock(return_value=None)):
        with patch(
            "salt.utils.vmware.get_mor_using_container_view",
            side_effect=[None, None],
        ):
            pytest.raises(
                SaltCloudSystemExit,
                vmware._add_new_hard_disk_helper,
                disk_label="test",
                size_gb=100,
                unit_number=0,
                datastore="whatever",
            )
        with patch(
            "salt.utils.vmware.get_mor_using_container_view",
            side_effect=["Datastore", None],
        ):
            pytest.raises(
                AttributeError,
                vmware._add_new_hard_disk_helper,
                disk_label="test",
                size_gb=100,
                unit_number=0,
                datastore="whatever",
            )
            vmware.salt.utils.vmware.get_mor_using_container_view.assert_called_with(
                None, vim.Datastore, "whatever"
            )
        with patch(
            "salt.utils.vmware.get_mor_using_container_view",
            side_effect=[None, "Cluster"],
        ):
            pytest.raises(
                AttributeError,
                vmware._add_new_hard_disk_helper,
                disk_label="test",
                size_gb=100,
                unit_number=0,
                datastore="whatever",
            )
            vmware.salt.utils.vmware.get_mor_using_container_view.assert_called_with(
                None, vim.StoragePod, "whatever"
            )
