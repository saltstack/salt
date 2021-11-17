"""
    :synopsis: Unit Tests for Windows IIS Module 'module.win_iis'
    :platform: Windows
    :maturity: develop
    versionadded:: 2016.11.0
"""
import salt.modules.win_iis as win_iis
import salt.utils.json
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase

APP_LIST = {
    "testApp": {
        "apppool": "MyTestPool",
        "path": "/testApp",
        "preload": False,
        "protocols": ["http"],
        "sourcepath": r"C:\inetpub\apps\testApp",
    }
}

APPPOOL_LIST = {"MyTestPool": {"applications": ["MyTestSite"], "state": "Started"}}

BINDING_LIST = {
    "*:80:": {
        "certificatehash": None,
        "certificatestorename": None,
        "hostheader": None,
        "ipaddress": "*",
        "port": 80,
        "protocol": "http",
        "sslflags": 0,
    },
    "*:443:mytestsite.local": {
        "certificatehash": "9988776655443322111000AAABBBCCCDDDEEEFFF",
        "certificatestorename": "My",
        "hostheader": "mytestsite.local",
        "ipaddress": "*",
        "port": 443,
        "protocol": "https",
        "sslflags": 0,
    },
}

SITE_LIST = {
    "MyTestSite": {
        "apppool": "MyTestPool",
        "bindings": BINDING_LIST,
        "id": 1,
        "sourcepath": r"C:\inetpub\wwwroot",
        "state": "Started",
    }
}

VDIR_LIST = {"TestVdir": {"sourcepath": r"C:\inetpub\vdirs\TestVdir"}}
NESTED_VDIR_LIST = {
    "Test/Nested/Vdir": {"sourcepath": r"C:\inetpub\vdirs\NestedTestVdir"}
}


LIST_APPS_SRVMGR = {
    "retcode": 0,
    "stdout": salt.utils.json.dumps(
        [
            {
                "applicationPool": "MyTestPool",
                "name": "testApp",
                "path": "/testApp",
                "PhysicalPath": r"C:\inetpub\apps\testApp",
                "preloadEnabled": False,
                "protocols": "http",
            }
        ]
    ),
}

LIST_APPPOOLS_SRVMGR = {
    "retcode": 0,
    "stdout": salt.utils.json.dumps(
        [
            {
                "name": "MyTestPool",
                "state": "Started",
                "Applications": {"value": ["MyTestSite"], "Count": 1},
            }
        ]
    ),
}

LIST_VDIRS_SRVMGR = {
    "retcode": 0,
    "stdout": salt.utils.json.dumps(
        [{"name": "TestVdir", "physicalPath": r"C:\inetpub\vdirs\TestVdir"}]
    ),
}

LIST_MORE_VDIRS_SRVMGR = {
    "retcode": 0,
    "stdout": salt.utils.json.dumps(
        [
            {"name": "TestVdir", "physicalPath": r"C:\inetpub\vdirs\TestVdir"},
            {
                "name": "Test/Nested/Vdir",
                "physicalPath": r"C:\inetpub\vdirs\NestedTestVdir",
            },
        ]
    ),
}

CONTAINER_SETTING = {
    "retcode": 0,
    "stdout": salt.utils.json.dumps([{"managedPipelineMode": "Integrated"}]),
}

CERT_BINDING_INFO = "*:443:mytestsite.local"


class WinIisTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_iis
    """

    def setup_loader_modules(self):
        return {win_iis: {}}

    def test_create_apppool(self):
        """
        Test - Create an IIS application pool.
        """
        with patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_apppools", MagicMock(return_value=dict())
        ), patch.dict(
            win_iis.__salt__
        ):
            self.assertTrue(win_iis.create_apppool("MyTestPool"))

    def test_list_apppools(self):
        """
        Test - List all configured IIS application pools.
        """
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value=LIST_APPPOOLS_SRVMGR)
        ):
            self.assertEqual(win_iis.list_apppools(), APPPOOL_LIST)

    def test_remove_apppool(self):
        """
        Test - Remove an IIS application pool.
        """
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_apppools",
            MagicMock(
                return_value={
                    "MyTestPool": {"applications": list(), "state": "Started"}
                }
            ),
        ):
            self.assertTrue(win_iis.remove_apppool("MyTestPool"))

    def test_restart_apppool(self):
        """
        Test - Restart an IIS application pool.
        """
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ):
            self.assertTrue(win_iis.restart_apppool("MyTestPool"))

    def test_create_site(self):
        """
        Test - Create a basic website in IIS.
        """
        kwargs = {
            "name": "MyTestSite",
            "sourcepath": r"C:\inetpub\wwwroot",
            "apppool": "MyTestPool",
            "hostheader": "mytestsite.local",
            "ipaddress": "*",
            "port": 80,
            "protocol": "http",
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_sites", MagicMock(return_value=dict())
        ), patch(
            "salt.modules.win_iis.list_apppools", MagicMock(return_value=dict())
        ):
            self.assertTrue(win_iis.create_site(**kwargs))

    def test_create_site_failed(self):
        """
        Test - Create a basic website in IIS using invalid data.
        """
        kwargs = {
            "name": "MyTestSite",
            "sourcepath": r"C:\inetpub\wwwroot",
            "apppool": "MyTestPool",
            "hostheader": "mytestsite.local",
            "ipaddress": "*",
            "port": 80,
            "protocol": "invalid-protocol-name",
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_sites", MagicMock(return_value=dict())
        ), patch(
            "salt.modules.win_iis.list_apppools", MagicMock(return_value=dict())
        ):
            self.assertRaises(SaltInvocationError, win_iis.create_site, **kwargs)

    def test_remove_site(self):
        """
        Test - Delete a website from IIS.
        """
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch("salt.modules.win_iis.list_sites", MagicMock(return_value=SITE_LIST)):
            self.assertTrue(win_iis.remove_site("MyTestSite"))

    def test_create_app(self):
        """
        Test - Create an IIS application.
        """
        kwargs = {
            "name": "testApp",
            "site": "MyTestSite",
            "sourcepath": r"C:\inetpub\apps\testApp",
            "apppool": "MyTestPool",
        }
        with patch.dict(win_iis.__salt__), patch(
            "os.path.isdir", MagicMock(return_value=True)
        ), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_apps", MagicMock(return_value=APP_LIST)
        ):
            self.assertTrue(win_iis.create_app(**kwargs))

    def test_list_apps(self):
        """
        Test - Get all configured IIS applications for the specified site.
        """
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value=LIST_APPS_SRVMGR)
        ):
            self.assertEqual(win_iis.list_apps("MyTestSite"), APP_LIST)

    def test_remove_app(self):
        """
        Test - Remove an IIS application.
        """
        kwargs = {"name": "otherApp", "site": "MyTestSite"}
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch("salt.modules.win_iis.list_apps", MagicMock(return_value=APP_LIST)):
            self.assertTrue(win_iis.remove_app(**kwargs))

    def test_create_binding(self):
        """
        Test - Create an IIS binding.
        """
        kwargs = {
            "site": "MyTestSite",
            "hostheader": "",
            "ipaddress": "*",
            "port": 80,
            "protocol": "http",
            "sslflags": 0,
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_bindings", MagicMock(return_value=BINDING_LIST)
        ):
            self.assertTrue(win_iis.create_binding(**kwargs))

    def test_create_binding_failed(self):
        """
        Test - Create an IIS binding using invalid data.
        """
        kwargs = {
            "site": "MyTestSite",
            "hostheader": "",
            "ipaddress": "*",
            "port": 80,
            "protocol": "invalid-protocol-name",
            "sslflags": 999,
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_bindings", MagicMock(return_value=BINDING_LIST)
        ):
            self.assertRaises(SaltInvocationError, win_iis.create_binding, **kwargs)

    def test_list_bindings(self):
        """
        Test - Get all configured IIS bindings for the specified site.
        """
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis.list_sites", MagicMock(return_value=SITE_LIST)
        ):
            self.assertEqual(win_iis.list_bindings("MyTestSite"), BINDING_LIST)

    def test_remove_binding(self):
        """
        Test - Remove an IIS binding.
        """
        kwargs = {
            "site": "MyTestSite",
            "hostheader": "myothertestsite.local",
            "ipaddress": "*",
            "port": 443,
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_bindings", MagicMock(return_value=BINDING_LIST)
        ):
            self.assertTrue(win_iis.remove_binding(**kwargs))

    def test_create_vdir(self):
        """
        Test - Create an IIS virtual directory.
        """
        kwargs = {
            "name": "TestVdir",
            "site": "MyTestSite",
            "sourcepath": r"C:\inetpub\vdirs\TestVdir",
        }
        with patch.dict(win_iis.__salt__), patch(
            "os.path.isdir", MagicMock(return_value=True)
        ), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_vdirs", MagicMock(return_value=VDIR_LIST)
        ):
            self.assertTrue(win_iis.create_vdir(**kwargs))

    def test_list_vdirs(self):
        """
        Test - Get configured IIS virtual directories.
        """
        vdirs = {"TestVdir": {"sourcepath": r"C:\inetpub\vdirs\TestVdir"}}
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value=LIST_VDIRS_SRVMGR)
        ):
            self.assertEqual(win_iis.list_vdirs("MyTestSite"), vdirs)

    def test_remove_vdir(self):
        """
        Test - Remove an IIS virtual directory.
        """
        kwargs = {"name": "TestOtherVdir", "site": "MyTestSite"}
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch("salt.modules.win_iis.list_vdirs", MagicMock(return_value=VDIR_LIST)):
            self.assertTrue(win_iis.remove_vdir(**kwargs))

    def test_create_nested_vdir(self):
        """
        Test - Create a nested IIS virtual directory.
        """
        kwargs = {
            "name": "Test/Nested/Vdir",
            "site": "MyTestSite",
            "sourcepath": r"C:\inetpub\vdirs\NestedTestVdir",
        }
        with patch.dict(win_iis.__salt__), patch(
            "os.path.isdir", MagicMock(return_value=True)
        ), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_vdirs", MagicMock(return_value=NESTED_VDIR_LIST)
        ):
            self.assertTrue(win_iis.create_vdir(**kwargs))

    def test_list_nested_vdirs(self):
        """
        Test - Get configured IIS virtual directories.
        """
        vdirs = {
            "TestVdir": {"sourcepath": r"C:\inetpub\vdirs\TestVdir"},
            "Test/Nested/Vdir": {"sourcepath": r"C:\inetpub\vdirs\NestedTestVdir"},
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr",
            MagicMock(return_value=LIST_MORE_VDIRS_SRVMGR),
        ):
            self.assertEqual(win_iis.list_vdirs("MyTestSite"), vdirs)

    def test_create_cert_binding(self):
        """
        Test - Assign a certificate to an IIS binding.
        """
        kwargs = {
            "name": "9988776655443322111000AAABBBCCCDDDEEEFFF",
            "site": "MyTestSite",
            "hostheader": "mytestsite.local",
            "ipaddress": "*",
            "port": 443,
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._list_certs",
            MagicMock(return_value={"9988776655443322111000AAABBBCCCDDDEEEFFF": None}),
        ), patch(
            "salt.modules.win_iis._srvmgr",
            MagicMock(return_value={"retcode": 0, "stdout": 10}),
        ), patch(
            "salt.utils.json.loads",
            MagicMock(return_value=[{"MajorVersion": 10, "MinorVersion": 0}]),
        ), patch(
            "salt.modules.win_iis.list_bindings", MagicMock(return_value=BINDING_LIST)
        ), patch(
            "salt.modules.win_iis.list_cert_bindings",
            MagicMock(
                return_value={CERT_BINDING_INFO: BINDING_LIST[CERT_BINDING_INFO]}
            ),
        ):
            self.assertTrue(win_iis.create_cert_binding(**kwargs))

    def test_list_cert_bindings(self):
        """
        Test - List certificate bindings for an IIS site.
        """
        key = "*:443:mytestsite.local"
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis.list_sites", MagicMock(return_value=SITE_LIST)
        ):
            self.assertEqual(
                win_iis.list_cert_bindings("MyTestSite"), {key: BINDING_LIST[key]}
            )

    def test_remove_cert_binding(self):
        """
        Test - Remove a certificate from an IIS binding.
        """
        kwargs = {
            "name": "FFFEEEDDDCCCBBBAAA0001112233445566778899",
            "site": "MyOtherTestSite",
            "hostheader": "myothertestsite.local",
            "ipaddress": "*",
            "port": 443,
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.list_cert_bindings",
            MagicMock(
                return_value={CERT_BINDING_INFO: BINDING_LIST[CERT_BINDING_INFO]}
            ),
        ):
            self.assertTrue(win_iis.remove_cert_binding(**kwargs))

    def test_get_container_setting(self):
        """
        Test - Get the value of the setting for the IIS container.
        """
        kwargs = {
            "name": "MyTestSite",
            "container": "AppPools",
            "settings": ["managedPipelineMode"],
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value=CONTAINER_SETTING)
        ):
            self.assertEqual(
                win_iis.get_container_setting(**kwargs),
                {"managedPipelineMode": "Integrated"},
            )

    def test_set_container_setting(self):
        """
        Test - Set the value of the setting for an IIS container.
        """
        kwargs = {
            "name": "MyTestSite",
            "container": "AppPools",
            "settings": {"managedPipelineMode": "Integrated"},
        }
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._srvmgr", MagicMock(return_value={"retcode": 0})
        ), patch(
            "salt.modules.win_iis.get_container_setting",
            MagicMock(return_value={"managedPipelineMode": "Integrated"}),
        ):
            self.assertTrue(win_iis.set_container_setting(**kwargs))

    def test__collection_match_to_index(self):
        bad_match = {"key_0": "value"}
        first_match = {"key_1": "value"}
        second_match = {"key_2": "value"}
        collection = [first_match, second_match]
        settings = [{"name": "enabled", "value": collection}]
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis.get_webconfiguration_settings",
            MagicMock(return_value=settings),
        ):
            ret = win_iis._collection_match_to_index(
                "pspath", "colfilter", "name", bad_match
            )
            self.assertEqual(ret, -1)
            ret = win_iis._collection_match_to_index(
                "pspath", "colfilter", "name", first_match
            )
            self.assertEqual(ret, 0)
            ret = win_iis._collection_match_to_index(
                "pspath", "colfilter", "name", second_match
            )
            self.assertEqual(ret, 1)

    def test__prepare_settings(self):
        simple_setting = {"name": "value", "filter": "value"}
        collection_setting = {"name": "Collection[{yaml:\n\tdata}]", "filter": "value"}
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._collection_match_to_index", MagicMock(return_value=0)
        ):
            ret = win_iis._prepare_settings(
                "pspath",
                [
                    simple_setting,
                    collection_setting,
                    {"invalid": "setting"},
                    {"name": "filter-less_setting"},
                ],
            )
            self.assertEqual(ret, [simple_setting, collection_setting])

    @patch("salt.modules.win_iis.log")
    def test_get_webconfiguration_settings_empty(self, mock_log):
        ret = win_iis.get_webconfiguration_settings("name", settings=[])
        mock_log.warning.assert_called_once_with("No settings provided")
        self.assertEqual(ret, {})

    def test_get_webconfiguration_settings(self):
        # Setup
        name = "IIS"
        collection_setting = {"name": "Collection[{yaml:\n\tdata}]", "filter": "value"}
        filter_setting = {
            "name": "enabled",
            "filter": (
                "system.webServer / security / authentication / anonymousAuthentication"
            ),
        }
        settings = [collection_setting, filter_setting]

        ps_cmd = [
            "$Settings = New-Object System.Collections.ArrayList;",
        ]
        for setting in settings:
            ps_cmd.extend(
                [
                    "$Property = Get-WebConfigurationProperty -PSPath '{}'".format(
                        name
                    ),
                    "-Name '{name}' -Filter '{filter}' -ErrorAction Stop;".format(
                        filter=setting["filter"], name=setting["name"]
                    ),
                    "if (([String]::IsNullOrEmpty($Property) -eq $False) -and",
                    "($Property.GetType()).Name -eq 'ConfigurationAttribute') {",
                    "$Property = $Property | Select-Object",
                    "-ExpandProperty Value };",
                    "$Settings.add(@{{filter='{filter}';name='{name}';value=[String]"
                    " $Property}})| Out-Null;".format(
                        filter=setting["filter"], name=setting["name"]
                    ),
                    "$Property = $Null;",
                ]
            )
        ps_cmd.append("$Settings")

        # Execute
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._prepare_settings", MagicMock(return_value=settings)
        ), patch(
            "salt.modules.win_iis._srvmgr",
            MagicMock(return_value={"retcode": 0, "stdout": "{}"}),
        ):
            ret = win_iis.get_webconfiguration_settings(name, settings=settings)

            # Verify
            win_iis._srvmgr.assert_called_with(cmd=ps_cmd, return_json=True)
            self.assertEqual(ret, {})

    @patch("salt.modules.win_iis.log")
    def test_set_webconfiguration_settings_empty(self, mock_log):
        ret = win_iis.set_webconfiguration_settings("name", settings=[])
        mock_log.warning.assert_called_once_with("No settings provided")
        self.assertEqual(ret, False)

    @patch("salt.modules.win_iis.log")
    def test_set_webconfiguration_settings_no_changes(self, mock_log):
        # Setup
        name = "IIS"
        setting = {
            "name": "Collection[{yaml:\n\tdata}]",
            "filter": (
                "system.webServer / security / authentication / anonymousAuthentication"
            ),
            "value": [],
        }
        settings = [setting]

        # Execute
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._prepare_settings", MagicMock(return_value=settings)
        ), patch(
            "salt.modules.win_iis._srvmgr",
            MagicMock(return_value={"retcode": 0, "stdout": "{}"}),
        ), patch(
            "salt.modules.win_iis.get_webconfiguration_settings",
            MagicMock(return_value=settings),
        ):
            ret = win_iis.set_webconfiguration_settings(name, settings=settings)

            # Verify
            mock_log.debug.assert_called_with(
                "Settings already contain the provided values."
            )
            self.assertEqual(ret, True)

    @patch("salt.modules.win_iis.log")
    def test_set_webconfiguration_settings_failed(self, mock_log):
        # Setup
        name = "IIS"
        setting = {
            "name": "Collection[{yaml:\n\tdata}]",
            "filter": (
                "system.webServer / security / authentication / anonymousAuthentication"
            ),
            "value": [],
        }
        settings = [setting]

        # Execute
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._prepare_settings", MagicMock(return_value=settings)
        ), patch(
            "salt.modules.win_iis._srvmgr",
            MagicMock(return_value={"retcode": 0, "stdout": "{}"}),
        ), patch(
            "salt.modules.win_iis.get_webconfiguration_settings",
            MagicMock(side_effect=[[], [{"value": "unexpected_change!"}]]),
        ):

            ret = win_iis.set_webconfiguration_settings(name, settings=settings)

            # Verify
            self.assertEqual(ret, False)
            mock_log.error.assert_called_with("Failed to change settings: %s", settings)

    @patch("salt.modules.win_iis.log")
    def test_set_webconfiguration_settings(self, mock_log):
        # Setup
        name = "IIS"
        setting = {
            "name": "Collection[{yaml:\n\tdata}]",
            "filter": (
                "system.webServer / security / authentication / anonymousAuthentication"
            ),
            "value": [],
        }
        settings = [setting]

        # Execute
        with patch.dict(win_iis.__salt__), patch(
            "salt.modules.win_iis._prepare_settings", MagicMock(return_value=settings)
        ), patch(
            "salt.modules.win_iis._srvmgr",
            MagicMock(return_value={"retcode": 0, "stdout": "{}"}),
        ), patch(
            "salt.modules.win_iis.get_webconfiguration_settings",
            MagicMock(side_effect=[[], settings]),
        ):
            ret = win_iis.set_webconfiguration_settings(name, settings=settings)

            # Verify
            self.assertEqual(ret, True)
            mock_log.debug.assert_called_with(
                "Settings configured successfully: %s", settings
            )

    def test_get_webconfiguration_settings_no_settings(self):
        self.assertEqual(win_iis.get_webconfiguration_settings("salt", {}), {})

    def test_get_webconfiguration_settings_pass(self):
        settings = [
            {
                "name": "enabled",
                "filter": (
                    "system.webServer/security/authentication/anonymousAuthentication"
                ),
            }
        ]

        ps_cmd_validate = [
            "Get-WebConfigurationProperty",
            "-PSPath",
            "'salt'",
            "-Filter",
            "'system.webServer/security/authentication/anonymousAuthentication'",
            "-Name",
            "'enabled'",
            "-ErrorAction",
            "Stop",
            "|",
            "Out-Null;",
        ]

        ps_cmd = [
            "$Settings = New-Object System.Collections.ArrayList;",
            "$Property = Get-WebConfigurationProperty -PSPath 'salt'",
            "-Name 'enabled' -Filter"
            " 'system.webServer/security/authentication/anonymousAuthentication'"
            " -ErrorAction Stop;",
            "if (([String]::IsNullOrEmpty($Property) -eq $False) -and",
            "($Property.GetType()).Name -eq 'ConfigurationAttribute') {",
            "$Property = $Property | Select-Object",
            "-ExpandProperty Value };",
            "$Settings.add(@{filter='system.webServer/security/authentication/anonymousAuthentication';name='enabled';value=[String]"
            " $Property})| Out-Null;",
            "$Property = $Null;",
            "$Settings",
        ]

        func_ret = {"name": "enabled", "value": True}
        with patch.object(
            win_iis, "_srvmgr", return_value={"retcode": 0, "stdout": "json data"}
        ) as _srvmgr:
            with patch.object(
                win_iis.salt.utils.json, "loads", return_value=func_ret
            ) as loads:
                ret = win_iis.get_webconfiguration_settings("salt", settings)

                self.assertEqual(_srvmgr.call_count, 2)
                self.assertEqual(
                    _srvmgr.mock_calls[0], call(cmd=ps_cmd_validate, return_json=True)
                )
                self.assertEqual(
                    _srvmgr.mock_calls[1], call(cmd=ps_cmd, return_json=True)
                )

                loads.assert_called_once_with("json data", strict=False)
                self.assertEqual(func_ret, ret)

    def test_set_webconfiguration_settings_no_settings(self):
        self.assertEqual(win_iis.set_webconfiguration_settings("salt", {}), False)

    def test_set_webconfiguration_settings_pass(self):
        settings = [
            {
                "name": "enabled",
                "filter": (
                    "system.webServer/security/authentication/anonymousAuthentication"
                ),
                "value": False,
            }
        ]

        current_settings = [
            {
                "name": "enabled",
                "filter": (
                    "system.webServer/security/authentication/anonymousAuthentication"
                ),
                "value": True,
            }
        ]

        new_settings = [
            {
                "name": "enabled",
                "filter": (
                    "system.webServer/security/authentication/anonymousAuthentication"
                ),
                "value": False,
            }
        ]

        ps_cmd = [
            "Set-WebConfigurationProperty",
            "-PSPath",
            "'salt'",
            "-Filter",
            "'system.webServer/security/authentication/anonymousAuthentication'",
            "-Name",
            "'enabled'",
            "-Value",
            "'False';",
        ]

        with patch.object(
            win_iis,
            "get_webconfiguration_settings",
            side_effect=[current_settings, new_settings],
        ) as get_webconfiguration_settings:
            with patch.object(
                win_iis, "_srvmgr", return_value={"retcode": 0}
            ) as _srvmgr:
                ret = win_iis.set_webconfiguration_settings("salt", settings)

                self.assertEqual(get_webconfiguration_settings.call_count, 2)
                self.assertEqual(
                    get_webconfiguration_settings.mock_calls[0],
                    call(name="salt", settings=settings),
                )
                self.assertEqual(
                    get_webconfiguration_settings.mock_calls[1],
                    call(name="salt", settings=settings),
                )

                _srvmgr.assert_called_once_with(ps_cmd)

                self.assertTrue(ret)

    def test_set_webconfiguration_settings_fail(self):
        settings = [
            {
                "name": "enabled",
                "filter": (
                    "system.webServer/security/authentication/anonymousAuthentication"
                ),
                "value": False,
            }
        ]

        current_settings = [
            {
                "name": "enabled",
                "filter": (
                    "system.webServer/security/authentication/anonymousAuthentication"
                ),
                "value": True,
            }
        ]

        new_settings = [
            {
                "name": "enabled",
                "filter": (
                    "system.webServer/security/authentication/anonymousAuthentication"
                ),
                "value": True,
            }
        ]

        ps_cmd = [
            "Set-WebConfigurationProperty",
            "-PSPath",
            "'salt'",
            "-Filter",
            "'system.webServer/security/authentication/anonymousAuthentication'",
            "-Name",
            "'enabled'",
            "-Value",
            "'False';",
        ]

        with patch.object(
            win_iis,
            "get_webconfiguration_settings",
            side_effect=[current_settings, new_settings],
        ) as get_webconfiguration_settings:
            with patch.object(
                win_iis, "_srvmgr", return_value={"retcode": 0}
            ) as _srvmgr:
                ret = win_iis.set_webconfiguration_settings("salt", settings)

                self.assertEqual(get_webconfiguration_settings.call_count, 2)
                self.assertEqual(
                    get_webconfiguration_settings.mock_calls[0],
                    call(name="salt", settings=settings),
                )
                self.assertEqual(
                    get_webconfiguration_settings.mock_calls[1],
                    call(name="salt", settings=settings),
                )

                _srvmgr.assert_called_once_with(ps_cmd)

                self.assertFalse(ret)
