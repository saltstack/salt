# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt libs
import salt.beacons.ps as ps
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch

# Salt testing libs
from tests.support.unit import TestCase

PATCH_OPTS = dict(autospec=True, spec_set=True)


class FakeProcess(object):
    def __init__(self, _name, pid):
        self._name = _name
        self.pid = pid

    def name(self):
        return self._name


class PSBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.[s]
    """

    def setup_loader_modules(self):
        return {}

    def test_non_list_config(self):
        config = {}

        ret = ps.validate(config)

        self.assertEqual(ret, (False, "Configuration for ps beacon must be a list."))

    def test_empty_config(self):
        config = [{}]

        ret = ps.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for ps beacon requires processes.")
        )

    def test_ps_running(self):
        with patch(
            "salt.utils.psutil_compat.process_iter", **PATCH_OPTS
        ) as mock_process_iter:
            mock_process_iter.return_value = [
                FakeProcess(_name="salt-master", pid=3),
                FakeProcess(_name="salt-minion", pid=4),
            ]
            config = [{"processes": {"salt-master": "running"}}]

            ret = ps.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = ps.beacon(config)
            self.assertEqual(ret, [{"salt-master": "Running"}])

    def test_ps_not_running(self):
        with patch(
            "salt.utils.psutil_compat.process_iter", **PATCH_OPTS
        ) as mock_process_iter:
            mock_process_iter.return_value = [
                FakeProcess(_name="salt-master", pid=3),
                FakeProcess(_name="salt-minion", pid=4),
            ]
            config = [{"processes": {"mysql": "stopped"}}]

            ret = ps.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = ps.beacon(config)
            self.assertEqual(ret, [{"mysql": "Stopped"}])
