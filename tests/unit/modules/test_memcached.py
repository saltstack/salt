"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.modules.memcached as memcached
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MemcachedTestCase(TestCase):
    """
    Test cases for salt.modules.memcached
    """

    # 'status' function tests: 2

    def test_status(self):
        """
        Test if it gets memcached status
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertDictEqual(memcached.status(), {"127.0.0.1:11211 (1)": {}})

    def test_status_false(self):
        """
        Test if it gets memcached status
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return []

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertFalse(memcached.status())

    # 'get' function tests: 1

    def test_get(self):
        """
        Test if it retrieve value for a key
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            @staticmethod
            def get(key):
                """
                Mock of get method
                """
                return key

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertEqual(memcached.get("salt"), "salt")

    # 'set_' function tests: 1

    def test_set(self):
        """
        Test if it set a key on the memcached server
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None
                self.value = None
                self.time = None
                self.min_compress_len = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def set(self, key, value, time, min_compress_len):
                """
                Mock of set method
                """
                self.key = key
                self.value = value
                self.time = time
                self.min_compress_len = min_compress_len
                return True

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertTrue(memcached.set_("salt", "1111"))

            self.assertRaises(
                SaltInvocationError, memcached.set_, "salt", "1111", time="0.1"
            )

            self.assertRaises(
                SaltInvocationError,
                memcached.set_,
                "salt",
                "1111",
                min_compress_len="0.1",
            )

    # 'delete' function tests: 1

    def test_delete(self):
        """
        Test if it delete a key from memcache server
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None
                self.time = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def delete(self, key, time):
                """
                Mock of delete method
                """
                self.key = key
                self.time = time
                return True

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertTrue(memcached.delete("salt"))

            self.assertRaises(
                SaltInvocationError, memcached.delete, "salt", "1111", time="0.1"
            )

    # 'add' function tests: 1

    def test_add(self):
        """
        Test if it add a key from memcache server
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None
                self.value = None
                self.time = None
                self.min_compress_len = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def add(self, key, value, time, min_compress_len):
                """
                Mock of add method
                """
                self.key = key
                self.value = value
                self.time = time
                self.min_compress_len = min_compress_len
                return True

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertTrue(memcached.add("salt", "1111"))

            self.assertRaises(
                SaltInvocationError, memcached.add, "salt", "1111", time="0.1"
            )

            self.assertRaises(
                SaltInvocationError,
                memcached.add,
                "salt",
                "1111",
                min_compress_len="0.1",
            )

    # 'replace' function tests: 1

    def test_replace(self):
        """
        Test if it replace a key from memcache server
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None
                self.value = None
                self.time = None
                self.min_compress_len = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def replace(self, key, value, time, min_compress_len):
                """
                Mock of replace method
                """
                self.key = key
                self.value = value
                self.time = time
                self.min_compress_len = min_compress_len
                return True

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertTrue(memcached.replace("salt", "1111"))

            self.assertRaises(
                SaltInvocationError, memcached.replace, "salt", "1111", time="0.1"
            )

            self.assertRaises(
                SaltInvocationError,
                memcached.replace,
                "salt",
                "1111",
                min_compress_len="0.1",
            )

    # 'increment' function tests: 3

    def test_increment(self):
        """
        Test if it increment the value of a key
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def get(self, key):
                """
                Mock of get method
                """
                self.key = key
                return 1

            def incr(self, key, delta):
                """
                Mock of incr method
                """
                self.key = key
                if not isinstance(delta, int):
                    raise SaltInvocationError("Delta value must be an integer")
                return key

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertEqual(memcached.increment("salt"), "salt")

            self.assertRaises(
                SaltInvocationError, memcached.increment, "salt", delta="sa"
            )

    def test_increment_exist(self):
        """
        Test if it increment the value of a key
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def get(self, key):
                """
                Mock of get method
                """
                self.key = key
                return key

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertRaises(CommandExecutionError, memcached.increment, "salt")

    def test_increment_none(self):
        """
        Test if it increment the value of a key
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def get(self, key):
                """
                Mock of get method
                """
                self.key = key
                return None

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertRaises(CommandExecutionError, memcached.increment, "salt")

    # 'decrement' function tests: 3

    def test_decrement(self):
        """
        Test if it decrement the value of a key
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def get(self, key):
                """
                Mock of get method
                """
                self.key = key
                return 1

            def decr(self, key, delta):
                """
                Mock of decr method
                """
                self.key = key
                if not isinstance(delta, int):
                    raise SaltInvocationError("Delta value must be an integer")
                return key

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertEqual(memcached.decrement("salt"), "salt")

            self.assertRaises(
                SaltInvocationError, memcached.decrement, "salt", delta="sa"
            )

    def test_decrement_exist(self):
        """
        Test if it decrement the value of a key
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def get(self, key):
                """
                Mock of get method
                """
                self.key = key
                return key

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertRaises(CommandExecutionError, memcached.decrement, "salt")

    def test_decrement_none(self):
        """
        Test if it decrement the value of a key
        """

        class MockMemcache:
            """
            Mock of memcache
            """

            def __init__(self):
                self.key = None

            @staticmethod
            def get_stats():
                """
                Mock of stats method
                """
                return [("127.0.0.1:11211 (1)", {})]

            def get(self, key):
                """
                Mock of get method
                """
                self.key = key
                return None

        with patch.object(
            memcached, "_connect", MagicMock(return_value=MockMemcache())
        ):
            self.assertRaises(CommandExecutionError, memcached.decrement, "salt")
