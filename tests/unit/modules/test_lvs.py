"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""


import salt.modules.lvs as lvs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class LvsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.lvs
    """

    def setup_loader_modules(self):
        return {lvs: {}}

    def test_add_service(self):
        """
        Test for Add a virtual service.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.add_service(), "stderr")

    def test_edit_service(self):
        """
        Test for Edit the virtual service.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.edit_service(), "stderr")

    def test_delete_service(self):
        """
        Test for Delete the virtual service.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.delete_service(), "stderr")

    def test_add_server(self):
        """
        Test for Add a real server to a virtual service.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.add_server(), "stderr")

    def test_edit_server(self):
        """
        Test for Edit a real server to a virtual service.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.edit_server(), "stderr")

    def test_delete_server(self):
        """
        Test for Delete the realserver from the virtual service.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.delete_server(), "stderr")

    def test_clear(self):
        """
        Test for Clear the virtual server table
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                self.assertEqual(lvs.clear(), "stderr")

    def test_get_rules(self):
        """
        Test for Get the virtual server rules
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.dict(lvs.__salt__, {"cmd.run": MagicMock(return_value="A")}):
                self.assertEqual(lvs.get_rules(), "A")

    def test_list_(self):
        """
        Test for List the virtual server table
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.list_("p", "s"), "stderr")

    def test_zero(self):
        """
        Test for Zero the packet, byte and rate counters in a
         service or all services.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    self.assertEqual(lvs.zero("p", "s"), "stderr")

    def test_check_service(self):
        """
        Test for Check the virtual service exists.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    with patch.object(lvs, "get_rules", return_value="C"):
                        self.assertEqual(
                            lvs.check_service("p", "s"), "Error: service not exists"
                        )

    def test_check_server(self):
        """
        Test for Check the real server exists in the specified service.
        """
        with patch.object(lvs, "__detect_os", return_value="C"):
            with patch.object(lvs, "_build_cmd", return_value="B"):
                with patch.dict(
                    lvs.__salt__,
                    {
                        "cmd.run_all": MagicMock(
                            return_value={"retcode": "ret", "stderr": "stderr"}
                        )
                    },
                ):
                    with patch.object(lvs, "get_rules", return_value="C"):
                        self.assertEqual(
                            lvs.check_server("p", "s"), "Error: server not exists"
                        )
