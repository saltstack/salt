# -*- coding: utf-8 -*-
"""
    tests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration tests PyTest configuration/fixtures
"""
# pylint: disable=unused-argument,redefined-outer-name

from __future__ import absolute_import, unicode_literals

import logging

import pytest
from tests.support.pytest.fixtures import *  # pylint: disable=unused-wildcard-import

log = logging.getLogger(__name__)


# @pytest.fixture(scope='package')
# def salt_syndic_master(request, salt_factories):
#     return salt_factories.spawn_master(request, 'syndic_master', order_masters=True)


# @pytest.fixture(scope='package')
# def salt_syndic(request, salt_factories, salt_syndic_master):
#     return salt_factories.spawn_syndic(request, 'syndic', master_of_masters_id='syndic_master')


# @pytest.fixture(scope='package')
# def salt_master(request, salt_factories, salt_syndic_master):
#    return salt_factories.spawn_master(request, 'master', master_of_masters_id='syndic_master')


@pytest.fixture(scope="package")
def salt_master(request, salt_factories):
    return salt_factories.spawn_master(request, "master")


@pytest.fixture(scope="package")
def salt_minion(request, salt_factories, salt_master):
    proc = salt_factories.spawn_minion(request, "minion", master_id="master")
    # Sync All
    salt_call_cli = salt_factories.get_salt_call_cli("minion")
    ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
    assert ret.exitcode == 0, ret
    return proc


@pytest.fixture(scope="package")
def salt_sub_minion(request, salt_factories, salt_master):
    proc = salt_factories.spawn_minion(request, "sub_minion", master_id="master")
    # Sync All
    salt_call_cli = salt_factories.get_salt_call_cli("sub_minion")
    ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
    assert ret.exitcode == 0, ret
    return proc


@pytest.fixture(scope="package", autouse=True)
def bridge_pytest_and_runtests_integration(
    bridge_pytest_and_runtests,
    salt_factories,
    # salt_syndic_master,
    # salt_syndic,
    salt_master,
    salt_minion,
):

    yield


@pytest.fixture(scope="package")
def salt_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_cp_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cp_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_key_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_key_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_run_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_run_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_call_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_call_cli(salt_minion.config["id"])
