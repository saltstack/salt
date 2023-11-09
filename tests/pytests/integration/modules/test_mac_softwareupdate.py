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


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    IGNORED_LIST = salt_call_cli.run("softwareupdate.list_ignored")
    SCHEDULE = salt_call_cli.run("softwareupdate.schedule")
    CATALOG = salt_call_cli.run("softwareupdate.get_catalog")

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


def test_list_available(salt_call_cli, setup_teardown_vars):
    """
    Test softwareupdate.list_available
    """
    # Can't predict what will be returned, so can only test that the return
    # is the correct type, dict
    assert isinstance(salt_call_cli.run("softwareupdate.list_available"), dict)


def test_ignore(salt_call_cli, setup_teardown_vars):
    """
    Test softwareupdate.ignore
    Test softwareupdate.list_ignored
    Test softwareupdate.reset_ignored
    """
    # Test reset_ignored
    assert salt_call_cli.run("softwareupdate.reset_ignored")
    assert salt_call_cli.run("softwareupdate.list_ignored") == []

    # Test ignore
    assert salt_call_cli.run("softwareupdate.ignore", "spongebob")
    assert salt_call_cli.run("softwareupdate.ignore", "squidward")

    # Test list_ignored and verify ignore
    assert "spongebob" in salt_call_cli.run("softwareupdate.list_ignored")
    assert "squidward" in salt_call_cli.run("softwareupdate.list_ignored")


def test_schedule(salt_call_cli):
    """
    Test softwareupdate.schedule_enable
    Test softwareupdate.schedule_enabled
    """
    # Test enable
    assert salt_call_cli.run("softwareupdate.schedule_enable", True)
    assert salt_call_cli.run("softwareupdate.schedule_enabled")

    # Test disable in case it was already enabled
    assert salt_call_cli.run("softwareupdate.schedule_enable", False)
    assert not salt_call_cli.run("softwareupdate.schedule_enabled")


def test_update(salt_call_cli, setup_teardown_vars):
    """
    Test softwareupdate.update_all
    Test softwareupdate.update
    Test softwareupdate.update_available

    Need to know the names of updates that are available to properly test
    the update functions...
    """
    # There's no way to know what the dictionary will contain, so all we can
    # check is that the return is a dictionary
    assert isinstance(salt_call_cli.run("softwareupdate.update_all"), dict)

    # Test update_available
    assert not salt_call_cli.run("softwareupdate.update_available", "spongebob")

    # Test update not available
    assert "Update not available" in salt_call_cli.run(
        "softwareupdate.update", "spongebob"
    )


def test_list_downloads(salt_call_cli, setup_teardown_vars):
    """
    Test softwareupdate.list_downloads
    """
    assert isinstance(salt_call_cli.run("softwareupdate.list_downloads"), list)


def test_download(salt_call_cli, setup_teardown_vars):
    """
    Test softwareupdate.download

    Need to know the names of updates that are available to properly test
    the download function
    """
    # Test update not available
    assert "Update not available" in salt_call_cli.run(
        "softwareupdate.download", ["spongebob"]
    )


def test_download_all(salt_call_cli, setup_teardown_vars):
    """
    Test softwareupdate.download_all
    """
    assert isinstance(salt_call_cli.run("softwareupdate.download_all"), list)


def test_get_set_reset_catalog(salt_call_cli, setup_teardown_vars):
    """
    Test softwareupdate.download_all
    """
    # Reset the catalog
    assert salt_call_cli.run("softwareupdate.reset_catalog")
    assert salt_call_cli.run("softwareupdate.get_catalog") == "Default"

    # Test setting and getting the catalog
    assert salt_call_cli.run("softwareupdate.set_catalog", "spongebob")
    assert salt_call_cli.run("softwareupdate.get_catalog") == "spongebob"

    # Test reset the catalog
    assert salt_call_cli.run("softwareupdate.reset_catalog")
    assert salt_call_cli.run("softwareupdate.get_catalog") == "Default"
