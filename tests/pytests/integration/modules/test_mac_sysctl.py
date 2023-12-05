"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import os
import random

import pytest

import salt.utils.files
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def assign_cmd():
    return "net.inet.icmp.timestamp"


@pytest.fixture(scope="function")
def config_file():
    return "/etc/sysctl.conf"


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli, assign_cmd, config_file):
    has_conf = False
    ret = salt_call_cli.run("sysctl.get", assign_cmd, config_file)
    val = ret.data

    if val is None:
        pytest.skip(f"The call 'sysctl.get {assign_cmd}' returned: None")

    # If sysctl file is present, make a copy
    # Remove original file so we can replace it with test files
    if os.path.isfile(config_file):
        has_conf = True
        try:
            temp_sysctl_config = __copy_sysctl(config_file)
        except CommandExecutionError:
            msg = "Could not copy file: {0}"
            raise CommandExecutionError(msg.format(config_file))
        os.remove(config_file)

    try:
        yield val
    finally:
        ret = salt_call_cli.run("sysctl.get", assign_cmd)
        if ret.data != val:
            salt_call_cli.run("sysctl.assign", assign_cmd, val)

        if has_conf is True:
            # restore original sysctl file
            __restore_sysctl(config_file, temp_sysctl_config)

        if has_conf is False and os.path.isfile(config_file):
            # remove sysctl.conf created by tests
            os.remove(temp_sysctl_config)


def test_assign(salt_call_cli, assign_cmd, setup_teardown_vars):
    """
    Tests assigning a single sysctl parameter
    """
    val = setup_teardown_vars[0]

    try:
        rand = random.randint(0, 500)
        while rand == val:
            rand = random.randint(0, 500)
        salt_call_cli.run("sysctl.assign", assign_cmd, rand)
        ret = int(salt_call_cli.run("sysctl.get", assign_cmd))
        info = int(ret.data)
        try:
            assert rand == info
        except AssertionError:
            salt_call_cli.run("sysctl.assign", assign_cmd, val)
            raise
    except CommandExecutionError:
        salt_call_cli.run("sysctl.assign", assign_cmd, val)
        raise


def test_persist_new_file(salt_call_cli, assign_cmd, config_file):
    """
    Tests assigning a sysctl value to a system without a sysctl.conf file
    """
    # Always start with a clean/known sysctl.conf state
    if os.path.isfile(config_file):
        os.remove(config_file)
    try:
        salt_call_cli.run("sysctl.persist", assign_cmd, 10)
        line = f"{assign_cmd}={10}"
        found = __check_string(config_file, line)
        assert found
    except CommandExecutionError:
        os.remove(config_file)
        raise


def test_persist_already_set(salt_call_cli, config_file, setup_teardown_vars):
    """
    Tests assigning a sysctl value that is already set in sysctl.conf file
    """
    # Always start with a clean/known sysctl.conf state
    if os.path.isfile(config_file):
        os.remove(config_file)
    try:
        salt_call_cli.run("sysctl.persist", assign_cmd, 50)
        ret = salt_call_cli.run("sysctl.persist", assign_cmd, 50)
        assert ret.data == "Already set"
    except CommandExecutionError:
        os.remove(config_file)
        raise


def test_persist_apply_change(
    salt_call_cli, assign_cmd, config_file, setup_teardown_vars
):
    """
    Tests assigning a sysctl value and applying the change to system
    """
    val = setup_teardown_vars[0]

    # Always start with a clean/known sysctl.conf state
    if os.path.isfile(config_file):
        os.remove(config_file)
    try:
        rand = random.randint(0, 500)
        while rand == val:
            rand = random.randint(0, 500)
        salt_call_cli.run("sysctl.persist", assign_cmd, rand, apply_change=True)
        ret = salt_call_cli.run("sysctl.get", assign_cmd)
        info = int(ret.data)
        assert info == rand
    except CommandExecutionError:
        os.remove(config_file)
        raise


def __copy_sysctl(CONFIG):
    """
    Copies an existing sysconf file and returns temp file path. Copied
    file will be restored in tearDown
    """
    # Create new temporary file path and open needed files
    temp_path = salt.utils.files.mkstemp()
    with salt.utils.files.fopen(CONFIG, "r") as org_conf:
        with salt.utils.files.fopen(temp_path, "w") as temp_sysconf:
            # write sysctl lines to temp file
            for line in org_conf:
                temp_sysconf.write(line)
    return temp_path


def __restore_sysctl(sysctl_config, temp_sysctl_config):
    """
    Restores the original sysctl.conf file from temporary copy
    """
    # If sysctl testing file exists, delete it
    if os.path.isfile(sysctl_config):
        os.remove(sysctl_config)

    # write temp lines to sysctl file to restore
    with salt.utils.files.fopen(temp_sysctl_config, "r") as temp_sysctl:
        with salt.utils.files.fopen(sysctl_config, "w") as sysctl:
            for line in temp_sysctl:
                sysctl.write(line)

    # delete temporary file
    os.remove(temp_sysctl_config)


def __check_string(conf_file, to_find):
    """
    Returns True if given line is present in file
    """
    with salt.utils.files.fopen(conf_file, "r") as f_in:
        for line in f_in:
            if to_find in salt.utils.stringutils.to_unicode(line):
                return True
        return False
