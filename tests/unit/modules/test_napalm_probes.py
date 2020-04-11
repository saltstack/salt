# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import tests.support.napalm as napalm_test_support

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.unit import TestCase

import salt.modules.napalm_probes as napalm_probes  # NOQA


TEST_PROBES = {
    "new_probe": {
        "new_test1": {
            "probe_type": "icmp-ping",
            "target": "192.168.0.1",
            "source": "192.168.0.2",
            "probe_count": 13,
            "test_interval": 3,
        }
    }
}


TEST_DELETE_PROBES = {"existing_probe": {"existing_test1": {}, "existing_test2": {}}}


TEST_SCHEDULE_PROBES = {"test_probe": {"existing_test1": {}, "existing_test2": {}}}


def mock_net_load(template, *args, **kwargs):
    if template == "set_probes":
        assert kwargs["probes"] == TEST_PROBES
        return napalm_test_support.TEST_TERM_CONFIG
    if template == "delete_probes":
        assert kwargs["probes"] == TEST_DELETE_PROBES
        return napalm_test_support.TEST_TERM_CONFIG
    if template == "schedule_probes":
        assert kwargs["probes"] == TEST_SCHEDULE_PROBES
        return napalm_test_support.TEST_TERM_CONFIG
    raise ValueError("incorrect template {0}".format(template))


class NapalmProbesModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {
            "__salt__": {
                "config.option": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                ),
                "file.file_exists": napalm_test_support.true,
                "file.join": napalm_test_support.join,
                "file.get_managed": napalm_test_support.get_managed_file,
                "random.hash": napalm_test_support.random_hash,
                "net.load_template": mock_net_load,
            }
        }

        return {napalm_probes: module_globals}

    def test_probes_config(self):
        ret = napalm_probes.config()
        assert ret["out"] == napalm_test_support.TEST_PROBES_CONFIG

    def test_probes_results(self):
        ret = napalm_probes.results()
        assert ret["out"] == napalm_test_support.TEST_PROBES_RESULTS

    def test_set_probes(self):
        ret = napalm_probes.set_probes(TEST_PROBES)
        assert ret["result"] is True

    def test_delete_probes(self):
        ret = napalm_probes.delete_probes(TEST_DELETE_PROBES)
        assert ret["result"] is True

    def test_schedule_probes(self):
        ret = napalm_probes.schedule_probes(TEST_SCHEDULE_PROBES)
        assert ret["result"] is True
