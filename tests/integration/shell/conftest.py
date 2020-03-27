# -*- coding: utf-8 -*-
"""
    tests.integration.shell.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import, print_function, unicode_literals

import pytest


@pytest.fixture
def salt_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cli(salt_master.config["id"])


@pytest.fixture
def salt_cp_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cp_cli(salt_master.config["id"])


@pytest.fixture
def salt_key_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_key_cli(salt_master.config["id"])


@pytest.fixture
def salt_run_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_run_cli(salt_master.config["id"])


@pytest.fixture
def salt_call_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_call_cli(salt_minion.config["id"])
