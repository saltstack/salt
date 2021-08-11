import pytest
import salt.states.virt as virt
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

from .test_helpers import domain_update_call


def test_defined_no_change(test):
    """
    defined state test, no change required case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        init_mock = MagicMock(return_value=True)
        update_mock = MagicMock(return_value={"definition": False})
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm"]),
                "virt.update": update_mock,
                "virt.init": init_mock,
            },
        ):
            assert virt.defined("myvm") == {
                "name": "myvm",
                "changes": {},
                "result": True,
                "comment": "Domain myvm unchanged",
            }
            init_mock.assert_not_called()
            assert update_mock.call_args_list == [domain_update_call("myvm", test=test)]


def test_defined_new_with_connection(test):
    """
    defined state test, new guest with connection details passed case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        init_mock = MagicMock(return_value=True)
        update_mock = MagicMock(side_effect=CommandExecutionError("not found"))
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=[]),
                "virt.init": init_mock,
                "virt.update": update_mock,
            },
        ):
            disks = [
                {
                    "name": "system",
                    "size": 8192,
                    "overlay_image": True,
                    "pool": "default",
                    "image": "/path/to/image.qcow2",
                },
                {"name": "data", "size": 16834},
            ]
            ifaces = [
                {"name": "eth0", "mac": "01:23:45:67:89:AB"},
                {"name": "eth1", "type": "network", "source": "admin"},
            ]
            graphics = {
                "type": "spice",
                "listen": {"type": "address", "address": "192.168.0.1"},
            }
            serials = [
                {"type": "tcp", "port": 22223, "protocol": "telnet"},
                {"type": "pty"},
            ]
            consoles = [
                {"type": "tcp", "port": 22223, "protocol": "telnet"},
                {"type": "pty"},
            ]
            assert virt.defined(
                "myvm",
                cpu=2,
                mem=2048,
                boot_dev="cdrom hd",
                os_type="linux",
                arch="i686",
                vm_type="qemu",
                disk_profile="prod",
                disks=disks,
                nic_profile="prod",
                interfaces=ifaces,
                graphics=graphics,
                seed=False,
                install=False,
                pub_key="/path/to/key.pub",
                priv_key="/path/to/key",
                hypervisor_features={"kvm-hint-dedicated": True},
                clock={"utc": True},
                stop_on_reboot=True,
                connection="someconnection",
                username="libvirtuser",
                password="supersecret",
                serials=serials,
                consoles=consoles,
                host_devices=["pci_0000_00_17_0"],
            ) == {
                "name": "myvm",
                "result": True if not test else None,
                "changes": {"myvm": {"definition": True}},
                "comment": "Domain myvm defined",
            }
            if not test:
                init_mock.assert_called_with(
                    "myvm",
                    cpu=2,
                    mem=2048,
                    boot_dev="cdrom hd",
                    os_type="linux",
                    arch="i686",
                    disk="prod",
                    disks=disks,
                    nic="prod",
                    interfaces=ifaces,
                    graphics=graphics,
                    hypervisor="qemu",
                    seed=False,
                    boot=None,
                    numatune=None,
                    install=False,
                    start=False,
                    pub_key="/path/to/key.pub",
                    priv_key="/path/to/key",
                    hypervisor_features={"kvm-hint-dedicated": True},
                    clock={"utc": True},
                    stop_on_reboot=True,
                    connection="someconnection",
                    username="libvirtuser",
                    password="supersecret",
                    serials=serials,
                    consoles=consoles,
                    host_devices=["pci_0000_00_17_0"],
                )
            else:
                init_mock.assert_not_called()
                update_mock.assert_not_called()


def test_defined_update(test):
    """
    defined state test, with change required case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        init_mock = MagicMock(return_value=True)
        update_mock = MagicMock(return_value={"definition": True, "cpu": True})
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm"]),
                "virt.update": update_mock,
                "virt.init": init_mock,
            },
        ):
            boot = {
                "kernel": "/root/f8-i386-vmlinuz",
                "initrd": "/root/f8-i386-initrd",
                "cmdline": "console=ttyS0 ks=http://example.com/f8-i386/os/",
            }
            assert virt.defined("myvm", cpu=2, boot=boot,) == {
                "name": "myvm",
                "changes": {"myvm": {"definition": True, "cpu": True}},
                "result": True if not test else None,
                "comment": "Domain myvm updated",
            }
            init_mock.assert_not_called()
            assert update_mock.call_args_list == [
                domain_update_call("myvm", cpu=2, test=test, boot=boot)
            ]


def test_defined_update_error(test):
    """
    defined state test, with error during the update.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        init_mock = MagicMock(return_value=True)
        update_mock = MagicMock(
            return_value={"definition": True, "cpu": False, "errors": ["some error"]}
        )
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm"]),
                "virt.update": update_mock,
                "virt.init": init_mock,
            },
        ):
            assert virt.defined("myvm", cpu=2, boot_dev="cdrom hd") == {
                "name": "myvm",
                "changes": {
                    "myvm": {
                        "definition": True,
                        "cpu": False,
                        "errors": ["some error"],
                    }
                },
                "result": True if not test else None,
                "comment": "Domain myvm updated with live update(s) failures",
            }
            init_mock.assert_not_called()
            update_mock.assert_called_with(
                "myvm",
                cpu=2,
                boot_dev="cdrom hd",
                mem=None,
                disk_profile=None,
                disks=None,
                nic_profile=None,
                interfaces=None,
                graphics=None,
                live=True,
                connection=None,
                username=None,
                password=None,
                boot=None,
                numatune=None,
                test=test,
                hypervisor_features=None,
                clock=None,
                serials=None,
                consoles=None,
                stop_on_reboot=False,
                host_devices=None,
            )


def test_defined_update_definition_error(test):
    """
    defined state test, with definition update failure
    """
    with patch.dict(virt.__opts__, {"test": test}):
        init_mock = MagicMock(return_value=True)
        update_mock = MagicMock(
            side_effect=[virt.libvirt.libvirtError("error message")]
        )
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm"]),
                "virt.update": update_mock,
                "virt.init": init_mock,
            },
        ):
            assert virt.defined("myvm", cpu=2) == {
                "name": "myvm",
                "changes": {},
                "result": False,
                "comment": "error message",
            }
            init_mock.assert_not_called()
            assert update_mock.call_args_list == [
                domain_update_call("myvm", cpu=2, test=test)
            ]


@pytest.mark.parametrize("running", ["running", "shutdown"])
def test_running_no_change(test, running):
    """
    running state test, no change required case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        update_mock = MagicMock(return_value={"definition": False})
        start_mock = MagicMock(return_value=0)
        with patch.dict(
            virt.__salt__,
            {
                "virt.vm_state": MagicMock(return_value={"myvm": running}),
                "virt.start": start_mock,
                "virt.update": MagicMock(return_value={"definition": False}),
                "virt.list_domains": MagicMock(return_value=["myvm"]),
            },
        ):
            assert virt.running("myvm") == {
                "name": "myvm",
                "result": True,
                "changes": {"myvm": {"started": True}} if running == "shutdown" else {},
                "comment": "Domain myvm started"
                if running == "shutdown"
                else "Domain myvm exists and is running",
            }
            if running == "shutdown" and not test:
                start_mock.assert_called()
            else:
                start_mock.assert_not_called()


def test_running_define(test):
    """
    running state test, defining and start a guest the old way
    """
    with patch.dict(virt.__opts__, {"test": test}):
        init_mock = MagicMock(return_value=True)
        start_mock = MagicMock(return_value=0)
        with patch.dict(
            virt.__salt__,
            {
                "virt.vm_state": MagicMock(return_value={"myvm": "stopped"}),
                "virt.init": init_mock,
                "virt.start": start_mock,
                "virt.list_domains": MagicMock(return_value=[]),
            },
        ):
            disks = [
                {
                    "name": "system",
                    "size": 8192,
                    "overlay_image": True,
                    "pool": "default",
                    "image": "/path/to/image.qcow2",
                },
                {"name": "data", "size": 16834},
            ]
            ifaces = [
                {"name": "eth0", "mac": "01:23:45:67:89:AB"},
                {"name": "eth1", "type": "network", "source": "admin"},
            ]
            graphics = {
                "type": "spice",
                "listen": {"type": "address", "address": "192.168.0.1"},
            }

            assert virt.running(
                "myvm",
                cpu=2,
                mem=2048,
                os_type="linux",
                arch="i686",
                vm_type="qemu",
                disk_profile="prod",
                disks=disks,
                nic_profile="prod",
                interfaces=ifaces,
                graphics=graphics,
                seed=False,
                install=False,
                pub_key="/path/to/key.pub",
                priv_key="/path/to/key",
                boot_dev="network hd",
                stop_on_reboot=True,
                host_devices=["pci_0000_00_17_0"],
                connection="someconnection",
                username="libvirtuser",
                password="supersecret",
            ) == {
                "name": "myvm",
                "result": True if not test else None,
                "changes": {"myvm": {"definition": True, "started": True}},
                "comment": "Domain myvm defined and started",
            }
            if not test:
                init_mock.assert_called_with(
                    "myvm",
                    cpu=2,
                    mem=2048,
                    os_type="linux",
                    arch="i686",
                    disk="prod",
                    disks=disks,
                    nic="prod",
                    interfaces=ifaces,
                    graphics=graphics,
                    hypervisor="qemu",
                    seed=False,
                    boot=None,
                    numatune=None,
                    install=False,
                    start=False,
                    pub_key="/path/to/key.pub",
                    priv_key="/path/to/key",
                    boot_dev="network hd",
                    hypervisor_features=None,
                    clock=None,
                    stop_on_reboot=True,
                    connection="someconnection",
                    username="libvirtuser",
                    password="supersecret",
                    serials=None,
                    consoles=None,
                    host_devices=["pci_0000_00_17_0"],
                )
                start_mock.assert_called_with(
                    "myvm",
                    connection="someconnection",
                    username="libvirtuser",
                    password="supersecret",
                )
            else:
                init_mock.assert_not_called()
                start_mock.assert_not_called()


def test_running_start_error():
    """
    running state test, start an existing guest raising an error
    """
    with patch.dict(virt.__opts__, {"test": False}):
        with patch.dict(
            virt.__salt__,
            {
                "virt.vm_state": MagicMock(return_value={"myvm": "stopped"}),
                "virt.update": MagicMock(return_value={"definition": False}),
                "virt.start": MagicMock(
                    side_effect=[virt.libvirt.libvirtError("libvirt error msg")]
                ),
                "virt.list_domains": MagicMock(return_value=["myvm"]),
            },
        ):
            assert virt.running("myvm") == {
                "name": "myvm",
                "changes": {},
                "result": False,
                "comment": "libvirt error msg",
            }


@pytest.mark.parametrize("running", ["running", "shutdown"])
def test_running_update(test, running):
    """
    running state test, update an existing guest
    """
    with patch.dict(virt.__opts__, {"test": test}):
        start_mock = MagicMock(return_value=0)
        with patch.dict(
            virt.__salt__,
            {
                "virt.vm_state": MagicMock(return_value={"myvm": running}),
                "virt.update": MagicMock(
                    return_value={"definition": True, "cpu": True}
                ),
                "virt.start": start_mock,
                "virt.list_domains": MagicMock(return_value=["myvm"]),
            },
        ):
            changes = {"definition": True, "cpu": True}
            if running == "shutdown":
                changes["started"] = True
            assert virt.running("myvm", cpu=2) == {
                "name": "myvm",
                "changes": {"myvm": changes},
                "result": True if not test else None,
                "comment": "Domain myvm updated"
                if running == "running"
                else "Domain myvm updated and started",
            }
            if running == "shutdown" and not test:
                start_mock.assert_called()
            else:
                start_mock.assert_not_called()


def test_running_definition_error():
    """
    running state test, update an existing guest raising an error when setting the XML
    """
    with patch.dict(virt.__opts__, {"test": False}):
        with patch.dict(
            virt.__salt__,
            {
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.update": MagicMock(
                    side_effect=[virt.libvirt.libvirtError("error message")]
                ),
                "virt.list_domains": MagicMock(return_value=["myvm"]),
            },
        ):
            assert virt.running("myvm", cpu=3) == {
                "name": "myvm",
                "changes": {},
                "result": False,
                "comment": "error message",
            }


def test_running_update_error():
    """
    running state test, update an existing guest raising an error
    """
    with patch.dict(virt.__opts__, {"test": False}):
        update_mock = MagicMock(
            return_value={"definition": True, "cpu": False, "errors": ["some error"]}
        )
        with patch.dict(
            virt.__salt__,
            {
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.update": update_mock,
                "virt.list_domains": MagicMock(return_value=["myvm"]),
            },
        ):
            assert virt.running("myvm", cpu=2) == {
                "name": "myvm",
                "changes": {
                    "myvm": {
                        "definition": True,
                        "cpu": False,
                        "errors": ["some error"],
                    }
                },
                "result": True,
                "comment": "Domain myvm updated with live update(s) failures",
            }
            update_mock.assert_called_with(
                "myvm",
                cpu=2,
                mem=None,
                disk_profile=None,
                disks=None,
                nic_profile=None,
                interfaces=None,
                graphics=None,
                live=True,
                connection=None,
                username=None,
                password=None,
                boot=None,
                numatune=None,
                test=False,
                boot_dev=None,
                hypervisor_features=None,
                clock=None,
                serials=None,
                consoles=None,
                stop_on_reboot=False,
                host_devices=None,
            )


@pytest.mark.parametrize("running", ["running", "shutdown"])
def test_stopped(test, running):
    """
    stopped state test, running guest
    """
    with patch.dict(virt.__opts__, {"test": test}):
        shutdown_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": running}),
                "virt.shutdown": shutdown_mock,
            },
        ):
            changes = {}
            comment = "No changes had happened"
            if running == "running":
                changes = {"stopped": [{"domain": "myvm", "shutdown": True}]}
                comment = "Machine has been shut down"
            assert virt.stopped(
                "myvm",
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "myvm",
                "changes": changes,
                "comment": comment,
                "result": True if not test or running == "shutdown" else None,
            }
            if not test and running == "running":
                shutdown_mock.assert_called_with(
                    "myvm",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
            else:
                shutdown_mock.assert_not_called()


def test_stopped_error():
    """
    stopped state test, error while stopping guest
    """
    with patch.dict(virt.__opts__, {"test": False}):
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.shutdown": MagicMock(
                    side_effect=virt.libvirt.libvirtError("Some error")
                ),
            },
        ):
            assert virt.stopped("myvm") == {
                "name": "myvm",
                "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                "result": False,
                "comment": "No changes had happened",
            }


def test_stopped_not_existing(test):
    """
    stopped state test, non existing guest
    """
    with patch.dict(virt.__opts__, {"test": test}):
        shutdown_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {"virt.list_domains": MagicMock(return_value=[])},
        ):
            assert virt.stopped("myvm") == {
                "name": "myvm",
                "changes": {},
                "comment": "No changes had happened",
                "result": False,
            }


@pytest.mark.parametrize("running", ["running", "shutdown"])
def test_powered_off(test, running):
    """
    powered_off state test
    """
    with patch.dict(virt.__opts__, {"test": test}):
        stop_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": running}),
                "virt.stop": stop_mock,
            },
        ):
            changes = {}
            comment = "No changes had happened"
            if running == "running":
                changes = {"unpowered": [{"domain": "myvm", "stop": True}]}
                comment = "Machine has been powered off"
            assert virt.powered_off(
                "myvm",
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "myvm",
                "result": True if not test or running == "shutdown" else None,
                "changes": changes,
                "comment": comment,
            }
            if not test and running == "running":
                stop_mock.assert_called_with(
                    "myvm",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
            else:
                stop_mock.assert_not_called()


def test_powered_off_error():
    """
    powered_off state test, error case
    """
    with patch.dict(virt.__opts__, {"test": False}):
        stop_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.stop": MagicMock(
                    side_effect=virt.libvirt.libvirtError("Some error")
                ),
            },
        ):
            assert virt.powered_off("myvm") == {
                "name": "myvm",
                "result": False,
                "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                "comment": "No changes had happened",
            }


def test_powered_off_not_existing():
    """
    powered_off state test cases.
    """
    ret = {"name": "myvm", "changes": {}, "result": True}
    with patch.dict(virt.__opts__, {"test": False}):
        with patch.dict(
            virt.__salt__, {"virt.list_domains": MagicMock(return_value=[])}
        ):  # pylint: disable=no-member
            ret.update(
                {"changes": {}, "result": False, "comment": "No changes had happened"}
            )
            assert virt.powered_off("myvm") == {
                "name": "myvm",
                "changes": {},
                "result": False,
                "comment": "No changes had happened",
            }


def test_snapshot(test):
    """
    snapshot state test
    """
    with patch.dict(virt.__opts__, {"test": test}):
        snapshot_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.snapshot": snapshot_mock,
            },
        ):
            assert virt.snapshot(
                "myvm",
                suffix="snap",
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "myvm",
                "result": True if not test else None,
                "changes": {"saved": [{"domain": "myvm", "snapshot": True}]},
                "comment": "Snapshot has been taken",
            }
            if not test:
                snapshot_mock.assert_called_with(
                    "myvm",
                    suffix="snap",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
            else:
                snapshot_mock.assert_not_called()


def test_snapshot_error():
    """
    snapshot state test, error case
    """
    with patch.dict(virt.__opts__, {"test": False}):
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.snapshot": MagicMock(
                    side_effect=virt.libvirt.libvirtError("Some error")
                ),
            },
        ):
            assert virt.snapshot("myvm") == {
                "name": "myvm",
                "result": False,
                "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                "comment": "No changes had happened",
            }


def test_snapshot_not_existing(test):
    """
    snapshot state test, guest not existing.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        with patch.dict(
            virt.__salt__, {"virt.list_domains": MagicMock(return_value=[])}
        ):
            assert virt.snapshot("myvm") == {
                "name": "myvm",
                "changes": {},
                "result": False,
                "comment": "No changes had happened",
            }


def test_rebooted(test):
    """
    rebooted state test
    """
    with patch.dict(virt.__opts__, {"test": test}):
        reboot_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.reboot": reboot_mock,
            },
        ):
            assert virt.rebooted(
                "myvm",
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "myvm",
                "result": True if not test else None,
                "changes": {"rebooted": [{"domain": "myvm", "reboot": True}]},
                "comment": "Machine has been rebooted",
            }
            if not test:
                reboot_mock.assert_called_with(
                    "myvm",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
            else:
                reboot_mock.assert_not_called()


def test_rebooted_error():
    """
    rebooted state test, error case.
    """
    with patch.dict(virt.__opts__, {"test": False}):
        reboot_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.reboot": MagicMock(
                    side_effect=virt.libvirt.libvirtError("Some error")
                ),
            },
        ):
            assert virt.rebooted("myvm") == {
                "name": "myvm",
                "result": False,
                "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                "comment": "No changes had happened",
            }


def test_rebooted_not_existing(test):
    """
    rebooted state test cases.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        with patch.dict(
            virt.__salt__, {"virt.list_domains": MagicMock(return_value=[])}
        ):
            assert virt.rebooted("myvm") == {
                "name": "myvm",
                "changes": {},
                "result": False,
                "comment": "No changes had happened",
            }
