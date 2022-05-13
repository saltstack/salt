import pytest
from salt.cloud.clouds import ec2

pytestmark = [
    pytest.mark.windows_whitelisted,
]


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
