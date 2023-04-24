"""
    :codeauthor: Piter Punk <piterpunk@slackware.com>
"""
import pytest

import salt.states.sysfs as sysfs
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {sysfs: {}}


def test_if_the_sysfs_attribute_exists():
    """
    Test sysfs.present for a non-existent attribute
    """
    name = "block/sda/queue/this_does_not_exist"
    value = "none"
    comment = "SysFS attribute {} doesn't exist.".format(name)
    ret = {"name": name, "result": False, "changes": {}, "comment": comment}

    mock_read = MagicMock(return_value=False)
    with patch.dict(sysfs.__salt__, {"sysfs.read": mock_read}):
        assert sysfs.present(name, value) == ret


def test_name_is_an_object_and_not_an_attribute():
    """
    Test sysfs.present targeting an object and not one of its attributes
    """
    name = "block/sda/queue"
    value = "none"
    comment = "{} is not a SysFS attribute.".format(name)
    ret = {"name": name, "result": False, "changes": {}, "comment": comment}

    read_from_sysfs = {
        "rotational": 1,
        "rq_affinity": 1,
        "scheduler": "[none] mq-deadline",
    }

    mock_read = MagicMock(return_value=read_from_sysfs)
    with patch.dict(sysfs.__salt__, {"sysfs.read": mock_read}):
        assert sysfs.present(name, value) == ret


def test_already_set():
    """
    Test sysfs.present with equal old and new values
    """
    name = "block/sda/queue"
    value = "none"
    comment = "SysFS attribute {} is already set.".format(name)
    ret = {"name": name, "result": True, "changes": {}, "comment": comment}

    read_from_sysfs = "[none] mq-deadline"

    mock_read = MagicMock(return_value=read_from_sysfs)
    with patch.dict(sysfs.__salt__, {"sysfs.read": mock_read}):
        assert sysfs.present(name, value) == ret


def test_set_new_value_with_test_equals_true():
    """
    Test sysfs.present setting a new value
    """
    name = "devices/system/cpu/cpufreq/policy0"
    value = "powersave"
    comment = "SysFS attribute {} set to be changed.".format(name)
    ret = {"name": name, "result": None, "changes": {}, "comment": comment}

    read_from_sysfs = "performance"

    mock_read = MagicMock(return_value=read_from_sysfs)
    with patch.dict(sysfs.__opts__, {"test": True}):
        with patch.dict(sysfs.__salt__, {"sysfs.read": mock_read}):
            assert sysfs.present(name, value) == ret


def test_set_new_value_with_success():
    """
    Test sysfs.present setting a new value
    """
    name = "block/sda/queue/scheduler"
    value = "mq-deadline"
    comment = "Updated SysFS attribute {} to {}".format(name, value)
    ret = {"name": name, "result": True, "changes": {name: value}, "comment": comment}

    read_from_sysfs = "[none] mq-deadline"

    mock_read = MagicMock(return_value=read_from_sysfs)
    with patch.dict(sysfs.__opts__, {"test": False}):
        with patch.dict(sysfs.__salt__, {"sysfs.read": mock_read}):
            mock_write = MagicMock(return_value=True)
            with patch.dict(sysfs.__salt__, {"sysfs.write": mock_write}):
                assert sysfs.present(name, value) == ret


def test_set_new_value_with_failure():
    """
    Test sysfs.present failure writing the value
    """
    name = "block/sda/queue/scheduler"
    value = "imaginary_scheduler"
    comment = "Failed to set {} to {}".format(name, value)
    ret = {"name": name, "result": False, "changes": {}, "comment": comment}

    read_from_sysfs = "[none] mq-deadline"

    mock_read = MagicMock(return_value=read_from_sysfs)
    with patch.dict(sysfs.__opts__, {"test": False}):
        with patch.dict(sysfs.__salt__, {"sysfs.read": mock_read}):
            mock_write = MagicMock(return_value=False)
            with patch.dict(sysfs.__salt__, {"sysfs.write": mock_write}):
                assert sysfs.present(name, value) == ret
