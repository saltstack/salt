import pytest

import salt.crypt
import salt.utils.files
from salt.cloud.clouds import ec2
from salt.exceptions import SaltCloudSystemExit
from tests.support.mock import PropertyMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def configure_loader_modules():
    return {ec2: {"__opts__": {}}}


def test__load_params_size():
    """
    Test that "Size" is added to params
    """
    kwargs = {"zone": "us-west-2", "size": 10}
    expected = {"Action": "CreateVolume", "AvailabilityZone": "us-west-2", "Size": 10}
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test__load_params_snapshot():
    """
    Test that "SnapshotID" is added to params
    """
    kwargs = {"zone": "us-west-2", "snapshot": 1234}
    expected = {
        "Action": "CreateVolume",
        "AvailabilityZone": "us-west-2",
        "SnapshotId": 1234,
    }
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test__load_params_type():
    """
    Test that "VolumeType" is added to params
    """
    kwargs = {"zone": "us-west-2", "type": "gp2"}
    expected = {
        "Action": "CreateVolume",
        "AvailabilityZone": "us-west-2",
        "VolumeType": "gp2",
    }
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test__load_params_type_io1():
    """
    Test that "Iops" is added to params when type is io1
    """
    kwargs = {"zone": "us-west-2", "type": "io1", "iops": 1000}
    expected = {
        "Action": "CreateVolume",
        "AvailabilityZone": "us-west-2",
        "VolumeType": "io1",
        "Iops": 1000,
    }
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test__load_params_type_io2():
    """
    Test that "Iops" is added to params when type is io2
    """
    kwargs = {"zone": "us-west-2", "type": "io2", "iops": 1000}
    expected = {
        "Action": "CreateVolume",
        "AvailabilityZone": "us-west-2",
        "VolumeType": "io2",
        "Iops": 1000,
    }
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test__load_params_encrypted():
    """
    Test that "Encrypted" is added to params
    """
    kwargs = {"zone": "us-west-2", "encrypted": True}
    expected = {
        "Action": "CreateVolume",
        "AvailabilityZone": "us-west-2",
        "Encrypted": True,
    }
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test__load_params_encrypted_kmskeyid():
    """
    Test that "KmsKeyId" is added to params when passed with encrypted
    """
    kwargs = {"zone": "us-west-2", "encrypted": True, "kmskeyid": "keyid"}
    expected = {
        "Action": "CreateVolume",
        "AvailabilityZone": "us-west-2",
        "Encrypted": True,
        "KmsKeyId": "keyid",
    }
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test__load_params_kmskeyid_without_encrypted():
    """
    Test that "KmsKeyId" is not added to params when encrypted is not passed
    """
    kwargs = {"zone": "us-west-2", "kmskeyid": "keyid"}
    expected = {
        "Action": "CreateVolume",
        "AvailabilityZone": "us-west-2",
    }
    result = ec2._load_params(kwargs=kwargs)
    assert result == expected


def test_create_volume_call_not_function():
    """
    Test check for function
    """
    ret = ec2.create_volume(kwargs={}, call="not a function")
    assert ret is False


def test_create_volume_no_zone():
    """
    Test that "zone" must be in kwargs
    """
    ret = ec2.create_volume(kwargs={}, call="function")
    assert ret is False


def test_create_volume_kmskeyid_without_encrypted():
    """
    Test that returns False if kmskeyid is passed without encrypted
    """
    kwargs = {"zone": "us-west-2", "kmskeyid": "keyid"}
    ret = ec2.create_volume(kwargs=kwargs, call="function")
    assert ret is False


def test_create_volume_missing_iops_io1():
    """
    Test that iops must be in kwargs if type is io1
    """
    kwargs = {"zone": "us-west-2", "type": "io1"}
    ret = ec2.create_volume(kwargs=kwargs, call="function")
    assert ret is False


def test_create_volume_missing_iops_io2():
    """
    Test that iops must be in kwargs if type is io2
    """
    kwargs = {"zone": "us-west-2", "type": "io1"}
    ret = ec2.create_volume(kwargs=kwargs, call="function")
    assert ret is False


def test__validate_key_path_and_mode():
    # Key file exists
    with patch("os.path.exists", return_value=True):
        with patch("os.stat") as patched_stat:
            type(patched_stat.return_value).st_mode = PropertyMock(return_value=0o644)
            with pytest.raises(SaltCloudSystemExit):
                ec2._validate_key_path_and_mode("key_file")

            type(patched_stat.return_value).st_mode = PropertyMock(return_value=0o600)
            assert ec2._validate_key_path_and_mode("key_file") is True

            type(patched_stat.return_value).st_mode = PropertyMock(return_value=0o400)
            assert ec2._validate_key_path_and_mode("key_file") is True

    # Key file does not exist
    with patch("os.path.exists", return_value=False):
        with pytest.raises(SaltCloudSystemExit):
            ec2._validate_key_path_and_mode("key_file")


@pytest.mark.skipif(
    not salt.crypt.HAS_M2 and not salt.crypt.HAS_CRYPTO, reason="Needs crypto library"
)
def test_get_password_data(tmp_path):
    key_file = str(tmp_path / "keyfile.pem")

    pass_data = (
        b"qOjCKDlBdcNEbJ/J8eRl7sH+bYIIm4cvHHY86gh2NEUnufFlFo0gGVTZR05Fj0cw3n/w7gR"
        b"urNXz5JoeSIHVuNI3YTwzL9yEAaC0kuy8EbOlO2yx8yPGdfml9BRwOV7A6b8UFo9co4H7fz"
        b"DdScMKU2yzvRYvp6N6Q2cJGBmPsemnXWWusb+1vZVWxcRAQmG3ogF6Z5rZSYAYH0N4rqJgH"
        b"mQfzuyb+jrBvV/IOoV1EdO9jGSH9338aS47NjrmNEN/SpnS6eCWZUwwyHbPASuOvWiY4QH/"
        b"0YZC6EGccwiUmt0ZOxIynk+tEyVPTkiS0V8RcZK6YKqMWHpKmPtLBzfuoA=="
    )

    privkey_data = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA75GR6ZTv5JOv90Vq8tKhKC7YQnhDIo2hM0HVziTEk5R4UQBW\n"
        "a0CKytFMbTONY2msEDwX9iA0x7F5Lgj0X8eD4ZMsYqLzqjWMekLC8bjhxc+EuPo9\n"
        "Dygu3mJ2VgRC7XhlFpmdo5NN8J2E7B/CNB3R4hOcMMZNZdi0xLtFoTfwU61UPfFX\n"
        "14mV2laqLbvDEfQLJhUTDeFFV8EN5Z4H1ttLP3sMXJvc3EvM0JiDVj4l1TWFUHHz\n"
        "eFgCA1Im0lv8i7PFrgW7nyMfK9uDSsUmIp7k6ai4tVzwkTmV5PsriP1ju88Lo3MB\n"
        "4/sUmDv/JmlZ9YyzTO3Po8Uz3Aeq9HJWyBWHAQIDAQABAoIBAGOzBzBYZUWRGOgl\n"
        "IY8QjTT12dY/ymC05GM6gMobjxuD7FZ5d32HDLu/QrknfS3kKlFPUQGDAbQhbbb0\n"
        "zw6VL5NO9mfOPO2W/3FaG1sRgBQcerWonoSSSn8OJwVBHMFLG3a+U1Zh1UvPoiPK\n"
        "S734swIM+zFpNYivGPvOm/muF/waFf8tF/47t1cwt/JGXYQnkG/P7z0vp47Irpsb\n"
        "Yjw7vPe4BnbY6SppSxscW3KoV7GtJLFKIxAXbxsuJMF/rYe3O3w2VKJ1Sug1VDJl\n"
        "/GytwAkSUer84WwP2b07Wn4c5pCnmLslMgXCLkENgi1NnJMhYVOnckxGDZk54hqP\n"
        "9RbLnkkCgYEA/yKuWEvgdzYRYkqpzB0l9ka7Y00CV4Dha9Of6GjQi9i4VCJ/UFVr\n"
        "UlhTo5y0ZzpcDAPcoZf5CFZsD90a/BpQ3YTtdln2MMCL/Kr3QFmetkmDrt+3wYnX\n"
        "sKESfsa2nZdOATRpl1antpwyD4RzsAeOPwBiACj4fkq5iZJBSI0bxrMCgYEA8GFi\n"
        "qAjgKh81/Uai6KWTOW2kX02LEMVRrnZLQ9VPPLGid4KZDDk1/dEfxjjkcyOxX1Ux\n"
        "Klu4W8ZEdZyzPcJrfk7PdopfGOfrhWzkREK9C40H7ou/1jUecq/STPfSOmxh3Y+D\n"
        "ifMNO6z4sQAHx8VaHaxVsJ7SGR/spr0pkZL+NXsCgYEA84rIgBKWB1W+TGRXJzdf\n"
        "yHIGaCjXpm2pQMN3LmP3RrcuZWm0vBt94dHcrR5l+u/zc6iwEDTAjJvqdU4rdyEr\n"
        "tfkwr7v6TNlQB3WvpWanIPyVzfVSNFX/ZWSsAgZvxYjr9ixw6vzWBXOeOb/Gqu7b\n"
        "cvpLkjmJ0wxDhbXtyXKhZA8CgYBZyvcQb+hUs732M4mtQBSD0kohc5TsGdlOQ1AQ\n"
        "McFcmbpnzDghkclyW8jzwdLMk9uxEeDAwuxWE/UEvhlSi6qdzxC+Zifp5NBc0fVe\n"
        "7lMx2mfJGxj5CnSqQLVdHQHB4zSXkAGB6XHbBd0MOUeuvzDPfs2voVQ4IG3FR0oc\n"
        "3/znuwKBgQChZGH3McQcxmLA28aUwOVbWssfXKdDCsiJO+PEXXlL0maO3SbnFn+Q\n"
        "Tyf8oHI5cdP7AbwDSx9bUfRPjg9dKKmATBFr2bn216pjGxK0OjYOCntFTVr0psRB\n"
        "CrKg52Qrq71/2l4V2NLQZU40Dr1bN9V+Ftd9L0pvpCAEAWpIbLXGDw==\n"
        "-----END RSA PRIVATE KEY-----"
    )

    with patch(
        "salt.cloud.clouds.ec2._get_node", return_value={"instanceId": "i-abcdef"}
    ):
        with patch("salt.cloud.clouds.ec2.get_location", return_value="us-west2"):
            with patch("salt.cloud.clouds.ec2.get_provider", return_value="ec2"):
                with patch(
                    "salt.utils.aws.query", return_value=[{"passwordData": pass_data}]
                ):
                    with salt.utils.files.fopen(key_file, "w") as fp:
                        fp.write(privkey_data)
                    ret = ec2.get_password_data(
                        name="i-abcddef", kwargs={"key_file": key_file}, call="action"
                    )
                    assert ret["passwordData"] == pass_data
                    assert ret["password"] == "testp4ss!"


def test_get_imageid():
    """
    test querying imageid function
    """
    vm = {}
    ami = "ami-1234"
    with patch("salt.cloud.clouds.ec2.get_location", return_value="us-west2"):
        with patch("salt.cloud.clouds.ec2.get_provider", return_value="ec2"):
            with patch(
                "salt.cloud.clouds.ec2.aws.query", return_value=[{"imageId": ami}]
            ) as aws_query:
                with patch(
                    "salt.cloud.clouds.ec2.config.get_cloud_config_value",
                    return_value="test/*",
                ):
                    # test image filter
                    assert ec2.get_imageid(vm) == ami

                with patch(
                    "salt.cloud.clouds.ec2.config.get_cloud_config_value",
                    return_value=ami,
                ):
                    # test ami-image
                    assert ec2.get_imageid(vm) == ami
                    # we should have only ran aws.query once when testing the aws filter
                    aws_query.assert_called_once()


def test_termination_protection():
    """
    Verify that `set_termination_protection` updates the right parameters
    """
    vm = {"name": "taco"}
    set_del_root_vol_on_destroy = "yes"
    termination_protection = True
    config_side_effect = (
        [None] * 2
        + ["test/*"]
        + [None] * 13
        + [set_del_root_vol_on_destroy, termination_protection]
    )
    with patch(
        "salt.cloud.clouds.ec2.config.get_cloud_config_value",
        side_effect=config_side_effect,
    ):
        with patch("salt.cloud.clouds.ec2.get_location", return_value="us-west2"):
            with patch(
                "salt.cloud.clouds.ec2.get_availability_zone", return_value=None
            ):
                with patch("salt.cloud.clouds.ec2.get_provider", return_value="ec2"):
                    with patch(
                        "salt.cloud.clouds.ec2.get_spot_config", return_value=None
                    ):
                        with patch(
                            "salt.cloud.clouds.ec2._param_from_config"
                        ) as _param_from_config:
                            with patch(
                                "salt.cloud.clouds.ec2.securitygroupid",
                                return_value=None,
                            ):
                                with pytest.raises(
                                    salt.exceptions.SaltCloudConfigError
                                ):
                                    ec2.request_instance(vm)
                                    _param_from_config.assert_called_once_with(
                                        "DisableApiTermination", True
                                    )


def test_termination_protection_exception():
    """
    Verify improper `set_termination_protection` parameters raises an exception
    """
    vm = {"name": "taco"}
    termination_protection = "not a bool"
    config_side_effect = (
        [None] * 2 + ["test/*"] + [None] * 14 + [termination_protection]
    )
    with patch(
        "salt.cloud.clouds.ec2.config.get_cloud_config_value",
        side_effect=config_side_effect,
    ):
        with patch("salt.cloud.clouds.ec2.get_location", return_value="us-west2"):
            with patch(
                "salt.cloud.clouds.ec2.get_availability_zone", return_value=None
            ):
                with patch("salt.cloud.clouds.ec2.get_provider", return_value="ec2"):
                    with patch(
                        "salt.cloud.clouds.ec2.get_spot_config", return_value=None
                    ):
                        with patch(
                            "salt.cloud.clouds.ec2.securitygroupid", return_value=None
                        ):
                            with pytest.raises(salt.exceptions.SaltCloudConfigError):
                                ec2.request_instance(vm)


def test_get_subnetname_id():
    """
    test querying subnetid function
    """
    vm = {}
    subnetid = "subnet-5678"
    subnetname = "valid-subnet-with-name"
    aws_query_return_value = [
        {"subnetId": "subnet-1234"},
        {
            "subnetId": subnetid,
            "tagSet": {"item": {"key": "Name", "value": subnetname}},
        },
    ]
    with patch(
        "salt.cloud.clouds.ec2.config.get_cloud_config_value", return_value=subnetname
    ):
        with patch("salt.cloud.clouds.ec2.get_location", return_value="us-west-2"):
            with patch("salt.cloud.clouds.ec2.get_provider", return_value="ec2"):
                with patch(
                    "salt.cloud.clouds.ec2.aws.query",
                    return_value=aws_query_return_value,
                ):
                    # test for returns that include subnets with missing Name tags, see Issue 44330
                    assert ec2._get_subnetname_id(subnetname) == subnetid
