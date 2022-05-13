"""
    :codeauthor: Alexander Schwartz <alexander.schwartz@gmx.net>
"""

import salt.client
from salt.cloud.clouds import saltify
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import ANY, MagicMock, patch
from tests.support.unit import TestCase

TEST_PROFILES = {
    "testprofile1": NotImplemented,
    "testprofile2": {  # this profile is used in test_saltify_destroy()
        "ssh_username": "fred",
        "remove_config_on_destroy": False,  # expected for test
        "shutdown_on_destroy": True,  # expected value for test
    },
    "testprofile3": {  # this profile is used in test_create_wake_on_lan()
        "wake_on_lan_mac": "aa-bb-cc-dd-ee-ff",
        "wol_sender_node": "friend1",
        "wol_boot_wait": 0.01,  # we want the wait to be very short
    },
}
TEST_PROFILE_NAMES = ["testprofile1", "testprofile2", "testprofile3"]


class SaltifyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.cloud.clouds.saltify
    """

    LOCAL_OPTS = {
        "providers": {
            "sfy1": {"saltify": {"driver": "saltify", "profiles": TEST_PROFILES}},
        },
        "profiles": TEST_PROFILES,
        "sock_dir": "/var/sockxxx",
        "transport": "tcp",
    }

    def setup_loader_modules(self):
        saltify_globals = {
            "__active_provider_name__": "",
            "__utils__": {
                "cloud.bootstrap": MagicMock(),
                "cloud.fire_event": MagicMock(),
            },
            "__opts__": self.LOCAL_OPTS,
        }
        return {saltify: saltify_globals}

    def test_create_no_deploy(self):
        """
        Test if deployment fails. This is the most basic test as saltify doesn't contain much logic
        """
        with patch("salt.cloud.clouds.saltify._verify", MagicMock(return_value=True)):
            vm = {"deploy": False, "driver": "saltify", "name": "dummy"}
            self.assertTrue(saltify.create(vm))

    def test_create_and_deploy(self):
        """
        Test if deployment can be done.
        """
        mock_cmd = MagicMock(return_value=True)
        with patch.dict(
            "salt.cloud.clouds.saltify.__utils__", {"cloud.bootstrap": mock_cmd}
        ):
            vm_ = {
                "deploy": True,
                "driver": "saltify",
                "name": "new2",
                "profile": "testprofile2",
            }
            result = saltify.create(vm_)
            mock_cmd.assert_called_once_with(vm_, ANY)
            self.assertTrue(result)

    def test_create_no_ssh_host(self):
        """
        Test that ssh_host is set to the vm name if not defined
        """
        mock_cmd = MagicMock(return_value=True)
        with patch.dict(
            "salt.cloud.clouds.saltify.__utils__", {"cloud.bootstrap": mock_cmd}
        ):
            vm_ = {
                "deploy": True,
                "driver": "saltify",
                "name": "new2",
                "profile": "testprofile2",
            }
            result = saltify.create(vm_)
            mock_cmd.assert_called_once_with(vm_, ANY)
            assert result
            # Make sure that ssh_host was added to the vm. Note that this is
            # done in two asserts so that the failure is more explicit about
            # what is wrong. If ssh_host wasn't inserted in the vm_ dict, the
            # failure would be a KeyError, which would be harder to
            # troubleshoot.
            assert "ssh_host" in vm_
            assert vm_["ssh_host"] == "new2"

    def test_create_wake_on_lan(self):
        """
        Test if wake on lan works
        """
        mock_sleep = MagicMock()
        mock_cmd = MagicMock(return_value=True)
        mm_cmd = MagicMock(return_value={"friend1": True})
        with salt.client.LocalClient() as lcl:
            lcl.cmd = mm_cmd
            with patch("time.sleep", mock_sleep):
                with patch("salt.client.LocalClient", return_value=lcl):
                    with patch.dict(
                        "salt.cloud.clouds.saltify.__utils__",
                        {"cloud.bootstrap": mock_cmd},
                    ):
                        vm_ = {
                            "deploy": True,
                            "driver": "saltify",
                            "name": "new1",
                            "profile": "testprofile3",
                        }
                        result = saltify.create(vm_)
                        mock_cmd.assert_called_once_with(vm_, ANY)
                        mm_cmd.assert_called_with(
                            "friend1", "network.wol", ["aa-bb-cc-dd-ee-ff"]
                        )
                        # The test suite might call time.sleep, look for any call
                        # that has the expected wait time.
                        mock_sleep.assert_any_call(0.01)
                        self.assertTrue(result)

    def test_avail_locations(self):
        """
        Test the avail_locations will always return {}
        """
        self.assertEqual(saltify.avail_locations(), {})

    def test_avail_sizes(self):
        """
        Test the avail_sizes will always return {}
        """
        self.assertEqual(saltify.avail_sizes(), {})

    def test_avail_images(self):
        """
        Test the avail_images will return profiles
        """
        testlist = list(TEST_PROFILE_NAMES)  # copy
        self.assertEqual(saltify.avail_images()["Profiles"].sort(), testlist.sort())

    def test_list_nodes(self):
        """
        Test list_nodes will return required fields only
        """
        testgrains = {
            "nodeX1": {
                "id": "nodeX1",
                "ipv4": ["127.0.0.1", "192.1.2.22", "172.16.17.18"],
                "ipv6": ["::1", "fdef:bad:add::f00", "3001:DB8::F00D"],
                "salt-cloud": {
                    "driver": "saltify",
                    "provider": "saltyfy",
                    "profile": "testprofile2",
                },
                "extra_stuff": "does not belong",
            }
        }
        expected_result = {
            "nodeX1": {
                "id": "nodeX1",
                "image": "testprofile2",
                "private_ips": ["172.16.17.18", "fdef:bad:add::f00"],
                "public_ips": ["192.1.2.22", "3001:DB8::F00D"],
                "size": "",
                "state": "running",
            }
        }
        mm_cmd = MagicMock(return_value=testgrains)
        with salt.client.LocalClient() as lcl:
            lcl.cmd = mm_cmd
            with patch("salt.client.LocalClient", return_value=lcl):
                self.assertEqual(saltify.list_nodes(), expected_result)

    def test_saltify_reboot(self):
        mm_cmd = MagicMock(return_value=True)
        with salt.client.LocalClient() as lcl:
            lcl.cmd = mm_cmd
            with patch("salt.client.LocalClient", return_value=lcl):
                result = saltify.reboot("nodeS1", "action")
                mm_cmd.assert_called_with("nodeS1", "system.reboot")
                self.assertTrue(result)

    def test_saltify_destroy(self):
        # destroy calls local.cmd several times and expects
        # different results, so we will provide a list of
        # results. Each call will get the next value.
        # NOTE: this assumes that the call order never changes,
        # so to keep things simple, we will not use remove_config...
        result_list = [
            {
                "nodeS1": {  # first call is grains.get
                    "driver": "saltify",
                    "provider": "saltify",
                    "profile": "testprofile2",
                }
            },
            #  Note:
            #    testprofile2 has remove_config_on_destroy: False
            #    and shutdown_on_destroy: True
            {
                "nodeS1": (  # last call shuts down the minion
                    "a system.shutdown worked message"
                )
            },
        ]
        mm_cmd = MagicMock(side_effect=result_list)
        with salt.client.LocalClient() as lcl:
            lcl.cmd = mm_cmd
            with patch("salt.client.LocalClient", return_value=lcl):
                result = saltify.destroy("nodeS1", "action")
                mm_cmd.assert_called_with("nodeS1", "system.shutdown")
                self.assertTrue(result)
