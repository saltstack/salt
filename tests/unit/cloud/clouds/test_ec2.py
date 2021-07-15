import os
import tempfile

import salt.crypt
import salt.utils.files
from salt.cloud.clouds import ec2
from salt.exceptions import SaltCloudSystemExit
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import PropertyMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf
from tests.unit.test_crypt import PRIVKEY_DATA

PASS_DATA = (
    b"qOjCKDlBdcNEbJ/J8eRl7sH+bYIIm4cvHHY86gh2NEUnufFlFo0gGVTZR05Fj0cw3n/w7gR"
    b"urNXz5JoeSIHVuNI3YTwzL9yEAaC0kuy8EbOlO2yx8yPGdfml9BRwOV7A6b8UFo9co4H7fz"
    b"DdScMKU2yzvRYvp6N6Q2cJGBmPsemnXWWusb+1vZVWxcRAQmG3ogF6Z5rZSYAYH0N4rqJgH"
    b"mQfzuyb+jrBvV/IOoV1EdO9jGSH9338aS47NjrmNEN/SpnS6eCWZUwwyHbPASuOvWiY4QH/"
    b"0YZC6EGccwiUmt0ZOxIynk+tEyVPTkiS0V8RcZK6YKqMWHpKmPtLBzfuoA=="
)


class EC2TestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for salt.cloud.clouds.ec2 module.
    """

    def setUp(self):
        super().setUp()
        with tempfile.NamedTemporaryFile(
            dir=RUNTIME_VARS.TMP, suffix=".pem", delete=True
        ) as fp:
            self.key_file = fp.name

    def tearDown(self):
        super().tearDown()
        if os.path.exists(self.key_file):
            os.remove(self.key_file)

    def setup_loader_modules(self):
        return {ec2: {"__opts__": {}}}

    def test__validate_key_path_and_mode(self):
        # Key file exists
        with patch("os.path.exists", return_value=True):
            with patch("os.stat") as patched_stat:
                type(patched_stat.return_value).st_mode = PropertyMock(
                    return_value=0o644
                )
                self.assertRaises(
                    SaltCloudSystemExit, ec2._validate_key_path_and_mode, "key_file"
                )

                type(patched_stat.return_value).st_mode = PropertyMock(
                    return_value=0o600
                )
                self.assertTrue(ec2._validate_key_path_and_mode("key_file"))

                type(patched_stat.return_value).st_mode = PropertyMock(
                    return_value=0o400
                )
                self.assertTrue(ec2._validate_key_path_and_mode("key_file"))

        # Key file does not exist
        with patch("os.path.exists", return_value=False):
            self.assertRaises(
                SaltCloudSystemExit, ec2._validate_key_path_and_mode, "key_file"
            )

    @skipIf(not salt.crypt.HAS_M2 and not salt.crypt.HAS_CRYPTO, "Needs crypto library")
    @patch("salt.cloud.clouds.ec2._get_node")
    @patch("salt.cloud.clouds.ec2.get_location")
    @patch("salt.cloud.clouds.ec2.get_provider")
    @patch("salt.utils.aws.query")
    def test_get_password_data(self, query, get_provider, get_location, _get_node):
        query.return_value = [{"passwordData": PASS_DATA}]
        _get_node.return_value = {"instanceId": "i-abcdef"}
        get_location.return_value = "us-west2"
        get_provider.return_value = "ec2"
        with salt.utils.files.fopen(self.key_file, "w") as fp:
            fp.write(PRIVKEY_DATA)
        ret = ec2.get_password_data(
            name="i-abcddef", kwargs={"key_file": self.key_file}, call="action"
        )
        assert ret["passwordData"] == PASS_DATA
        assert ret["password"] == "testp4ss!"

    @patch("salt.cloud.clouds.ec2.config.get_cloud_config_value")
    @patch("salt.cloud.clouds.ec2.get_location")
    @patch("salt.cloud.clouds.ec2.get_provider")
    @patch("salt.cloud.clouds.ec2.aws.query")
    def test_get_imageid(self, aws_query, get_provider, get_location, config):
        """
        test querying imageid function
        """
        vm = {}
        ami = "ami-1234"
        config.return_value = "test/*"
        get_location.return_value = "us-west2"
        get_provider.return_value = "ec2"
        aws_query.return_value = [{"imageId": ami}]

        # test image filter
        self.assertEqual(ec2.get_imageid(vm), ami)

        # test ami-image
        config.return_value = ami
        self.assertEqual(ec2.get_imageid(vm), ami)

        # we should have only ran aws.query once when testing the aws filter
        aws_query.assert_called_once()

    @patch("salt.cloud.clouds.ec2.config.get_cloud_config_value")
    @patch("salt.cloud.clouds.ec2.get_location")
    @patch("salt.cloud.clouds.ec2.get_availability_zone")
    @patch("salt.cloud.clouds.ec2.get_provider")
    @patch("salt.cloud.clouds.ec2.get_spot_config")
    @patch("salt.cloud.clouds.ec2._param_from_config")
    @patch("salt.cloud.clouds.ec2.securitygroupid")
    def test_termination_protection(
        self,
        securitygroupid,
        _param_from_config,
        get_spot_config,
        get_provider,
        get_availability_zone,
        get_location,
        config,
    ):
        """
        Verify that `set_termination_protection` updates the right parameters
        """
        vm = {"name": "taco"}
        set_del_root_vol_on_destroy = "yes"
        termination_protection = True
        config.side_effect = (
            [None] * 2
            + ["test/*"]
            + [None] * 13
            + [set_del_root_vol_on_destroy, termination_protection]
        )
        get_location.return_value = "us-west2"
        get_availability_zone.return_value = None
        get_provider.return_value = "ec2"
        get_spot_config.return_value = None
        securitygroupid.return_value = None

        self.assertRaises(
            salt.exceptions.SaltCloudConfigError, ec2.request_instance, vm
        )
        _param_from_config.assert_called_once_with("DisableApiTermination", True)

    @patch("salt.cloud.clouds.ec2.config.get_cloud_config_value")
    @patch("salt.cloud.clouds.ec2.get_location")
    @patch("salt.cloud.clouds.ec2.get_availability_zone")
    @patch("salt.cloud.clouds.ec2.get_provider")
    @patch("salt.cloud.clouds.ec2.get_spot_config")
    @patch("salt.cloud.clouds.ec2.securitygroupid")
    def test_termination_protection_exception(
        self,
        securitygroupid,
        get_spot_config,
        get_provider,
        get_availability_zone,
        get_location,
        config,
    ):
        """
        Verify improper `set_termination_protection` parameters raises an exception
        """
        vm = {"name": "taco"}
        termination_protection = "not a bool"
        config.side_effect = (
            [None] * 2 + ["test/*"] + [None] * 14 + [termination_protection]
        )
        get_location.return_value = "us-west2"
        get_availability_zone.return_value = None
        get_provider.return_value = "ec2"
        get_spot_config.return_value = None
        securitygroupid.return_value = None

        self.assertRaises(
            salt.exceptions.SaltCloudConfigError, ec2.request_instance, vm
        )

    @patch("salt.cloud.clouds.ec2.config.get_cloud_config_value")
    @patch("salt.cloud.clouds.ec2.get_location")
    @patch("salt.cloud.clouds.ec2.get_provider")
    @patch("salt.cloud.clouds.ec2.aws.query")
    def test_get_subnetname_id(self, aws_query, get_provider, get_location, config):
        """
        test querying subnetid function
        """
        vm = {}
        subnetid = "subnet-5678"
        subnetname = "valid-subnet-with-name"
        config.return_value = subnetname
        get_location.return_value = "us-west-2"
        get_provider.return_value = "ec2"

        # test for returns that include subnets with missing Name tags, see Issue 44330
        aws_query.return_value = [
            {"subnetId": "subnet-1234"},
            {
                "subnetId": subnetid,
                "tagSet": {"item": {"key": "Name", "value": subnetname}},
            },
        ]

        # test subnetname lookup
        self.assertEqual(ec2._get_subnetname_id(subnetname), subnetid)
