import shutil

import pytest

import salt.loader
import salt.roster.ansible as ansible
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_if_binaries_missing("ansible-inventory"),
]


@pytest.fixture
def roster_opts():
    return {"roster_defaults": {"passwd": "test123"}}


@pytest.fixture
def configure_loader_modules(temp_salt_master, roster_opts):
    opts = temp_salt_master.config.copy()
    utils = salt.loader.utils(opts, whitelist=["json", "stringutils", "ansible"])
    runner = salt.loader.runner(opts, utils=utils, whitelist=["salt"])
    return {
        ansible: {"__utils__": utils, "__opts__": roster_opts, "__runner__": runner}
    }


@pytest.fixture
def expected_targets_return():
    return {
        "host1": {
            "host": "host1",
            "passwd": "test123",
            "minion_opts": {
                "escape_pods": 2,
                "halon_system_timeout": 30,
                "self_destruct_countdown": 60,
                "some_server": "foo.southeast.example.com",
            },
        },
        "host2": {
            "host": "host2",
            "passwd": "test123",
            "minion_opts": {
                "escape_pods": 2,
                "halon_system_timeout": 30,
                "self_destruct_countdown": 60,
                "some_server": "foo.southeast.example.com",
            },
        },
        "host3": {
            "host": "host3",
            "passwd": "test123",
            "minion_opts": {
                "escape_pods": 2,
                "halon_system_timeout": 30,
                "self_destruct_countdown": 60,
                "some_server": "foo.southeast.example.com",
            },
        },
    }


@pytest.fixture(scope="module")
def roster_dir(tmp_path_factory):
    dpath = tmp_path_factory.mktemp("roster")
    roster_py_contents = """
    #!/usr/bin/env python

    import json
    import sys

    inventory = {
        "usa": {"children": ["southeast"]},
        "southeast": {
            "children": ["atlanta", "raleigh"],
            "vars": {
                "some_server": "foo.southeast.example.com",
                "halon_system_timeout": 30,
                "self_destruct_countdown": 60,
                "escape_pods": 2,
            },
        },
        "raleigh": ["host2", "host3"],
        "atlanta": ["host1", "host2"],
    }
    hostvars = {"host1": {}, "host2": {}, "host3": {}}

    if "--host" in sys.argv:
        print(json.dumps(hostvars.get(sys.argv[-1], {})))
    if "--list" in sys.argv:
        print(json.dumps(inventory))
    """
    roster_ini_contents = """
    [atlanta]
    host1
    host2

    [raleigh]
    host2
    host3

    [southeast:children]
    atlanta
    raleigh

    [southeast:vars]
    some_server=foo.southeast.example.com
    halon_system_timeout=30
    self_destruct_countdown=60
    escape_pods=2

    [usa:children]
    southeast
    """
    roster_yaml_contents = """
    atlanta:
      hosts:
        host1:
        host2:
    raleigh:
      hosts:
        host2:
        host3:
    southeast:
      children:
        atlanta:
        raleigh:
      vars:
        some_server: foo.southeast.example.com
        halon_system_timeout: 30
        self_destruct_countdown: 60
        escape_pods: 2
    usa:
      children:
        southeast:
    """
    with pytest.helpers.temp_file(
        "roster.py", roster_py_contents, directory=dpath
    ) as py_roster:
        py_roster.chmod(0o755)
        with pytest.helpers.temp_file(
            "roster.ini", roster_ini_contents, directory=dpath
        ), pytest.helpers.temp_file(
            "roster.yml", roster_yaml_contents, directory=dpath
        ):
            try:
                yield dpath
            finally:
                shutil.rmtree(str(dpath), ignore_errors=True)


@pytest.mark.parametrize(
    "which_value",
    [False, None],
)
def test_virtual_returns_False_if_ansible_inventory_doesnt_exist(which_value):
    with patch("salt.utils.path.which", autospec=True, return_value=which_value):
        assert ansible.__virtual__() == (False, "Install `ansible` to use inventory")


def test_ini(roster_opts, roster_dir, expected_targets_return):
    roster_opts["roster_file"] = str(roster_dir / "roster.ini")
    with patch.dict(ansible.__opts__, roster_opts):
        ret = ansible.targets("*")
        assert ret == expected_targets_return


def test_yml(roster_opts, roster_dir, expected_targets_return):
    roster_opts["roster_file"] = str(roster_dir / "roster.yml")
    with patch.dict(ansible.__opts__, roster_opts):
        ret = ansible.targets("*")
        assert ret == expected_targets_return


def test_script(roster_opts, roster_dir, expected_targets_return):
    roster_opts["roster_file"] = str(roster_dir / "roster.py")
    with patch.dict(ansible.__opts__, roster_opts):
        ret = ansible.targets("*")
        assert ret == expected_targets_return
