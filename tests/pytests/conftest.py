# -*- coding: utf-8 -*-
"""
    tests.pytests.conftest
    ~~~~~~~~~~~~~~~~~~~~~~
"""
import pathlib

import pytest
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

PYTESTS_SUITE_PATH = pathlib.Path(__file__).parent


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_collection_modifyitems(config, items):
    """
    called after collection has been performed, may filter or re-order
    the items in-place.

    :param _pytest.main.Session session: the pytest session object
    :param _pytest.config.Config config: pytest config object
    :param List[_pytest.nodes.Item] items: list of item objects
    """
    # Let PyTest or other plugins handle the initial collection
    yield

    # Check each collected item that's under this package to ensure that none is using TestCase as the base class
    for item in items:
        if not str(item.fspath).startswith(str(PYTESTS_SUITE_PATH)):
            continue
        if not item.cls:
            # The test item is not part of a class
            continue

        if issubclass(item.cls, TestCase):
            raise RuntimeError(
                "The tests under {} MUST NOT use unittest's TestCase class or a subclass of it.".format(
                    pathlib.Path(str(item.fspath)).relative_to(RUNTIME_VARS.CODE_DIR)
                )
            )
