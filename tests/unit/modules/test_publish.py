"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.publish as publish
from salt.exceptions import SaltReqTimeoutError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SAuth:
    """
    Mock SAuth class
    """

    def __init__(self, __opts__):
        self.tok = None

    def gen_token(self, tok):
        """
        Mock gen_token method
        """
        self.tok = tok
        return "salt_tok"


class Channel:
    """
    Mock Channel class
    """

    flag = None

    def __init__(self):
        self.tok = None
        self.load = None

    def factory(self, tok):
        """
        Mock factory method
        """
        self.tok = tok
        return Channel()

    def send(self, load):
        """
        Mock send method
        """
        self.load = load
        if self.flag == 1:
            raise SaltReqTimeoutError
        return True

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class PublishTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.publish
    """

    def setup_loader_modules(self):
        return {publish: {}}

    @classmethod
    def setUpClass(cls):
        cls.channel_patcher = patch("salt.transport.client.ReqChannel", Channel())
        cls.channel_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.channel_patcher.stop()
        del cls.channel_patcher

    def setUp(self):
        patcher = patch("salt.crypt.SAuth", return_value=SAuth(publish.__opts__))
        patcher.start()
        self.addCleanup(patcher.stop)

    # 'publish' function tests: 1

    def test_publish(self):
        """
        Test if it publish a command from the minion out to other minions.
        """
        self.assertDictEqual(publish.publish("os:Fedora", "publish.salt"), {})

    # 'full_data' function tests: 1

    def test_full_data(self):
        """
        Test if it return the full data about the publication
        """
        self.assertDictEqual(publish.publish("*", "publish.salt"), {})

    # 'runner' function tests: 1

    def test_runner(self):
        """
        Test if it execute a runner on the master and return the data
        from the runner function
        """
        ret = "No access to master. If using salt-call with --local, please remove."
        self.assertEqual(publish.runner("manage.down"), ret)

        mock = MagicMock(return_value=True)
        mock_id = MagicMock(return_value="salt_id")
        with patch.dict(publish.__opts__, {"master_uri": mock, "id": mock_id}):
            Channel.flag = 0
            self.assertTrue(publish.runner("manage.down"))

            Channel.flag = 1
            self.assertEqual(
                publish.runner("manage.down"), "'manage.down' runner publish timed out"
            )
