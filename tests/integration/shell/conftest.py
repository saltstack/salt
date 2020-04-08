# -*- coding: utf-8 -*-
"""
    tests.integration.shell.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import, print_function, unicode_literals

import pytest


@pytest.fixture
def salt_cli(request, salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cli(request, salt_master.config["id"])


@pytest.fixture
def salt_cp_cli(request, salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cp(request, salt_master.config["id"])


@pytest.fixture
def salt_key_cli(request, salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_key(request, salt_master.config["id"])


@pytest.fixture
def salt_call_cli(request, salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_call_cli(request, salt_minion.config["id"])
