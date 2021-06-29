"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

from salt.cli.batch import Batch
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class BatchTestCase(TestCase):
    """
    Unit Tests for the salt.cli.batch module
    """

    def setUp(self):
        opts = {
            "batch": "",
            "conf_file": {},
            "tgt": "",
            "transport": "",
            "timeout": 5,
            "gather_job_timeout": 5,
        }

        mock_client = MagicMock()
        with patch("salt.client.get_local_client", MagicMock(return_value=mock_client)):
            with patch("salt.client.LocalClient.cmd_iter", MagicMock(return_value=[])):
                self.batch = Batch(opts, quiet="quiet")

    # get_bnum tests

    def test_get_bnum_str(self):
        """
        Tests passing batch value as a number(str)
        """
        self.batch.opts = {"batch": "2", "timeout": 5}
        self.batch.minions = ["foo", "bar"]
        self.assertEqual(Batch.get_bnum(self.batch), 2)

    def test_get_bnum_int(self):
        """
        Tests passing batch value as a number(int)
        """
        self.batch.opts = {"batch": 2, "timeout": 5}
        self.batch.minions = ["foo", "bar"]
        self.assertEqual(Batch.get_bnum(self.batch), 2)

    def test_get_bnum_percentage(self):
        """
        Tests passing batch value as percentage
        """
        self.batch.opts = {"batch": "50%", "timeout": 5}
        self.batch.minions = ["foo"]
        self.assertEqual(Batch.get_bnum(self.batch), 1)

    def test_get_bnum_high_percentage(self):
        """
        Tests passing batch value as percentage over 100%
        """
        self.batch.opts = {"batch": "160%", "timeout": 5}
        self.batch.minions = ["foo", "bar", "baz"]
        self.assertEqual(Batch.get_bnum(self.batch), 4)

    def test_get_bnum_invalid_batch_data(self):
        """
        Tests when an invalid batch value is passed
        """
        ret = Batch.get_bnum(self.batch)
        self.assertEqual(ret, None)

    def test_return_value_in_run_for_ret(self):
        """
        cmd_iter_no_block should have been called with a return no matter if
        the return value was in ret or return.
        """
        self.batch.opts = {
            "batch": "100%",
            "timeout": 5,
            "fun": "test",
            "arg": "foo",
            "gather_job_timeout": 5,
            "ret": "my_return",
        }
        self.batch.gather_minions = MagicMock(
            return_value=[["foo", "bar", "baz"], [], []],
        )
        self.batch.local.cmd_iter_no_block = MagicMock(return_value=iter([]))
        ret = Batch.run(self.batch)
        # We need to fetch at least one object to trigger the relevant code path.
        x = next(ret)
        self.batch.local.cmd_iter_no_block.assert_called_with(
            ["baz", "bar", "foo"],
            "test",
            "foo",
            5,
            "list",
            raw=False,
            ret="my_return",
            show_jid=False,
            verbose=False,
            gather_job_timeout=5,
        )

    def test_return_value_in_run_for_return(self):
        """
        cmd_iter_no_block should have been called with a return no matter if
        the return value was in ret or return.
        """
        self.batch.opts = {
            "batch": "100%",
            "timeout": 5,
            "fun": "test",
            "arg": "foo",
            "gather_job_timeout": 5,
            "return": "my_return",
        }
        self.batch.gather_minions = MagicMock(
            return_value=[["foo", "bar", "baz"], [], []],
        )
        self.batch.local.cmd_iter_no_block = MagicMock(return_value=iter([]))
        ret = Batch.run(self.batch)
        # We need to fetch at least one object to trigger the relevant code path.
        x = next(ret)
        self.batch.local.cmd_iter_no_block.assert_called_with(
            ["baz", "bar", "foo"],
            "test",
            "foo",
            5,
            "list",
            raw=False,
            ret="my_return",
            show_jid=False,
            verbose=False,
            gather_job_timeout=5,
        )
