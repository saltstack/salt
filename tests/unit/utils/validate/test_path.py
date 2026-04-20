from salt.utils.validate import path
from tests.support.unit import TestCase


class ValidatePathTestCase(TestCase):
    """
    TestCase for salt.utils.validate.path module
    """

    def test_is_syslog_path(self):

        """
        Test syslog path
        """

        valid_paths = [
            "file:///dev/log",
            "file:///dev/log/LOG_USER",
            "udp://loghost:10514",
            "udp://loghost:10514/LOG_USER",
            "udp://loghost/LOG_USER",
            "tcp://loghost:10514",
            "tcp://loghost:10514/LOG_USER",
            "tcp://loghost/USER"
        ]

        invalid_paths = [
            "/dev/log",
            "file:///dev/log/USER",
            "udp://loghost/USER",
            "tcp://loghost/USER",
            "unix:///dev/log"
        ]

        for addr in valid_paths:
            self.assertTrue(path.is_syslog_path(addr))

        for addr in invalid_paths:
            self.assertFalse(path.is_syslog_path(addr))
