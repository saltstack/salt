"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.states.ipset as ipset
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class IpsetSetPresentTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.ipset.present
    """

    fake_name = "fake_ipset"
    fake_set_type = {"bitmap": "192.168.0.3"}

    def setup_loader_modules(self):
        return {ipset: {}}

    def _runner(
        self,
        expected_ret,
        test=False,
        check_set=False,
        new_set=None,
        new_set_assertion=True,
    ):
        mock_check_set = MagicMock(return_value=check_set)
        mock_new_set = (
            MagicMock() if new_set is None else MagicMock(return_value=new_set)
        )
        with patch.dict(
            ipset.__salt__,
            {"ipset.check_set": mock_check_set, "ipset.new_set": mock_new_set},
        ):
            with patch.dict(ipset.__opts__, {"test": test}):
                actual_ret = ipset.set_present(self.fake_name, self.fake_set_type)
        mock_check_set.assert_called_once_with(self.fake_name)
        if new_set_assertion:
            mock_new_set.assert_called_once_with(
                self.fake_name, self.fake_set_type, "ipv4"
            )
        else:
            self.assertTrue(mock_new_set.call_count == 0)
        self.assertDictEqual(actual_ret, expected_ret)

    def test_already_exists(self):
        """
        Test to verify the chain exists when it already exists.
        """
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": f"ipset set {self.fake_name} already exists for ipv4",
            "changes": {},
        }
        self._runner(ret, check_set=True, new_set_assertion=False)

    def test_needs_update_test_mode(self):
        """
        Test to verify that detects need for update but doesn't apply when in test mode.
        """

        ret = {
            "name": self.fake_name,
            "result": None,
            "comment": f"ipset set {self.fake_name} would be added for ipv4",
            "changes": {},
        }
        self._runner(ret, test=True, new_set_assertion=False)

    def test_creates_set(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": "ipset set {} created successfully for ipv4".format(
                self.fake_name
            ),
            "changes": {"locale": self.fake_name},
        }
        self._runner(ret, new_set=True)

    def test_create_fails(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": f"Failed to create set {self.fake_name} for ipv4: ",
            "changes": {},
        }
        self._runner(ret, new_set="")


class IpsetSetAbsentTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.ipset.present
    """

    fake_name = "fake_ipset"
    fake_set_type = {"bitmap": "192.168.0.3"}

    def setup_loader_modules(self):
        return {ipset: {}}

    def _runner(
        self,
        expected_ret,
        test=False,
        check_set=True,
        delete_set="",
        flush_assertion=False,
        delete_set_assertion=False,
    ):
        mock_check_set = MagicMock(return_value=check_set)
        mock_flush = MagicMock()
        mock_delete_set = (
            MagicMock() if delete_set is None else MagicMock(return_value=delete_set)
        )
        with patch.dict(ipset.__opts__, {"test": test}):
            with patch.dict(
                ipset.__salt__,
                {
                    "ipset.check_set": mock_check_set,
                    "ipset.flush": mock_flush,
                    "ipset.delete_set": mock_delete_set,
                },
            ):
                actual_ret = ipset.set_absent(self.fake_name)
        mock_check_set.assert_called_once_with(self.fake_name, "ipv4")
        if flush_assertion:
            mock_flush.assert_called_once_with(self.fake_name, "ipv4")
        else:
            self.assertTrue(mock_flush.call_count == 0)
        if delete_set_assertion:
            mock_delete_set.assert_called_once_with(self.fake_name, "ipv4")
        else:
            self.assertTrue(mock_delete_set.call_count == 0)
        self.assertDictEqual(actual_ret, expected_ret)

    def test_already_absent(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": f"ipset set {self.fake_name} for ipv4 is already absent",
            "changes": {},
        }
        self._runner(ret, check_set=False, delete_set=None)

    def test_remove_test_mode(self):
        ret = {
            "name": self.fake_name,
            "result": None,
            "comment": f"ipset set {self.fake_name} for ipv4 would be removed",
            "changes": {},
        }
        self._runner(ret, test=True, delete_set=None)

    def test_remove_fails(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": f"Failed to delete set {self.fake_name} for ipv4: ",
            "changes": {},
        }
        self._runner(ret, flush_assertion=True, delete_set_assertion=True)

    def test_remove_success(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": "ipset set {} deleted successfully for family ipv4".format(
                self.fake_name
            ),
            "changes": {"locale": "fake_ipset"},
        }
        self._runner(
            ret, delete_set=True, flush_assertion=True, delete_set_assertion=True
        )


class IpsetPresentTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.ipset.present
    """

    fake_name = "fake_ipset"
    fake_entries = ["192.168.0.3", "192.168.1.3"]

    def setup_loader_modules(self):
        return {ipset: {}}

    def _runner(
        self, expected_ret, test=False, check=False, add=False, add_assertion=False
    ):
        mock_check = MagicMock(return_value=check)
        mock_add = MagicMock(return_value=add)
        with patch.dict(ipset.__opts__, {"test": test}):
            with patch.dict(
                ipset.__salt__, {"ipset.check": mock_check, "ipset.add": mock_add}
            ):
                actual_ret = ipset.present(
                    self.fake_name, self.fake_entries, set_name=self.fake_name
                )

        mock_check.assert_has_calls(
            [call(self.fake_name, e, "ipv4") for e in self.fake_entries], any_order=True
        )
        if add_assertion:
            expected_calls = [
                call(self.fake_name, e, "ipv4", set_name=self.fake_name)
                for e in self.fake_entries
            ]
            if add is not True:
                # if the add fails, then it will only get called once.
                expected_calls = expected_calls[:1]
            mock_add.assert_has_calls(expected_calls, any_order=True)
        else:
            self.assertTrue(mock_add.call_count == 0)
        self.assertDictEqual(actual_ret, expected_ret)

    def test_entries_already_present(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": (
                "entry for 192.168.0.3 already in set {0} for ipv4\n"
                "entry for 192.168.1.3 already in set {0} for ipv4\n"
                "".format(self.fake_name)
            ),
            "changes": {},
        }
        self._runner(ret, check=True)

    def test_in_test_mode(self):
        ret = {
            "name": self.fake_name,
            "result": None,
            "comment": (
                "entry 192.168.0.3 would be added to set {0} for family ipv4\n"
                "entry 192.168.1.3 would be added to set {0} for family ipv4\n"
                "".format(self.fake_name)
            ),
            "changes": {},
        }
        self._runner(ret, test=True)

    def test_add_fails(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": (
                "Failed to add to entry 192.168.1.3 to set {} for family ipv4.\n"
                "Error".format(self.fake_name)
            ),
            "changes": {},
        }
        self._runner(ret, add="Error", add_assertion=True)

    def test_success(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": (
                "entry 192.168.0.3 added to set {0} for family ipv4\n"
                "entry 192.168.1.3 added to set {0} for family ipv4\n"
                "".format(self.fake_name)
            ),
            "changes": {"locale": "fake_ipset"},
        }
        self._runner(ret, add="worked", add_assertion=True)

    def test_missing_entry(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": "ipset entry must be specified",
            "changes": {},
        }
        mock = MagicMock(return_value=True)
        with patch.dict(ipset.__salt__, {"ipset.check": mock}):
            self.assertDictEqual(ipset.present(self.fake_name), ret)


class IpsetAbsentTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.ipset.present
    """

    fake_name = "fake_ipset"
    fake_entries = ["192.168.0.3", "192.168.1.3"]

    def setup_loader_modules(self):
        return {ipset: {}}

    def _runner(
        self,
        expected_ret,
        test=False,
        check=False,
        delete=False,
        delete_assertion=False,
    ):
        mock_check = MagicMock(return_value=check)
        mock_delete = MagicMock(return_value=delete)
        with patch.dict(ipset.__opts__, {"test": test}):
            with patch.dict(
                ipset.__salt__, {"ipset.check": mock_check, "ipset.delete": mock_delete}
            ):
                actual_ret = ipset.absent(
                    self.fake_name, self.fake_entries, set_name=self.fake_name
                )
        mock_check.assert_has_calls(
            [call(self.fake_name, e, "ipv4") for e in self.fake_entries], any_order=True
        )
        if delete_assertion:
            expected_calls = [
                call(self.fake_name, e, "ipv4", set_name=self.fake_name)
                for e in self.fake_entries
            ]
            if delete is not True:
                expected_calls = expected_calls[:1]
            mock_delete.assert_has_calls(expected_calls, any_order=True)
        else:
            self.assertTrue(mock_delete.call_count == 0)
        self.assertDictEqual(actual_ret, expected_ret)

    def test_already_absent(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": (
                "ipset entry for 192.168.0.3 not present in set {0} for ipv4\n"
                "ipset entry for 192.168.1.3 not present in set {0} for ipv4\n"
                "".format(self.fake_name)
            ),
            "changes": {},
        }
        self._runner(ret)

    def test_in_test_mode(self):
        ret = {
            "name": self.fake_name,
            "result": None,
            "comment": (
                "ipset entry 192.168.0.3 would be removed from set {0} for ipv4\n"
                "ipset entry 192.168.1.3 would be removed from set {0} for ipv4\n"
                "".format(self.fake_name)
            ),
            "changes": {},
        }
        self._runner(ret, test=True, check=True)

    def test_del_fails(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": (
                "Failed to delete ipset entry from set {} for ipv4. Attempted entry was"
                " 192.168.1.3.\nError\n".format(self.fake_name)
            ),
            "changes": {},
        }
        self._runner(ret, check=True, delete="Error", delete_assertion=True)

    def test_success(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": (
                "ipset entry 192.168.0.3 removed from set {0} for ipv4\n"
                "ipset entry 192.168.1.3 removed from set {0} for ipv4\n"
                "".format(self.fake_name)
            ),
            "changes": {"locale": "fake_ipset"},
        }
        self._runner(ret, check=True, delete="worked", delete_assertion=True)

    def test_absent(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": "ipset entry must be specified",
            "changes": {},
        }
        mock = MagicMock(return_value=True)
        with patch.dict(ipset.__salt__, {"ipset.check": mock}):
            self.assertDictEqual(ipset.absent(self.fake_name), ret)


class IpsetFlushTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.ipset.present
    """

    fake_name = "fake_ipset"

    def setup_loader_modules(self):
        return {ipset: {}}

    def _runner(
        self, expected_ret, test=False, check_set=True, flush=True, flush_assertion=True
    ):
        mock_check_set = MagicMock(return_value=check_set)
        mock_flush = MagicMock(return_value=flush)
        with patch.dict(ipset.__opts__, {"test": test}):
            with patch.dict(
                ipset.__salt__,
                {"ipset.check_set": mock_check_set, "ipset.flush": mock_flush},
            ):
                actual_ret = ipset.flush(self.fake_name)
        mock_check_set.assert_called_once_with(self.fake_name)
        if flush_assertion:
            mock_flush.assert_called_once_with(self.fake_name, "ipv4")
        else:
            self.assertTrue(mock_flush.call_count == 0)
        self.assertDictEqual(actual_ret, expected_ret)

    def test_no_set(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": f"ipset set {self.fake_name} does not exist for ipv4",
            "changes": {},
        }
        self._runner(ret, check_set=False, flush_assertion=False)

    def test_in_test_mode(self):
        ret = {
            "name": self.fake_name,
            "result": None,
            "comment": "ipset entries in set {} for ipv4 would be flushed".format(
                self.fake_name
            ),
            "changes": {},
        }
        self._runner(ret, test=True, flush_assertion=False)

    def test_flush_fails(self):
        ret = {
            "name": self.fake_name,
            "result": False,
            "comment": "Failed to flush ipset entries from set {} for ipv4".format(
                self.fake_name
            ),
            "changes": {},
        }
        self._runner(ret, flush=False)

    def test_success(self):
        ret = {
            "name": self.fake_name,
            "result": True,
            "comment": "Flushed ipset entries from set {} for ipv4".format(
                self.fake_name
            ),
            "changes": {"locale": "fake_ipset"},
        }
        self._runner(ret)
