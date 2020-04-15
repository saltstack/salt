# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import shutil
import tempfile

# Import Salt Libs
import salt.states.virt as virt
import salt.utils.files
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class LibvirtMock(MagicMock):  # pylint: disable=too-many-ancestors
    """
    libvirt library mockup
    """

    class libvirtError(Exception):  # pylint: disable=invalid-name
        """
        libvirt error mockup
        """

        def get_error_message(self):
            """
            Fake function return error message
            """
            return six.text_type(self)


class LibvirtTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.libvirt
    """

    def setup_loader_modules(self):
        self.mock_libvirt = (
            LibvirtMock()
        )  # pylint: disable=attribute-defined-outside-init
        self.addCleanup(delattr, self, "mock_libvirt")
        loader_globals = {"libvirt": self.mock_libvirt}
        return {virt: loader_globals}

    @classmethod
    def setUpClass(cls):
        cls.pki_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pki_dir)
        del cls.pki_dir

    # 'keys' function tests: 1

    def test_keys(self):
        """
        Test to manage libvirt keys.
        """
        with patch("os.path.isfile", MagicMock(return_value=False)):
            name = "sunrise"

            ret = {"name": name, "result": True, "comment": "", "changes": {}}

            mock = MagicMock(
                side_effect=[
                    [],
                    ["libvirt.servercert.pem"],
                    {"libvirt.servercert.pem": "A"},
                ]
            )
            with patch.dict(virt.__salt__, {"pillar.ext": mock}):
                comt = "All keys are correct"
                ret.update({"comment": comt})
                self.assertDictEqual(virt.keys(name, basepath=self.pki_dir), ret)

                with patch.dict(virt.__opts__, {"test": True}):
                    comt = "Libvirt keys are set to be updated"
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(virt.keys(name, basepath=self.pki_dir), ret)

                with patch.dict(virt.__opts__, {"test": False}):
                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(mock_open())
                    ):
                        comt = "Updated libvirt certs and keys"
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"servercert": "new"},
                            }
                        )
                        self.assertDictEqual(
                            virt.keys(name, basepath=self.pki_dir), ret
                        )

    def test_keys_with_expiration_days(self):
        """
        Test to manage libvirt keys.
        """
        with patch("os.path.isfile", MagicMock(return_value=False)):
            name = "sunrise"

            ret = {"name": name, "result": True, "comment": "", "changes": {}}

            mock = MagicMock(
                side_effect=[
                    [],
                    ["libvirt.servercert.pem"],
                    {"libvirt.servercert.pem": "A"},
                ]
            )
            with patch.dict(virt.__salt__, {"pillar.ext": mock}):
                comt = "All keys are correct"
                ret.update({"comment": comt})
                self.assertDictEqual(
                    virt.keys(name, basepath=self.pki_dir, expiration_days=700), ret
                )

                with patch.dict(virt.__opts__, {"test": True}):
                    comt = "Libvirt keys are set to be updated"
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(
                        virt.keys(name, basepath=self.pki_dir, expiration_days=700), ret
                    )

                with patch.dict(virt.__opts__, {"test": False}):
                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(mock_open())
                    ):
                        comt = "Updated libvirt certs and keys"
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"servercert": "new"},
                            }
                        )
                        self.assertDictEqual(
                            virt.keys(name, basepath=self.pki_dir, expiration_days=700),
                            ret,
                        )

    def test_keys_with_state(self):
        """
        Test to manage libvirt keys.
        """
        with patch("os.path.isfile", MagicMock(return_value=False)):
            name = "sunrise"

            ret = {"name": name, "result": True, "comment": "", "changes": {}}

            mock = MagicMock(
                side_effect=[
                    [],
                    ["libvirt.servercert.pem"],
                    {"libvirt.servercert.pem": "A"},
                ]
            )
            with patch.dict(virt.__salt__, {"pillar.ext": mock}):
                comt = "All keys are correct"
                ret.update({"comment": comt})
                self.assertDictEqual(
                    virt.keys(name, basepath=self.pki_dir, st="California"), ret
                )

                with patch.dict(virt.__opts__, {"test": True}):
                    comt = "Libvirt keys are set to be updated"
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(
                        virt.keys(name, basepath=self.pki_dir, st="California"), ret
                    )

                with patch.dict(virt.__opts__, {"test": False}):
                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(mock_open())
                    ):
                        comt = "Updated libvirt certs and keys"
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"servercert": "new"},
                            }
                        )
                        self.assertDictEqual(
                            virt.keys(name, basepath=self.pki_dir, st="California"), ret
                        )

    def test_keys_with_all_options(self):
        """
        Test to manage libvirt keys.
        """
        with patch("os.path.isfile", MagicMock(return_value=False)):
            name = "sunrise"

            ret = {"name": name, "result": True, "comment": "", "changes": {}}

            mock = MagicMock(
                side_effect=[
                    [],
                    ["libvirt.servercert.pem"],
                    {"libvirt.servercert.pem": "A"},
                ]
            )
            with patch.dict(virt.__salt__, {"pillar.ext": mock}):
                comt = "All keys are correct"
                ret.update({"comment": comt})
                self.assertDictEqual(
                    virt.keys(
                        name,
                        basepath=self.pki_dir,
                        country="USA",
                        st="California",
                        locality="Los_Angeles",
                        organization="SaltStack",
                        expiration_days=700,
                    ),
                    ret,
                )

                with patch.dict(virt.__opts__, {"test": True}):
                    comt = "Libvirt keys are set to be updated"
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(
                        virt.keys(
                            name,
                            basepath=self.pki_dir,
                            country="USA",
                            st="California",
                            locality="Los_Angeles",
                            organization="SaltStack",
                            expiration_days=700,
                        ),
                        ret,
                    )

                with patch.dict(virt.__opts__, {"test": False}):
                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(mock_open())
                    ):
                        comt = "Updated libvirt certs and keys"
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"servercert": "new"},
                            }
                        )
                        self.assertDictEqual(
                            virt.keys(
                                name,
                                basepath=self.pki_dir,
                                country="USA",
                                st="California",
                                locality="Los_Angeles",
                                organization="SaltStack",
                                expiration_days=700,
                            ),
                            ret,
                        )

    def test_running(self):
        """
        running state test cases.
        """
        ret = {
            "name": "myvm",
            "changes": {},
            "result": True,
            "comment": "myvm is running",
        }
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(return_value={"myvm": "stopped"}),
                "virt.start": MagicMock(return_value=0),
            },
        ):
            ret.update(
                {
                    "changes": {"myvm": "Domain started"},
                    "comment": "Domain myvm started",
                }
            )
            self.assertDictEqual(virt.running("myvm"), ret)

        init_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(
                    side_effect=CommandExecutionError("not found")
                ),
                "virt.init": init_mock,
                "virt.start": MagicMock(return_value=0),
            },
        ):
            ret.update(
                {
                    "changes": {"myvm": "Domain defined and started"},
                    "comment": "Domain myvm defined and started",
                }
            )
            self.assertDictEqual(
                virt.running("myvm", cpu=2, mem=2048, image="/path/to/img.qcow2"), ret
            )
            init_mock.assert_called_with(
                "myvm",
                cpu=2,
                mem=2048,
                image="/path/to/img.qcow2",
                os_type=None,
                arch=None,
                boot=None,
                disk=None,
                disks=None,
                nic=None,
                interfaces=None,
                graphics=None,
                hypervisor=None,
                seed=True,
                install=True,
                pub_key=None,
                priv_key=None,
                connection=None,
                username=None,
                password=None,
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(
                    side_effect=CommandExecutionError("not found")
                ),
                "virt.init": init_mock,
                "virt.start": MagicMock(return_value=0),
            },
        ):
            ret.update(
                {
                    "changes": {"myvm": "Domain defined and started"},
                    "comment": "Domain myvm defined and started",
                }
            )
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
            self.assertDictEqual(
                virt.running(
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
                    connection="someconnection",
                    username="libvirtuser",
                    password="supersecret",
                ),
                ret,
            )
            init_mock.assert_called_with(
                "myvm",
                cpu=2,
                mem=2048,
                os_type="linux",
                arch="i686",
                image=None,
                disk="prod",
                disks=disks,
                nic="prod",
                interfaces=ifaces,
                graphics=graphics,
                hypervisor="qemu",
                seed=False,
                boot=None,
                install=False,
                pub_key="/path/to/key.pub",
                priv_key="/path/to/key",
                connection="someconnection",
                username="libvirtuser",
                password="supersecret",
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(return_value={"myvm": "stopped"}),
                "virt.start": MagicMock(
                    side_effect=[self.mock_libvirt.libvirtError("libvirt error msg")]
                ),
            },
        ):
            ret.update({"changes": {}, "result": False, "comment": "libvirt error msg"})
            self.assertDictEqual(virt.running("myvm"), ret)

        # Working update case when running
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.update": MagicMock(
                    return_value={"definition": True, "cpu": True}
                ),
            },
        ):
            ret.update(
                {
                    "changes": {"myvm": {"definition": True, "cpu": True}},
                    "result": True,
                    "comment": "Domain myvm updated, restart to fully apply the changes",
                }
            )
            self.assertDictEqual(virt.running("myvm", update=True, cpu=2), ret)

        # Working update case when running with boot params
        boot = {
            "kernel": "/root/f8-i386-vmlinuz",
            "initrd": "/root/f8-i386-initrd",
            "cmdline": "console=ttyS0 ks=http://example.com/f8-i386/os/",
        }

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.update": MagicMock(
                    return_value={"definition": True, "cpu": True}
                ),
            },
        ):
            ret.update(
                {
                    "changes": {"myvm": {"definition": True, "cpu": True}},
                    "result": True,
                    "comment": "Domain myvm updated, restart to fully apply the changes",
                }
            )
            self.assertDictEqual(virt.running("myvm", update=True, boot=boot), ret)

        # Working update case when stopped
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(return_value={"myvm": "stopped"}),
                "virt.start": MagicMock(return_value=0),
                "virt.update": MagicMock(return_value={"definition": True}),
            },
        ):
            ret.update(
                {
                    "changes": {"myvm": "Domain updated and started"},
                    "result": True,
                    "comment": "Domain myvm updated and started",
                }
            )
            self.assertDictEqual(virt.running("myvm", update=True, cpu=2), ret)

        # Failed live update case
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.update": MagicMock(
                    return_value={
                        "definition": True,
                        "cpu": False,
                        "errors": ["some error"],
                    }
                ),
            },
        ):
            ret.update(
                {
                    "changes": {
                        "myvm": {
                            "definition": True,
                            "cpu": False,
                            "errors": ["some error"],
                        }
                    },
                    "result": True,
                    "comment": "Domain myvm updated, but some live update(s) failed",
                }
            )
            self.assertDictEqual(virt.running("myvm", update=True, cpu=2), ret)

        # Failed definition update case
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.update": MagicMock(
                    side_effect=[self.mock_libvirt.libvirtError("error message")]
                ),
            },
        ):
            ret.update({"changes": {}, "result": False, "comment": "error message"})
            self.assertDictEqual(virt.running("myvm", update=True, cpu=2), ret)

    def test_stopped(self):
        """
        stopped state test cases.
        """
        ret = {"name": "myvm", "changes": {}, "result": True}

        shutdown_mock = MagicMock(return_value=True)

        # Normal case
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.shutdown": shutdown_mock,
            },
        ):
            ret.update(
                {
                    "changes": {"stopped": [{"domain": "myvm", "shutdown": True}]},
                    "comment": "Machine has been shut down",
                }
            )
            self.assertDictEqual(virt.stopped("myvm"), ret)
            shutdown_mock.assert_called_with(
                "myvm", connection=None, username=None, password=None
            )

        # Normal case with user-provided connection parameters
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.shutdown": shutdown_mock,
            },
        ):
            self.assertDictEqual(
                virt.stopped(
                    "myvm",
                    connection="myconnection",
                    username="user",
                    password="secret",
                ),
                ret,
            )
            shutdown_mock.assert_called_with(
                "myvm", connection="myconnection", username="user", password="secret"
            )

        # Case where an error occurred during the shutdown
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.shutdown": MagicMock(
                    side_effect=self.mock_libvirt.libvirtError("Some error")
                ),
            },
        ):
            ret.update(
                {
                    "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                    "result": False,
                    "comment": "No changes had happened",
                }
            )
            self.assertDictEqual(virt.stopped("myvm"), ret)

        # Case there the domain doesn't exist
        with patch.dict(
            virt.__salt__, {"virt.list_domains": MagicMock(return_value=[])}
        ):  # pylint: disable=no-member
            ret.update(
                {"changes": {}, "result": False, "comment": "No changes had happened"}
            )
            self.assertDictEqual(virt.stopped("myvm"), ret)

        # Case where the domain is already stopped
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "shutdown"}),
            },
        ):
            ret.update(
                {"changes": {}, "result": True, "comment": "No changes had happened"}
            )
            self.assertDictEqual(virt.stopped("myvm"), ret)

    def test_powered_off(self):
        """
        powered_off state test cases.
        """
        ret = {"name": "myvm", "changes": {}, "result": True}

        stop_mock = MagicMock(return_value=True)

        # Normal case
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.stop": stop_mock,
            },
        ):
            ret.update(
                {
                    "changes": {"unpowered": [{"domain": "myvm", "stop": True}]},
                    "comment": "Machine has been powered off",
                }
            )
            self.assertDictEqual(virt.powered_off("myvm"), ret)
            stop_mock.assert_called_with(
                "myvm", connection=None, username=None, password=None
            )

        # Normal case with user-provided connection parameters
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.stop": stop_mock,
            },
        ):
            self.assertDictEqual(
                virt.powered_off(
                    "myvm",
                    connection="myconnection",
                    username="user",
                    password="secret",
                ),
                ret,
            )
            stop_mock.assert_called_with(
                "myvm", connection="myconnection", username="user", password="secret"
            )

        # Case where an error occurred during the poweroff
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "running"}),
                "virt.stop": MagicMock(
                    side_effect=self.mock_libvirt.libvirtError("Some error")
                ),
            },
        ):
            ret.update(
                {
                    "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                    "result": False,
                    "comment": "No changes had happened",
                }
            )
            self.assertDictEqual(virt.powered_off("myvm"), ret)

        # Case there the domain doesn't exist
        with patch.dict(
            virt.__salt__, {"virt.list_domains": MagicMock(return_value=[])}
        ):  # pylint: disable=no-member
            ret.update(
                {"changes": {}, "result": False, "comment": "No changes had happened"}
            )
            self.assertDictEqual(virt.powered_off("myvm"), ret)

        # Case where the domain is already stopped
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.vm_state": MagicMock(return_value={"myvm": "shutdown"}),
            },
        ):
            ret.update(
                {"changes": {}, "result": True, "comment": "No changes had happened"}
            )
            self.assertDictEqual(virt.powered_off("myvm"), ret)

    def test_snapshot(self):
        """
        snapshot state test cases.
        """
        ret = {"name": "myvm", "changes": {}, "result": True}

        snapshot_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.snapshot": snapshot_mock,
            },
        ):
            ret.update(
                {
                    "changes": {"saved": [{"domain": "myvm", "snapshot": True}]},
                    "comment": "Snapshot has been taken",
                }
            )
            self.assertDictEqual(virt.snapshot("myvm"), ret)
            snapshot_mock.assert_called_with(
                "myvm", suffix=None, connection=None, username=None, password=None
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.snapshot": snapshot_mock,
            },
        ):
            self.assertDictEqual(
                virt.snapshot(
                    "myvm",
                    suffix="snap",
                    connection="myconnection",
                    username="user",
                    password="secret",
                ),
                ret,
            )
            snapshot_mock.assert_called_with(
                "myvm",
                suffix="snap",
                connection="myconnection",
                username="user",
                password="secret",
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.snapshot": MagicMock(
                    side_effect=self.mock_libvirt.libvirtError("Some error")
                ),
            },
        ):
            ret.update(
                {
                    "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                    "result": False,
                    "comment": "No changes had happened",
                }
            )
            self.assertDictEqual(virt.snapshot("myvm"), ret)

        with patch.dict(
            virt.__salt__, {"virt.list_domains": MagicMock(return_value=[])}
        ):  # pylint: disable=no-member
            ret.update(
                {"changes": {}, "result": False, "comment": "No changes had happened"}
            )
            self.assertDictEqual(virt.snapshot("myvm"), ret)

    def test_rebooted(self):
        """
        rebooted state test cases.
        """
        ret = {"name": "myvm", "changes": {}, "result": True}

        reboot_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.reboot": reboot_mock,
            },
        ):
            ret.update(
                {
                    "changes": {"rebooted": [{"domain": "myvm", "reboot": True}]},
                    "comment": "Machine has been rebooted",
                }
            )
            self.assertDictEqual(virt.rebooted("myvm"), ret)
            reboot_mock.assert_called_with(
                "myvm", connection=None, username=None, password=None
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.reboot": reboot_mock,
            },
        ):
            self.assertDictEqual(
                virt.rebooted(
                    "myvm",
                    connection="myconnection",
                    username="user",
                    password="secret",
                ),
                ret,
            )
            reboot_mock.assert_called_with(
                "myvm", connection="myconnection", username="user", password="secret"
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.list_domains": MagicMock(return_value=["myvm", "vm1"]),
                "virt.reboot": MagicMock(
                    side_effect=self.mock_libvirt.libvirtError("Some error")
                ),
            },
        ):
            ret.update(
                {
                    "changes": {"ignored": [{"domain": "myvm", "issue": "Some error"}]},
                    "result": False,
                    "comment": "No changes had happened",
                }
            )
            self.assertDictEqual(virt.rebooted("myvm"), ret)

        with patch.dict(
            virt.__salt__, {"virt.list_domains": MagicMock(return_value=[])}
        ):  # pylint: disable=no-member
            ret.update(
                {"changes": {}, "result": False, "comment": "No changes had happened"}
            )
            self.assertDictEqual(virt.rebooted("myvm"), ret)

    def test_network_running(self):
        """
        network_running state test cases.
        """
        ret = {"name": "mynet", "changes": {}, "result": True, "comment": ""}
        define_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.network_info": MagicMock(return_value={}),
                "virt.network_define": define_mock,
            },
        ):
            ret.update(
                {
                    "changes": {"mynet": "Network defined and started"},
                    "comment": "Network mynet defined and started",
                }
            )
            self.assertDictEqual(
                virt.network_running(
                    "mynet",
                    "br2",
                    "bridge",
                    vport="openvswitch",
                    tag=180,
                    ipv4_config={
                        "cidr": "192.168.2.0/24",
                        "dhcp_ranges": [
                            {"start": "192.168.2.10", "end": "192.168.2.25"},
                            {"start": "192.168.2.110", "end": "192.168.2.125"},
                        ],
                    },
                    ipv6_config={
                        "cidr": "2001:db8:ca2:2::1/64",
                        "dhcp_ranges": [
                            {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                        ],
                    },
                    autostart=False,
                    connection="myconnection",
                    username="user",
                    password="secret",
                ),
                ret,
            )
            define_mock.assert_called_with(
                "mynet",
                "br2",
                "bridge",
                vport="openvswitch",
                tag=180,
                autostart=False,
                start=True,
                ipv4_config={
                    "cidr": "192.168.2.0/24",
                    "dhcp_ranges": [
                        {"start": "192.168.2.10", "end": "192.168.2.25"},
                        {"start": "192.168.2.110", "end": "192.168.2.125"},
                    ],
                },
                ipv6_config={
                    "cidr": "2001:db8:ca2:2::1/64",
                    "dhcp_ranges": [
                        {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                    ],
                },
                connection="myconnection",
                username="user",
                password="secret",
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.network_info": MagicMock(
                    return_value={"mynet": {"active": True}}
                ),
                "virt.network_define": define_mock,
            },
        ):
            ret.update(
                {"changes": {}, "comment": "Network mynet exists and is running"}
            )
            self.assertDictEqual(virt.network_running("mynet", "br2", "bridge"), ret)

        start_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.network_info": MagicMock(
                    return_value={"mynet": {"active": False}}
                ),
                "virt.network_start": start_mock,
                "virt.network_define": define_mock,
            },
        ):
            ret.update(
                {
                    "changes": {"mynet": "Network started"},
                    "comment": "Network mynet started",
                }
            )
            self.assertDictEqual(
                virt.network_running(
                    "mynet",
                    "br2",
                    "bridge",
                    connection="myconnection",
                    username="user",
                    password="secret",
                ),
                ret,
            )
            start_mock.assert_called_with(
                "mynet", connection="myconnection", username="user", password="secret"
            )

        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.network_info": MagicMock(return_value={}),
                "virt.network_define": MagicMock(
                    side_effect=self.mock_libvirt.libvirtError("Some error")
                ),
            },
        ):
            ret.update({"changes": {}, "comment": "Some error", "result": False})
            self.assertDictEqual(virt.network_running("mynet", "br2", "bridge"), ret)

    def test_pool_running(self):
        """
        pool_running state test cases.
        """
        ret = {"name": "mypool", "changes": {}, "result": True, "comment": ""}
        mocks = {
            mock: MagicMock(return_value=True)
            for mock in ["define", "autostart", "build", "start", "stop"]
        }
        with patch.dict(virt.__opts__, {"test": False}):
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(return_value={}),
                    "virt.pool_define": mocks["define"],
                    "virt.pool_build": mocks["build"],
                    "virt.pool_start": mocks["start"],
                    "virt.pool_set_autostart": mocks["autostart"],
                },
            ):
                ret.update(
                    {
                        "changes": {
                            "mypool": "Pool defined, started and marked for autostart"
                        },
                        "comment": "Pool mypool defined, started and marked for autostart",
                    }
                )
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        permissions={
                            "mode": "0770",
                            "owner": 1000,
                            "group": 100,
                            "label": "seclabel",
                        },
                        source={"devices": [{"path": "/dev/sda"}]},
                        transient=True,
                        autostart=True,
                        connection="myconnection",
                        username="user",
                        password="secret",
                    ),
                    ret,
                )
                mocks["define"].assert_called_with(
                    "mypool",
                    ptype="logical",
                    target="/dev/base",
                    permissions={
                        "mode": "0770",
                        "owner": 1000,
                        "group": 100,
                        "label": "seclabel",
                    },
                    source_devices=[{"path": "/dev/sda"}],
                    source_dir=None,
                    source_adapter=None,
                    source_hosts=None,
                    source_auth=None,
                    source_name=None,
                    source_format=None,
                    source_initiator=None,
                    transient=True,
                    start=False,
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
                mocks["autostart"].assert_called_with(
                    "mypool",
                    state="on",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
                mocks["build"].assert_called_with(
                    "mypool",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
                mocks["start"].assert_called_with(
                    "mypool",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )

            mocks["update"] = MagicMock(return_value=False)
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        return_value={"mypool": {"state": "running", "autostart": True}}
                    ),
                    "virt.pool_update": MagicMock(return_value=False),
                },
            ):
                ret.update(
                    {"changes": {}, "comment": "Pool mypool unchanged and is running"}
                )
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )

            for mock in mocks:
                mocks[mock].reset_mock()
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        return_value={"mypool": {"state": "stopped", "autostart": True}}
                    ),
                    "virt.pool_update": mocks["update"],
                    "virt.pool_build": mocks["build"],
                    "virt.pool_start": mocks["start"],
                },
            ):
                ret.update(
                    {
                        "changes": {"mypool": "Pool started"},
                        "comment": "Pool mypool started",
                    }
                )
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )
                mocks["start"].assert_called_with(
                    "mypool", connection=None, username=None, password=None
                )
                mocks["build"].assert_not_called()

            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(return_value={}),
                    "virt.pool_define": MagicMock(
                        side_effect=self.mock_libvirt.libvirtError("Some error")
                    ),
                },
            ):
                ret.update({"changes": {}, "comment": "Some error", "result": False})
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )

            # Test case with update and autostart change on stopped pool
            for mock in mocks:
                mocks[mock].reset_mock()
            mocks["update"] = MagicMock(return_value=True)
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        return_value={"mypool": {"state": "stopped", "autostart": True}}
                    ),
                    "virt.pool_update": mocks["update"],
                    "virt.pool_set_autostart": mocks["autostart"],
                    "virt.pool_build": mocks["build"],
                    "virt.pool_start": mocks["start"],
                },
            ):
                ret.update(
                    {
                        "changes": {
                            "mypool": "Pool updated, built, autostart flag changed and started"
                        },
                        "comment": "Pool mypool updated, built, autostart flag changed and started",
                        "result": True,
                    }
                )
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        autostart=False,
                        permissions={
                            "mode": "0770",
                            "owner": 1000,
                            "group": 100,
                            "label": "seclabel",
                        },
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )
                mocks["start"].assert_called_with(
                    "mypool", connection=None, username=None, password=None
                )
                mocks["build"].assert_called_with(
                    "mypool", connection=None, username=None, password=None
                )
                mocks["autostart"].assert_called_with(
                    "mypool", state="off", connection=None, username=None, password=None
                )
                mocks["update"].assert_called_with(
                    "mypool",
                    ptype="logical",
                    target="/dev/base",
                    permissions={
                        "mode": "0770",
                        "owner": 1000,
                        "group": 100,
                        "label": "seclabel",
                    },
                    source_devices=[{"path": "/dev/sda"}],
                    source_dir=None,
                    source_adapter=None,
                    source_hosts=None,
                    source_auth=None,
                    source_name=None,
                    source_format=None,
                    source_initiator=None,
                    connection=None,
                    username=None,
                    password=None,
                )

            # test case with update and no autostart change on running pool
            for mock in mocks:
                mocks[mock].reset_mock()
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        return_value={
                            "mypool": {"state": "running", "autostart": False}
                        }
                    ),
                    "virt.pool_update": mocks["update"],
                    "virt.pool_build": mocks["build"],
                    "virt.pool_start": mocks["start"],
                    "virt.pool_stop": mocks["stop"],
                },
            ):
                ret.update(
                    {
                        "changes": {"mypool": "Pool updated, built and restarted"},
                        "comment": "Pool mypool updated, built and restarted",
                        "result": True,
                    }
                )
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        autostart=False,
                        permissions={
                            "mode": "0770",
                            "owner": 1000,
                            "group": 100,
                            "label": "seclabel",
                        },
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )
                mocks["stop"].assert_called_with(
                    "mypool", connection=None, username=None, password=None
                )
                mocks["start"].assert_called_with(
                    "mypool", connection=None, username=None, password=None
                )
                mocks["build"].assert_called_with(
                    "mypool", connection=None, username=None, password=None
                )
                mocks["update"].assert_called_with(
                    "mypool",
                    ptype="logical",
                    target="/dev/base",
                    permissions={
                        "mode": "0770",
                        "owner": 1000,
                        "group": 100,
                        "label": "seclabel",
                    },
                    source_devices=[{"path": "/dev/sda"}],
                    source_dir=None,
                    source_adapter=None,
                    source_hosts=None,
                    source_auth=None,
                    source_name=None,
                    source_format=None,
                    source_initiator=None,
                    connection=None,
                    username=None,
                    password=None,
                )

        with patch.dict(virt.__opts__, {"test": True}):
            # test case with test=True and no change
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        return_value={"mypool": {"state": "running", "autostart": True}}
                    ),
                    "virt.pool_update": MagicMock(return_value=False),
                },
            ):
                ret.update(
                    {
                        "changes": {},
                        "comment": "Pool mypool unchanged and is running",
                        "result": True,
                    }
                )
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )

            # test case with test=True and started
            for mock in mocks:
                mocks[mock].reset_mock()
            mocks["update"] = MagicMock(return_value=False)
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        return_value={"mypool": {"state": "stopped", "autostart": True}}
                    ),
                    "virt.pool_update": mocks["update"],
                },
            ):
                ret.update(
                    {
                        "changes": {"mypool": "Pool started"},
                        "comment": "Pool mypool started",
                        "result": None,
                    }
                )
                self.assertDictEqual(
                    virt.pool_running(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )

    def test_pool_deleted(self):
        """
        Test the pool_deleted state
        """
        # purge=False test case, stopped pool
        with patch.dict(
            virt.__salt__,
            {
                "virt.pool_info": MagicMock(
                    return_value={"test01": {"state": "stopped", "type": "dir"}}
                ),
                "virt.pool_undefine": MagicMock(return_value=True),
            },
        ):
            expected = {
                "name": "test01",
                "changes": {
                    "stopped": False,
                    "deleted_volumes": [],
                    "deleted": False,
                    "undefined": True,
                },
                "result": True,
                "comment": "",
            }

            with patch.dict(virt.__opts__, {"test": False}):
                self.assertDictEqual(expected, virt.pool_deleted("test01"))

            with patch.dict(virt.__opts__, {"test": True}):
                expected["result"] = None
                self.assertDictEqual(expected, virt.pool_deleted("test01"))

        # purge=False test case
        with patch.dict(
            virt.__salt__,
            {
                "virt.pool_info": MagicMock(
                    return_value={"test01": {"state": "running", "type": "dir"}}
                ),
                "virt.pool_undefine": MagicMock(return_value=True),
                "virt.pool_stop": MagicMock(return_value=True),
            },
        ):
            expected = {
                "name": "test01",
                "changes": {
                    "stopped": True,
                    "deleted_volumes": [],
                    "deleted": False,
                    "undefined": True,
                },
                "result": True,
                "comment": "",
            }

            with patch.dict(virt.__opts__, {"test": False}):
                self.assertDictEqual(expected, virt.pool_deleted("test01"))

            with patch.dict(virt.__opts__, {"test": True}):
                expected["result"] = None
                self.assertDictEqual(expected, virt.pool_deleted("test01"))

        # purge=True test case

        with patch.dict(
            virt.__salt__,
            {
                "virt.pool_info": MagicMock(
                    return_value={"test01": {"state": "running", "type": "dir"}}
                ),
                "virt.pool_list_volumes": MagicMock(
                    return_value=["vm01.qcow2", "vm02.qcow2"]
                ),
                "virt.pool_refresh": MagicMock(return_value=True),
                "virt.volume_delete": MagicMock(return_value=True),
                "virt.pool_stop": MagicMock(return_value=True),
                "virt.pool_delete": MagicMock(return_value=True),
                "virt.pool_undefine": MagicMock(return_value=True),
            },
        ):
            expected = {
                "name": "test01",
                "changes": {
                    "stopped": True,
                    "deleted_volumes": ["vm01.qcow2", "vm02.qcow2"],
                    "deleted": True,
                    "undefined": True,
                },
                "result": True,
                "comment": "",
            }

            with patch.dict(virt.__opts__, {"test": False}):
                self.assertDictEqual(expected, virt.pool_deleted("test01", purge=True))

            with patch.dict(virt.__opts__, {"test": True}):
                expected["result"] = None
                self.assertDictEqual(expected, virt.pool_deleted("test01", purge=True))

        # Case of backend not unsupporting delete operations
        with patch.dict(
            virt.__salt__,
            {
                "virt.pool_info": MagicMock(
                    return_value={"test01": {"state": "running", "type": "iscsi"}}
                ),
                "virt.pool_stop": MagicMock(return_value=True),
                "virt.pool_undefine": MagicMock(return_value=True),
            },
        ):
            expected = {
                "name": "test01",
                "changes": {
                    "stopped": True,
                    "deleted_volumes": [],
                    "deleted": False,
                    "undefined": True,
                },
                "result": True,
                "comment": 'Unsupported actions for pool of type "iscsi": deleting volume, deleting pool',
            }

            with patch.dict(virt.__opts__, {"test": False}):
                self.assertDictEqual(expected, virt.pool_deleted("test01", purge=True))

            with patch.dict(virt.__opts__, {"test": True}):
                expected["result"] = None
                self.assertDictEqual(expected, virt.pool_deleted("test01", purge=True))
