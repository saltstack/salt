"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import shutil
import tempfile

import salt.states.virt as virt
import salt.utils.files
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
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
            return str(self)


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

    def test_pool_defined(self):
        """
        pool_defined state test cases.
        """
        ret = {"name": "mypool", "changes": {}, "result": True, "comment": ""}
        mocks = {
            mock: MagicMock(return_value=True)
            for mock in ["define", "autostart", "build"]
        }
        with patch.dict(virt.__opts__, {"test": False}):
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        side_effect=[
                            {},
                            {"mypool": {"state": "stopped", "autostart": True}},
                        ]
                    ),
                    "virt.pool_define": mocks["define"],
                    "virt.pool_build": mocks["build"],
                    "virt.pool_set_autostart": mocks["autostart"],
                },
            ):
                ret.update(
                    {
                        "changes": {"mypool": "Pool defined, marked for autostart"},
                        "comment": "Pool mypool defined, marked for autostart",
                    }
                )
                self.assertDictEqual(
                    virt.pool_defined(
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

            # Define a pool that doesn't handle build
            for mock in mocks:
                mocks[mock].reset_mock()
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        side_effect=[
                            {},
                            {"mypool": {"state": "stopped", "autostart": True}},
                        ]
                    ),
                    "virt.pool_define": mocks["define"],
                    "virt.pool_build": mocks["build"],
                    "virt.pool_set_autostart": mocks["autostart"],
                },
            ):
                ret.update(
                    {
                        "changes": {"mypool": "Pool defined, marked for autostart"},
                        "comment": "Pool mypool defined, marked for autostart",
                    }
                )
                self.assertDictEqual(
                    virt.pool_defined(
                        "mypool",
                        ptype="rbd",
                        source={
                            "name": "libvirt-pool",
                            "hosts": ["ses2.tf.local", "ses3.tf.local"],
                            "auth": {
                                "username": "libvirt",
                                "password": "AQAz+PRdtquBBRAASMv7nlMZYfxIyLw3St65Xw==",
                            },
                        },
                        autostart=True,
                    ),
                    ret,
                )
                mocks["define"].assert_called_with(
                    "mypool",
                    ptype="rbd",
                    target=None,
                    permissions=None,
                    source_devices=None,
                    source_dir=None,
                    source_adapter=None,
                    source_hosts=["ses2.tf.local", "ses3.tf.local"],
                    source_auth={
                        "username": "libvirt",
                        "password": "AQAz+PRdtquBBRAASMv7nlMZYfxIyLw3St65Xw==",
                    },
                    source_name="libvirt-pool",
                    source_format=None,
                    source_initiator=None,
                    start=False,
                    transient=False,
                    connection=None,
                    username=None,
                    password=None,
                )
                mocks["autostart"].assert_called_with(
                    "mypool",
                    state="on",
                    connection=None,
                    username=None,
                    password=None,
                )
                mocks["build"].assert_not_called()

            mocks["update"] = MagicMock(return_value=False)
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
                },
            ):
                ret.update({"changes": {}, "comment": "Pool mypool unchanged"})
                self.assertDictEqual(
                    virt.pool_defined(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
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
                    virt.pool_defined(
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
            mocks["build"] = MagicMock(
                side_effect=self.mock_libvirt.libvirtError("Existing VG")
            )
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(
                        return_value={"mypool": {"state": "stopped", "autostart": True}}
                    ),
                    "virt.pool_update": mocks["update"],
                    "virt.pool_set_autostart": mocks["autostart"],
                    "virt.pool_build": mocks["build"],
                },
            ):
                ret.update(
                    {
                        "changes": {
                            "mypool": "Pool updated, built, autostart flag changed"
                        },
                        "comment": "Pool mypool updated, built, autostart flag changed",
                        "result": True,
                    }
                )
                self.assertDictEqual(
                    virt.pool_defined(
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
                },
            ):
                ret.update(
                    {
                        "changes": {"mypool": "Pool updated"},
                        "comment": "Pool mypool updated",
                        "result": True,
                    }
                )
                self.assertDictEqual(
                    virt.pool_defined(
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
                mocks["build"].assert_not_called()
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
                    {"changes": {}, "comment": "Pool mypool unchanged", "result": True}
                )
                self.assertDictEqual(
                    virt.pool_defined(
                        "mypool",
                        ptype="logical",
                        target="/dev/base",
                        source={"devices": [{"path": "/dev/sda"}]},
                    ),
                    ret,
                )

            # test case with test=True and pool to be defined
            for mock in mocks:
                mocks[mock].reset_mock()
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(return_value={}),
                },
            ):
                ret.update(
                    {
                        "changes": {"mypool": "Pool defined, marked for autostart"},
                        "comment": "Pool mypool defined, marked for autostart",
                        "result": None,
                    }
                )
                self.assertDictEqual(
                    virt.pool_defined(
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
                    "virt.pool_info": MagicMock(
                        side_effect=[
                            {},
                            {"mypool": {"state": "stopped", "autostart": True}},
                        ]
                    ),
                    "virt.pool_define": mocks["define"],
                    "virt.pool_build": mocks["build"],
                    "virt.pool_start": mocks["start"],
                    "virt.pool_set_autostart": mocks["autostart"],
                },
            ):
                ret.update(
                    {
                        "changes": {
                            "mypool": "Pool defined, marked for autostart, started"
                        },
                        "comment": "Pool mypool defined, marked for autostart, started",
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
                ret.update({"changes": {}, "comment": "Pool mypool already running"})
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
                            "mypool": (
                                "Pool updated, built, autostart flag changed, started"
                            )
                        },
                        "comment": (
                            "Pool mypool updated, built, autostart flag changed,"
                            " started"
                        ),
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
                        "changes": {"mypool": "Pool updated, restarted"},
                        "comment": "Pool mypool updated, restarted",
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
                mocks["build"].assert_not_called()
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
                        "comment": "Pool mypool already running",
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

            # test case with test=True and pool to be defined
            for mock in mocks:
                mocks[mock].reset_mock()
            with patch.dict(
                virt.__salt__,
                {  # pylint: disable=no-member
                    "virt.pool_info": MagicMock(return_value={}),
                },
            ):
                ret.update(
                    {
                        "changes": {
                            "mypool": "Pool defined, marked for autostart, started"
                        },
                        "comment": "Pool mypool defined, marked for autostart, started",
                        "result": None,
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
                "comment": (
                    'Unsupported actions for pool of type "iscsi": deleting volume,'
                    " deleting pool"
                ),
            }

            with patch.dict(virt.__opts__, {"test": False}):
                self.assertDictEqual(expected, virt.pool_deleted("test01", purge=True))

            with patch.dict(virt.__opts__, {"test": True}):
                expected["result"] = None
                self.assertDictEqual(expected, virt.pool_deleted("test01", purge=True))

    def test_volume_defined(self):
        """
        test the virt.volume_defined state
        """
        with patch.dict(virt.__opts__, {"test": False}):
            # test case: creating a volume
            define_mock = MagicMock()
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(return_value={"mypool": {}}),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {"mypool/myvol": {"old": "", "new": "defined"}},
                        "result": True,
                        "comment": "Volume myvol defined in pool mypool",
                    },
                )
                define_mock.assert_called_once_with(
                    "mypool",
                    "myvol",
                    "1234",
                    allocation="12345",
                    format="qcow2",
                    type="file",
                    permissions={"mode": "0755", "owner": "123", "group": "456"},
                    backing_store={"path": "/path/to/image", "format": "raw"},
                    nocow=True,
                    connection="test:///",
                    username="jdoe",
                    password="supersecret",
                )

            # test case: with existing volume
            define_mock.reset_mock()
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "qcow2",
                                    "capacity": "1293942784",
                                    "backing_store": {
                                        "path": "/path/to/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": True,
                        "comment": "volume is existing",
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different sizes
            define_mock.reset_mock()
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "qcow2",
                                    "capacity": "12345",
                                    "backing_store": {
                                        "path": "/path/to/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": True,
                        "comment": (
                            "The capacity of the volume is different, but no resize"
                            " performed"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different backing store
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "qcow2",
                                    "capacity": "1234",
                                    "backing_store": {
                                        "path": "/path/to/other/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": False,
                        "comment": (
                            "A volume with the same name but different backing store or"
                            " format is existing"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different format
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "raw",
                                    "capacity": "1234",
                                    "backing_store": {
                                        "path": "/path/to/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": False,
                        "comment": (
                            "A volume with the same name but different backing store or"
                            " format is existing"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: no pool
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "qcow2",
                                    "capacity": "1234",
                                    "backing_store": {
                                        "path": "/path/to/other/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": False,
                        "comment": (
                            "A volume with the same name but different backing store or"
                            " format is existing"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different format
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=[]),
                    "virt.volume_infos": MagicMock(return_value={}),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertRaisesRegex(
                    SaltInvocationError,
                    "Storage pool mypool not existing",
                    virt.volume_defined,
                    "mypool",
                    "myvol",
                    "1234",
                    allocation="12345",
                    format="qcow2",
                    type="file",
                    permissions={"mode": "0755", "owner": "123", "group": "456"},
                    backing_store={"path": "/path/to/image", "format": "raw"},
                    nocow=True,
                    connection="test:///",
                    username="jdoe",
                    password="supersecret",
                )

        # Test mode cases
        with patch.dict(virt.__opts__, {"test": True}):
            # test case: creating a volume
            define_mock.reset_mock()
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(return_value={"mypool": {}}),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {"mypool/myvol": {"old": "", "new": "defined"}},
                        "result": None,
                        "comment": "Volume myvol would be defined in pool mypool",
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different sizes
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "qcow2",
                                    "capacity": "12345",
                                    "backing_store": {
                                        "path": "/path/to/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": True,
                        "comment": (
                            "The capacity of the volume is different, but no resize"
                            " performed"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different backing store
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "qcow2",
                                    "capacity": "1234",
                                    "backing_store": {
                                        "path": "/path/to/other/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": False,
                        "comment": (
                            "A volume with the same name but different backing store or"
                            " format is existing"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different format
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "raw",
                                    "capacity": "1234",
                                    "backing_store": {
                                        "path": "/path/to/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": False,
                        "comment": (
                            "A volume with the same name but different backing store or"
                            " format is existing"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: no pool
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=["mypool"]),
                    "virt.volume_infos": MagicMock(
                        return_value={
                            "mypool": {
                                "myvol": {
                                    "format": "qcow2",
                                    "capacity": "1234",
                                    "backing_store": {
                                        "path": "/path/to/other/image",
                                        "format": "raw",
                                    },
                                }
                            }
                        }
                    ),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertDictEqual(
                    virt.volume_defined(
                        "mypool",
                        "myvol",
                        "1234",
                        allocation="12345",
                        format="qcow2",
                        type="file",
                        permissions={"mode": "0755", "owner": "123", "group": "456"},
                        backing_store={"path": "/path/to/image", "format": "raw"},
                        nocow=True,
                        connection="test:///",
                        username="jdoe",
                        password="supersecret",
                    ),
                    {
                        "name": "myvol",
                        "changes": {},
                        "result": False,
                        "comment": (
                            "A volume with the same name but different backing store or"
                            " format is existing"
                        ),
                    },
                )
                define_mock.assert_not_called()

            # test case: with existing volume, different format
            with patch.dict(
                virt.__salt__,
                {
                    "virt.list_pools": MagicMock(return_value=[]),
                    "virt.volume_infos": MagicMock(return_value={}),
                    "virt.volume_define": define_mock,
                },
            ):
                self.assertRaisesRegex(
                    SaltInvocationError,
                    "Storage pool mypool not existing",
                    virt.volume_defined,
                    "mypool",
                    "myvol",
                    "1234",
                    allocation="12345",
                    format="qcow2",
                    type="file",
                    permissions={"mode": "0755", "owner": "123", "group": "456"},
                    backing_store={"path": "/path/to/image", "format": "raw"},
                    nocow=True,
                    connection="test:///",
                    username="jdoe",
                    password="supersecret",
                )
