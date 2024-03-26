"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def assistive(modules):
    return modules.assistive


@pytest.fixture
def osa_script(assistive):
    osa_script_path = "/usr/bin/osascript"
    try:
        assistive.install(osa_script_path, True)
        yield osa_script_path
    except CommandExecutionError as exc:
        pytest.skip(f"Unable to install {osa_script}: {exc}")
    finally:
        osa_script_ret = assistive.installed(osa_script_path)
        if osa_script_ret:
            assistive.remove(osa_script_path)


@pytest.fixture
def install_remove_pkg_name(assistive, grains):
    smile_bundle = "com.smileonmymac.textexpander"
    try:
        yield smile_bundle
    finally:
        smile_bundle_present = assistive.installed(smile_bundle)
        if smile_bundle_present:
            assistive.remove(smile_bundle)


@pytest.mark.slow_test
def test_install_and_remove(assistive, install_remove_pkg_name, grains):
    """
    Tests installing and removing a bundled ID or command to use assistive access.
    """
    try:
        ret = assistive.install(install_remove_pkg_name)
        assert ret
    except CommandExecutionError as exc:
        if grains["osmajorrelease"] != 12:
            raise exc from None
        if "attempt to write a readonly database" not in str(exc):
            raise exc from None
        pytest.skip("Test fails on MacOS 12(attempt to write a readonly database)")
    ret = assistive.remove(install_remove_pkg_name)
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
