"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import pytest
import salt.states.gnomedesktop as gnomedesktop


@pytest.fixture
def configure_loader_modules():
    return {gnomedesktop: {}}


@pytest.fixture
def ret_results():
    return {"name": "salt", "result": True, "comment": "", "changes": {}}


def test_wm_preferences(ret_results):
    """
    Test to sets values in the org.gnome.desktop.wm.preferences schema
    """
    assert gnomedesktop.wm_preferences(ret_results["name"]) == ret_results


def test_desktop_lockdown(ret_results):
    """
    Test to sets values in the org.gnome.desktop.lockdown schema
    """
    assert gnomedesktop.desktop_lockdown(ret_results["name"]) == ret_results


def test_desktop_interface(ret_results):
    """
    Test to sets values in the org.gnome.desktop.interface schema
    """
    assert gnomedesktop.desktop_interface(ret_results["name"]) == ret_results
