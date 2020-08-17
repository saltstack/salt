# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>

from __future__ import absolute_import, print_function, unicode_literals

import os

import pytest
import salt.modules.ansiblegate as ansible
import salt.utils.platform
from salt.exceptions import LoaderError
from tests.support.mock import MagicMock, patch

pytestmark = pytest.mark.skipif(
    salt.utils.platform.is_windows(), reason="Not supported on Windows"
)


@pytest.fixture
def resolver():
    _resolver = ansible.AnsibleModuleResolver({})
    _resolver._modules_map = {
        "one.two.three": os.sep + os.path.join("one", "two", "three.py"),
        "four.five.six": os.sep + os.path.join("four", "five", "six.py"),
        "three.six.one": os.sep + os.path.join("three", "six", "one.py"),
    }
    return _resolver


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {ansible: {}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


def test_ansible_module_help(resolver):
    """
    Test help extraction from the module
    :return:
    """

    class Module(object):
        """
        An ansible module mock.
        """

        __name__ = "foo"
        DOCUMENTATION = """
---
one:
    text here
---
two:
    text here
description:
    describe the second part
    """

    with patch.object(ansible, "_resolver", resolver), patch.object(
        ansible._resolver, "load_module", MagicMock(return_value=Module())
    ):
        ret = ansible.help("dummy")
        assert sorted(
            ret.get('Available sections on module "{0}"'.format(Module().__name__))
        ) == ["one", "two"]
        assert ret.get("Description") == "describe the second part"


def test_module_resolver_modlist(resolver):
    """
    Test Ansible resolver modules list.
    :return:
    """
    assert resolver.get_modules_list() == [
        "four.five.six",
        "one.two.three",
        "three.six.one",
    ]
    for ptr in ["five", "fi", "ve"]:
        assert resolver.get_modules_list(ptr) == ["four.five.six"]
    for ptr in ["si", "ix", "six"]:
        assert resolver.get_modules_list(ptr) == ["four.five.six", "three.six.one"]
    assert resolver.get_modules_list("one") == ["one.two.three", "three.six.one"]
    assert resolver.get_modules_list("one.two") == ["one.two.three"]
    assert resolver.get_modules_list("four") == ["four.five.six"]


def test_resolver_module_loader_failure(resolver):
    """
    Test Ansible module loader.
    :return:
    """
    mod = "four.five.six"
    with pytest.raises(ImportError) as import_error:
        resolver.load_module(mod)

    mod = "i.even.do.not.exist.at.all"
    with pytest.raises(LoaderError) as loader_error:
        resolver.load_module(mod)


def test_resolver_module_loader(resolver):
    """
    Test Ansible module loader.
    :return:
    """
    with patch("salt.modules.ansiblegate.importlib", MagicMock()), patch(
        "salt.modules.ansiblegate.importlib.import_module", lambda x: x
    ):
        assert resolver.load_module("four.five.six") == "ansible.modules.four.five.six"


def test_resolver_module_loader_import_failure(resolver):
    """
    Test Ansible module loader failure.
    :return:
    """
    with patch("salt.modules.ansiblegate.importlib", MagicMock()), patch(
        "salt.modules.ansiblegate.importlib.import_module", lambda x: x
    ):
        with pytest.raises(LoaderError) as loader_error:
            resolver.load_module("something.strange")


def test_virtual_function(resolver):
    """
    Test Ansible module __virtual__ when ansible is not installed on the minion.
    :return:
    """
    with patch("salt.modules.ansiblegate.ansible", None):
        assert ansible.__virtual__() == "ansible"
