import salt.utils.cloud
from salt.utils.cloud import __ssh_gateway_arguments as ssh_gateway_arguments
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class CloudUtilTest(TestCase):
    def test_ssh_gateway_arguments_default_alive_args(self):
        arguments = ssh_gateway_arguments({"ssh_gateway": "host"})
        self.assertIn(
            "-oServerAliveInterval={}".format(salt.utils.cloud.SERVER_ALIVE_INTERVAL),
            arguments,
        )
        self.assertIn(
            "-oServerAliveCountMax={}".format(salt.utils.cloud.SERVER_ALIVE_COUNT_MAX),
            arguments,
        )

    def test_ssh_gateway_arguments_alive_args(self):
        arguments = ssh_gateway_arguments(
            {
                "ssh_gateway": "host",
                "server_alive_interval": salt.utils.cloud.SERVER_ALIVE_INTERVAL + 1,
                "server_alive_count_max": salt.utils.cloud.SERVER_ALIVE_COUNT_MAX * 2,
            }
        )
        self.assertIn(
            "-oServerAliveInterval={}".format(
                salt.utils.cloud.SERVER_ALIVE_INTERVAL + 1
            ),
            arguments,
        )
        self.assertIn(
            "-oServerAliveCountMax={}".format(
                salt.utils.cloud.SERVER_ALIVE_COUNT_MAX * 2
            ),
            arguments,
        )

    @patch("salt.utils.cloud.socket", MagicMock())
    def test_wait_for_port_default_alive_args(self):
        with patch(
            "salt.utils.cloud._exec_ssh_cmd", MagicMock(return_value=0)
        ) as exec_ssh_cmd:
            salt.utils.cloud.wait_for_port(
                "127.0.0.1",
                gateway={"ssh_gateway": "host", "ssh_gateway_user": "user"},
            )
            self.assertEqual(exec_ssh_cmd.call_count, 2)
            ssh_call = exec_ssh_cmd.call_args[0][0]
            self.assertIn(
                "-oServerAliveInterval={}".format(
                    salt.utils.cloud.SERVER_ALIVE_INTERVAL
                ),
                ssh_call,
            )
            self.assertIn(
                "-oServerAliveCountMax={}".format(
                    salt.utils.cloud.SERVER_ALIVE_COUNT_MAX
                ),
                ssh_call,
            )

    @patch("salt.utils.cloud.socket", MagicMock())
    def test_wait_for_port_alive_args(self):
        with patch(
            "salt.utils.cloud._exec_ssh_cmd", MagicMock(return_value=0)
        ) as exec_ssh_cmd:
            salt.utils.cloud.wait_for_port(
                "127.0.0.1",
                server_alive_interval=salt.utils.cloud.SERVER_ALIVE_INTERVAL * 2,
                server_alive_count_max=salt.utils.cloud.SERVER_ALIVE_COUNT_MAX + 1,
                gateway={"ssh_gateway": "host", "ssh_gateway_user": "user"},
            )
            self.assertEqual(exec_ssh_cmd.call_count, 2)
            ssh_call = exec_ssh_cmd.call_args[0][0]
            self.assertIn(
                "-oServerAliveInterval={}".format(
                    salt.utils.cloud.SERVER_ALIVE_INTERVAL * 2
                ),
                ssh_call,
            )
            self.assertIn(
                "-oServerAliveCountMax={}".format(
                    salt.utils.cloud.SERVER_ALIVE_COUNT_MAX + 1
                ),
                ssh_call,
            )

    @patch("salt.utils.cloud.socket", MagicMock())
    def test_scp_file_default_alive_args(self):
        with patch(
            "salt.utils.cloud._exec_ssh_cmd", MagicMock(return_value=0)
        ) as exec_ssh_cmd:
            salt.utils.cloud.scp_file(
                "/salt.txt",
                contents=None,
                kwargs={"hostname": "127.0.0.1", "username": "user"},
                local_file="/salt.txt",
            )
            self.assertEqual(exec_ssh_cmd.call_count, 1)
            ssh_call = exec_ssh_cmd.call_args[0][0]
            self.assertIn(
                "-oServerAliveInterval={}".format(
                    salt.utils.cloud.SERVER_ALIVE_INTERVAL
                ),
                ssh_call,
            )
            self.assertIn(
                "-oServerAliveCountMax={}".format(
                    salt.utils.cloud.SERVER_ALIVE_COUNT_MAX
                ),
                ssh_call,
            )

    @patch("salt.utils.cloud.socket", MagicMock())
    def test_scp_file_alive_args(self):
        with patch(
            "salt.utils.cloud._exec_ssh_cmd", MagicMock(return_value=0)
        ) as exec_ssh_cmd:
            salt.utils.cloud.scp_file(
                "/salt.txt",
                contents=None,
                kwargs={
                    "hostname": "127.0.0.1",
                    "username": "user",
                    "server_alive_interval": salt.utils.cloud.SERVER_ALIVE_INTERVAL + 2,
                    "server_alive_count_max": salt.utils.cloud.SERVER_ALIVE_COUNT_MAX
                    + 3,
                },
                local_file="/salt.txt",
            )
            self.assertEqual(exec_ssh_cmd.call_count, 1)
            ssh_call = exec_ssh_cmd.call_args[0][0]
            self.assertIn(
                "-oServerAliveInterval={}".format(
                    salt.utils.cloud.SERVER_ALIVE_INTERVAL + 2
                ),
                ssh_call,
            )
            self.assertIn(
                "-oServerAliveCountMax={}".format(
                    salt.utils.cloud.SERVER_ALIVE_COUNT_MAX + 3
                ),
                ssh_call,
            )

    @patch("salt.utils.cloud.socket", MagicMock())
    def test_sftp_file_default_alive_args(self):
        with patch(
            "salt.utils.cloud._exec_ssh_cmd", MagicMock(return_value=0)
        ) as exec_ssh_cmd:
            salt.utils.cloud.sftp_file(
                "/salt.txt",
                contents=None,
                kwargs={"hostname": "127.0.0.1", "username": "user"},
                local_file="/salt.txt",
            )
            self.assertEqual(exec_ssh_cmd.call_count, 1)
            ssh_call = exec_ssh_cmd.call_args[0][0]
            self.assertIn(
                "-oServerAliveInterval={}".format(
                    salt.utils.cloud.SERVER_ALIVE_INTERVAL
                ),
                ssh_call,
            )
            self.assertIn(
                "-oServerAliveCountMax={}".format(
                    salt.utils.cloud.SERVER_ALIVE_COUNT_MAX
                ),
                ssh_call,
            )

    @patch("salt.utils.cloud.socket", MagicMock())
    def test_sftp_file_alive_args(self):
        with patch(
            "salt.utils.cloud._exec_ssh_cmd", MagicMock(return_value=0)
        ) as exec_ssh_cmd:
            salt.utils.cloud.sftp_file(
                "/salt.txt",
                contents=None,
                kwargs={
                    "hostname": "127.0.0.1",
                    "username": "user",
                    "server_alive_interval": salt.utils.cloud.SERVER_ALIVE_INTERVAL + 2,
                    "server_alive_count_max": salt.utils.cloud.SERVER_ALIVE_COUNT_MAX
                    + 3,
                },
                local_file="/salt.txt",
            )
            self.assertEqual(exec_ssh_cmd.call_count, 1)
            ssh_call = exec_ssh_cmd.call_args[0][0]
            self.assertIn(
                "-oServerAliveInterval={}".format(
                    salt.utils.cloud.SERVER_ALIVE_INTERVAL + 2
                ),
                ssh_call,
            )
            self.assertIn(
                "-oServerAliveCountMax={}".format(
                    salt.utils.cloud.SERVER_ALIVE_COUNT_MAX + 3
                ),
                ssh_call,
            )
