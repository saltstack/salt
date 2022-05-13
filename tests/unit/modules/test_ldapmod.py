"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import time

import salt.modules.ldapmod as ldapmod
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class LdapmodTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.ldapmod
    """

    def setup_loader_modules(self):
        return {ldapmod: {}}

    # 'search' function tests: 1

    def test_search(self):
        """
        Test if it run an arbitrary LDAP query and return the results.
        """

        class MockConnect:
            """
            Mocking _connect method
            """

            def __init__(self):
                self.bdn = None
                self.scope = None
                self._filter = None
                self.attrs = None

            def search_s(self, bdn, scope, _filter, attrs):
                """
                Mock function for search_s
                """
                self.bdn = bdn
                self.scope = scope
                self._filter = _filter
                self.attrs = attrs
                return "SALT"

        mock = MagicMock(return_value=True)
        with patch.dict(ldapmod.__salt__, {"config.option": mock}):
            with patch.object(
                ldapmod, "_connect", MagicMock(return_value=MockConnect())
            ):
                with patch.object(time, "time", MagicMock(return_value=8e-04)):
                    self.assertDictEqual(
                        ldapmod.search(filter="myhost"),
                        {
                            "count": 4,
                            "results": "SALT",
                            "time": {"raw": "0.0", "human": "0.0ms"},
                        },
                    )
