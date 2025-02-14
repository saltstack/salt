"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.states.gnomedesktop
"""

import pytest

import salt.states.gnomedesktop as gnomedesktop


@pytest.fixture
def configure_loader_modules():
    return {gnomedesktop: {}}


def test_wm_preferences():
    """
    Test to sets values in the org.gnome.desktop.wm.preferences schema
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    assert gnomedesktop.wm_preferences(name) == ret


def test_desktop_lockdown():
    """
    Test to sets values in the org.gnome.desktop.lockdown schema
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    assert gnomedesktop.desktop_lockdown(name) == ret


def test_desktop_interface():
    """
    Test to sets values in the org.gnome.desktop.interface schema
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    assert gnomedesktop.desktop_interface(name) == ret
