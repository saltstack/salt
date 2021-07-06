"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import salt.modules.sdb as sdb
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class SdbTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.sdb
    """

    def setup_loader_modules(self):
        return {sdb: {}}

    # 'get' function tests: 4

    def test_get(self):
        """
        Test if it gets a value from a db, using a uri in the form of
        sdb://<profile>/<key>
        """
        self.assertEqual(sdb.get("sdb://salt/foo"), "sdb://salt/foo")

    def test_get_strict_no_sdb_in_uri(self):
        """
        Test if SaltInvocationError exception will be raised if we
        don't start uri with sdb://
        """

        msg = 'SDB uri must start with "sdb://"'
        with self.assertRaisesRegex(SaltInvocationError, msg) as cm:
            sdb.get("://salt/foo", strict=True)

    def test_get_strict_no_profile(self):
        """
        Test if SaltInvocationError exception will be raised if we
        don't have a valid profile in the uri
        """

        msg = "SDB uri must have a profile name as a first part of the uri before the /"
        with self.assertRaisesRegex(SaltInvocationError, msg) as cm:
            sdb.get("sdb://salt", strict=True)

    def test_get_strict_no_profile_in_config(self):
        """
        Test if SaltInvocationError exception will be raised if we
        don't have expected profile in the minion config
        """

        msg = 'SDB profile "salt" wasnt found in the minion configuration'
        with self.assertRaisesRegex(SaltInvocationError, msg) as cm:
            sdb.get("sdb://salt/foo", strict=True)

    # 'set_' function tests: 1

    def test_set(self):
        """
        Test if it sets a value from a db, using a uri in the form of
        sdb://<profile>/<key>
        """
        self.assertFalse(sdb.set_("sdb://mymemcached/foo", "bar"))
