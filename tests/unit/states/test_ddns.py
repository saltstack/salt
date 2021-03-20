"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.states.ddns as ddns
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DdnsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.ddns
    """

    def setup_loader_modules(self):
        return {ddns: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensures that the named DNS record is present with the given ttl.
        """
        name = "webserver"
        zone = "example.com"
        ttl = "60"
        data = "111.222.333.444"

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        with patch.dict(ddns.__opts__, {"test": True}):
            comt = 'A record "{}" will be updated'.format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(ddns.present(name, zone, ttl, data), ret)

            with patch.dict(ddns.__opts__, {"test": False}):
                mock = MagicMock(return_value=None)
                with patch.dict(ddns.__salt__, {"ddns.update": mock}):
                    comt = 'A record "{}" already present with ttl of {}'.format(
                        name, ttl
                    )
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(ddns.present(name, zone, ttl, data), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensures that the named DNS record is absent.
        """
        name = "webserver"
        zone = "example.com"
        data = "111.222.333.444"

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        with patch.dict(ddns.__opts__, {"test": True}):
            comt = 'None record "{}" will be deleted'.format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(ddns.absent(name, zone, data), ret)

            with patch.dict(ddns.__opts__, {"test": False}):
                mock = MagicMock(return_value=None)
                with patch.dict(ddns.__salt__, {"ddns.delete": mock}):
                    comt = "No matching DNS record(s) present"
                    ret.update({"comment": comt, "result": True})
                    self.assertDictEqual(ddns.absent(name, zone, data), ret)
