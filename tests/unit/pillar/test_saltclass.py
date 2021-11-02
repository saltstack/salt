import os

import salt.pillar.saltclass as saltclass
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class SaltclassPillarTestCase(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.pillar.saltclass
    """

    def setup_loader_modules(self):
        return {saltclass: {}}

    def _runner(self, expected_ret):
        fake_args = {
            "path": os.path.abspath(
                os.path.join(RUNTIME_VARS.FILES, "saltclass", "examples")
            )
        }
        fake_pillar = {}
        fake_minion_id = "fake_id"
        try:
            full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
            parsed_ret = full_ret["__saltclass__"]["classes"]
        # Fail the test if we hit our NoneType error
        except TypeError as err:
            self.fail(err)
        # Else give the parsed content result
        self.assertListEqual(expected_ret, parsed_ret)

    def test_succeeds(self):
        ret = [
            "default.users",
            "default.motd",
            "default.empty",
            "default",
            "roles.app",
            "roles.nginx",
        ]
        self._runner(ret)


class SaltclassPillarTestCaseListExpansion(TestCase, LoaderModuleMockMixin):
    """
    Tests for salt.pillar.saltclass variable expansion in list
    """

    def setup_loader_modules(self):
        return {saltclass: {}}

    def _runner(self, expected_ret):
        full_ret = {}
        parsed_ret = []
        fake_args = {
            "path": os.path.abspath(
                os.path.join(RUNTIME_VARS.FILES, "saltclass", "examples")
            )
        }
        fake_pillar = {}
        fake_minion_id = "fake_id"
        try:
            full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
            parsed_ret = full_ret["test_list"]
        # Fail the test if we hit our NoneType error
        except TypeError as err:
            self.fail(err)
        # Else give the parsed content result
        self.assertListEqual(expected_ret, parsed_ret)

    def test_succeeds(self):
        ret = [{"a": "192.168.10.10"}, "192.168.10.20"]
        self._runner(ret)
