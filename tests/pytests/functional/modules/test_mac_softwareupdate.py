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


@pytest.fixture(scope="module")
def softwareupdate(modules):
    return modules.softwareupdate


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(softwareupdate):
    IGNORED_LIST = softwareupdate.list_ignored()

    SCHEDULE = softwareupdate.schedule_enabled()

    CATALOG = softwareupdate.get_catalog()

    try:
        yield IGNORED_LIST, SCHEDULE, CATALOG
    finally:
        if IGNORED_LIST:
            for item in IGNORED_LIST:
                softwareupdate.ignore(item)
        else:
            softwareupdate.reset_ignored()

        softwareupdate.schedule_enable(SCHEDULE)

        if CATALOG == "Default":
            softwareupdate.reset_catalog()
        else:
            softwareupdate.set_catalog(CATALOG)


def test_list_available(softwareupdate):
    """
    Test softwareupdate.list_available
    """
    # Can't predict what will be returned, so can only test that the return
    # is the correct type, dict
    ret = softwareupdate.list_available()
    assert isinstance(ret, dict)


@pytest.mark.skip(reason="Ignore removed from latest OS X.")
def test_ignore(softwareupdate):
    """
    Test softwareupdate.ignore
    Test softwareupdate.list_ignored
    Test softwareupdate.reset_ignored
    """
    # Test reset_ignored
    ret = softwareupdate.reset_ignored()
    assert ret

    ret = softwareupdate.list_ignored()
    assert ret == []

    # Test ignore
    ret = softwareupdate.ignore("spongebob")
    assert ret

    ret = softwareupdate.ignore("squidward")
    assert ret

    # Test list_ignored and verify ignore
    ret = softwareupdate.list_ignored()
    assert "spongebob" in ret

    ret = softwareupdate.list_ignored()
    assert "squidward" in ret


def test_schedule(softwareupdate):
    """
    Test softwareupdate.schedule_enable
    Test softwareupdate.schedule_enabled
    """
    # Test enable
    ret = softwareupdate.schedule_enable(True)
    assert ret

    ret = softwareupdate.schedule_enabled()
    assert ret

    # Test disable in case it was already enabled
    ret = softwareupdate.schedule_enable(False)
    assert not ret

    ret = softwareupdate.schedule_enabled()
    assert not ret


def test_update(softwareupdate):
    """
    Test softwareupdate.update_all
    Test softwareupdate.update
    Test softwareupdate.update_available

    Need to know the names of updates that are available to properly test
    the update functions...
    """
    # There's no way to know what the dictionary will contain, so all we can
    # check is that the return is a dictionary
    ret = softwareupdate.update_all()
    assert isinstance(ret, dict)

    # Test update_available
    ret = softwareupdate.update_available("spongebob")
    assert not ret

    # Test update not available
    ret = softwareupdate.update("spongebob")
    assert "Update not available" in ret


def test_list_downloads(softwareupdate):
    """
    Test softwareupdate.list_downloads
    """
    ret = softwareupdate.list_downloads()
    assert isinstance(ret, list)


def test_download(softwareupdate):
    """
    Test softwareupdate.download

    Need to know the names of updates that are available to properly test
    the download function
    """
    # Test update not available
    ret = softwareupdate.download("spongebob")
    assert "Update not available" in ret


def test_download_all(softwareupdate):
    """
    Test softwareupdate.download_all
    """
    ret = softwareupdate.download_all()
    assert isinstance(ret, list)


def test_get_set_reset_catalog(softwareupdate):
    """
    Test softwareupdate.download_all
    """
    # Reset the catalog
    ret = softwareupdate.reset_catalog()
    assert ret

    ret = softwareupdate.get_catalog()
    assert ret == "Default"

    # Test setting and getting the catalog
    ret = softwareupdate.set_catalog("spongebob")
    assert ret

    ret = softwareupdate.get_catalog()
    assert ret == "spongebob"

    # Test reset the catalog
    ret = softwareupdate.reset_catalog()
    assert ret

    assert softwareupdate.get_catalog()
    assert ret == "Default"
