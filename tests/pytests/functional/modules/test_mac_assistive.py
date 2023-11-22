"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def assistive(modules):
    return modules.assistive


@pytest.fixture(scope="function")
def osa_script():
    yield "/usr/bin/osascript"


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(assistive, osa_script):
    assistive.install(osa_script, True)
    try:
        yield
    finally:
        osa_script_ret = assistive.installed(osa_script)
        if osa_script_ret:
            assistive.remove(osa_script)

        smile_bundle = "com.smileonmymac.textexpander"
        smile_bundle_present = assistive.installed(smile_bundle)
        if smile_bundle_present:
            assistive.remove(smile_bundle)


@pytest.mark.slow_test
def test_install_and_remove(assistive, osa_script):
    """
    Tests installing and removing a bundled ID or command to use assistive access.
    """
    new_bundle = "com.smileonmymac.textexpander"
    ret = assistive.install(new_bundle)
    assert ret
    ret = assistive.remove(new_bundle)
    assert ret


@pytest.mark.slow_test
def test_installed(assistive, osa_script):
    """
    Tests the True and False return of assistive.installed.
    """
    # OSA script should have been installed in _setup_teardown_vars function
    ret = assistive.installed(osa_script)
    assert ret
    # Clean up install
    assistive.remove(osa_script)
    # Installed should now return False
    ret = assistive.installed(osa_script)
    assert not ret


@pytest.mark.slow_test
def test_enable(assistive, osa_script):
    """
    Tests setting the enabled status of a bundled ID or command.
    """
    # OSA script should have been installed and enabled in _setup_teardown_vars function
    # Now let's disable it, which should return True.
    ret = assistive.enable(osa_script, False)
    assert ret
    # Double check the script was disabled, as intended.
    ret = assistive.enabled(osa_script)
    assert not ret
    # Now re-enable
    ret = assistive.enable(osa_script)
    assert ret
    # Double check the script was enabled, as intended.
    ret = assistive.enabled(osa_script)
    assert ret


@pytest.mark.slow_test
def test_enabled(assistive, osa_script):
    """
    Tests if a bundled ID or command is listed in assistive access returns True.
    """
    # OSA script should have been installed in _setup_teardown_vars function, which sets
    # enabled to True by default.
    ret = assistive.enabled(osa_script)
    assert ret
    # Disable OSA Script
    assistive.enable(osa_script, False)
    # Assert against new disabled status
    ret = assistive.enabled(osa_script)
    assert not ret
