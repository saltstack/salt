"""
integration tests for mac_softwareupdate
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("softwareupdate"),
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
    pytest.mark.skip_initial_gh_actions_failure,
]


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(salt_call_cli):
    ret = salt_call_cli.run("softwareupdate.list_ignored")
    IGNORED_LIST = ret.data

    ret = salt_call_cli.run("softwareupdate.schedule")
    SCHEDULE = ret.data

    ret = salt_call_cli.run("softwareupdate.get_catalog")
    CATALOG = ret.data

    try:
        yield IGNORED_LIST, SCHEDULE, CATALOG
    finally:
        if IGNORED_LIST:
            for item in IGNORED_LIST:
                salt_call_cli.run_function("softwareupdate.ignore", item)
        else:
            salt_call_cli.run_function("softwareupdate.reset_ignored")

        salt_call_cli.run_function("softwareupdate.schedule", SCHEDULE)

        if CATALOG == "Default":
            salt_call_cli.run_function("softwareupdate.reset_catalog")
        else:
            salt_call_cli.run_function("softwareupdate.set_catalog", CATALOG)


def test_list_available(salt_call_cli):
    """
    Test softwareupdate.list_available
    """
    # Can't predict what will be returned, so can only test that the return
    # is the correct type, dict
    ret = salt_call_cli.run("softwareupdate.list_available")
    assert isinstance(ret.data, dict)


def test_ignore(salt_call_cli):
    """
    Test softwareupdate.ignore
    Test softwareupdate.list_ignored
    Test softwareupdate.reset_ignored
    """
    # Test reset_ignored
    ret = salt_call_cli.run("softwareupdate.reset_ignored")
    assert ret.data

    ret = salt_call_cli.run("softwareupdate.list_ignored") == []
    assert ret.data

    # Test ignore
    ret = salt_call_cli.run("softwareupdate.ignore", "spongebob")
    assert ret.data

    ret = salt_call_cli.run("softwareupdate.ignore", "squidward")
    assert ret.data

    # Test list_ignored and verify ignore
    ret = salt_call_cli.run("softwareupdate.list_ignored")
    assert "spongebob" in ret.data

    ret = salt_call_cli.run("softwareupdate.list_ignored")
    assert "squidward" in ret.data


def test_schedule(salt_call_cli):
    """
    Test softwareupdate.schedule_enable
    Test softwareupdate.schedule_enabled
    """
    # Test enable
    ret = salt_call_cli.run("softwareupdate.schedule_enable", True)
    assert ret.data

    ret = salt_call_cli.run("softwareupdate.schedule_enabled")
    assert ret.data

    # Test disable in case it was already enabled
    ret = salt_call_cli.run("softwareupdate.schedule_enable", False)
    assert ret.data

    ret = salt_call_cli.run("softwareupdate.schedule_enabled")
    assert not ret.data


def test_update(salt_call_cli):
    """
    Test softwareupdate.update_all
    Test softwareupdate.update
    Test softwareupdate.update_available

    Need to know the names of updates that are available to properly test
    the update functions...
    """
    # There's no way to know what the dictionary will contain, so all we can
    # check is that the return is a dictionary
    ret = salt_call_cli.run("softwareupdate.update_all")
    assert isinstance(ret, dict)

    # Test update_available
    ret = salt_call_cli.run("softwareupdate.update_available", "spongebob")
    assert not ret.data

    # Test update not available
    ret = salt_call_cli.run("softwareupdate.update", "spongebob")
    assert "Update not available" in ret.data


def test_list_downloads(salt_call_cli):
    """
    Test softwareupdate.list_downloads
    """
    ret = salt_call_cli.run("softwareupdate.list_downloads")
    assert isinstance(ret.data, list)


def test_download(salt_call_cli):
    """
    Test softwareupdate.download

    Need to know the names of updates that are available to properly test
    the download function
    """
    # Test update not available
    ret = salt_call_cli.run("softwareupdate.download", ["spongebob"])
    assert "Update not available" in ret.data


def test_download_all(salt_call_cli):
    """
    Test softwareupdate.download_all
    """
    ret = salt_call_cli.run("softwareupdate.download_all")
    assert isinstance(ret.data, list)


def test_get_set_reset_catalog(salt_call_cli):
    """
    Test softwareupdate.download_all
    """
    # Reset the catalog
    ret = salt_call_cli.run("softwareupdate.reset_catalog")
    assert ret.data

    ret = salt_call_cli.run("softwareupdate.get_catalog")
    assert ret.data == "Default"

    # Test setting and getting the catalog
    ret = salt_call_cli.run("softwareupdate.set_catalog", "spongebob")
    assert ret.data

    ret = salt_call_cli.run("softwareupdate.get_catalog") == "spongebob"
    assert ret.data

    # Test reset the catalog
    ret = salt_call_cli.run("softwareupdate.reset_catalog")
    assert ret.data

    assert salt_call_cli.run("softwareupdate.get_catalog")
    assert ret.data == "Default"
