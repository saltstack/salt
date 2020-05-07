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
    return salt_factories.spawn_minion(request, "minion", master_id="master")


@pytest.fixture(scope="package")
def salt_sub_minion(request, salt_factories, salt_master):
    return salt_factories.spawn_minion(request, "sub_minion", master_id="master")


@pytest.fixture(scope="package", autouse=True)
def bridge_pytest_and_runtests(
    bridge_pytest_and_runtests,
    salt_factories,
    # salt_syndic_master,
    # salt_syndic,
    salt_master,
    salt_minion,
    salt_sub_minion,
):

    yield
