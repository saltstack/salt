"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.modules.data as data
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class DataTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.data
    """

    def setup_loader_modules(self):
        return {data: {}}

    # 'clear' function tests: 1

    def test_clear(self):
        """
        Test if it clear out all of the data in the minion datastore
        """
        with patch("os.remove", MagicMock(return_value="")):
            with patch.dict(data.__opts__, {"cachedir": ""}):
                self.assertTrue(data.clear())

    # 'load' function tests: 1

    def test_load(self):
        """
        Test if it return all of the data in the minion datastore
        """
        with patch("salt.payload.Serial.load", MagicMock(return_value=True)):
            mocked_fopen = MagicMock(return_value=True)
            mocked_fopen.__enter__ = MagicMock(return_value=mocked_fopen)
            mocked_fopen.__exit__ = MagicMock()
            with patch("salt.utils.files.fopen", MagicMock(return_value=mocked_fopen)):
                with patch("salt.payload.loads", MagicMock(return_value=True)):
                    with patch.dict(data.__opts__, {"cachedir": "/"}):
                        self.assertTrue(data.load())

    # 'dump' function tests: 3

    def test_dump(self):
        """
        Test if it replace the entire datastore with a passed data structure
        """
        with patch.dict(data.__opts__, {"cachedir": "/"}):
            with patch("salt.utils.files.fopen", mock_open()):
                self.assertTrue(data.dump('{"eggs": "spam"}'))

    def test_dump_isinstance(self):
        """
        Test if it replace the entire datastore with a passed data structure
        """
        with patch("ast.literal_eval", MagicMock(return_value="")):
            self.assertFalse(data.dump("salt"))

    def test_dump_ioerror(self):
        """
        Test if it replace the entire datastore with a passed data structure
        """
        with patch.dict(data.__opts__, {"cachedir": "/"}):
            mock = MagicMock(side_effect=IOError(""))
            with patch("salt.utils.files.fopen", mock):
                self.assertFalse(data.dump('{"eggs": "spam"}'))

    # 'update' function tests: 1

    def test_update(self):
        """
        Test if it update a key with a value in the minion datastore
        """
        with patch("salt.modules.data.load", MagicMock(return_value={})), patch(
            "salt.modules.data.dump", MagicMock(return_value=True)
        ):
            self.assertTrue(data.update("foo", "salt"))

    # 'get' function tests: 2

    def test_get(self):
        """
        Test if it gets a value from the minion datastore
        """
        with patch("salt.modules.data.load", MagicMock(return_value={"salt": "SALT"})):
            self.assertEqual(data.get("salt"), "SALT")

    def test_get_vals(self):
        """
        Test if it gets values from the minion datastore
        """
        with patch(
            "salt.modules.data.load",
            MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
        ):
            self.assertEqual(data.get(["salt", "salt1"]), ["SALT", "SALT1"])

    # 'cas' function tests: 1

    def test_cas_not_load(self):
        """
        Test if it check and set a value in the minion datastore
        """
        with patch(
            "salt.modules.data.load",
            MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
        ):
            self.assertFalse(data.cas("salt3", "SALT", "SALTSTACK"))

    def test_cas_not_equal(self):
        """
        Test if it check and set a value in the minion datastore
        """
        with patch(
            "salt.modules.data.load",
            MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
        ):
            self.assertFalse(data.cas("salt", "SALT", "SALTSTACK"))

    def test_cas(self):
        """
        Test if it check and set a value in the minion datastore
        """
        with patch(
            "salt.modules.data.load",
            MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
        ), patch("salt.modules.data.dump", MagicMock(return_value=True)):
            self.assertTrue(data.cas("salt", "SALTSTACK", "SALT"))
