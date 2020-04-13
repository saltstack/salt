# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

from tests.support.case import ModuleCase

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS


class PillarModuleTest(ModuleCase):
    """
    Validate the pillar module
    """

    def test_data(self):
        """
        pillar.data
        """
        grains = self.run_function("grains.items")
        pillar = self.run_function("pillar.data")
        self.assertEqual(pillar["os"], grains["os"])
        self.assertEqual(pillar["monty"], "python")
        if grains["os"] == "Fedora":
            self.assertEqual(pillar["class"], "redhat")
        else:
            self.assertEqual(pillar["class"], "other")

    def test_issue_5449_report_actual_file_roots_in_pillar(self):
        """
        pillar['master']['file_roots'] is overwritten by the master
        in order to use the fileclient interface to read the pillar
        files. We should restore the actual file_roots when we send
        the pillar back to the minion.
        """
        self.assertIn(
            RUNTIME_VARS.TMP_STATE_TREE,
            self.run_function("pillar.data")["master"]["file_roots"]["base"],
        )

    def test_ext_cmd_yaml(self):
        """
        pillar.data for ext_pillar cmd.yaml
        """
        self.assertEqual(self.run_function("pillar.data")["ext_spam"], "eggs")

    def test_issue_5951_actual_file_roots_in_opts(self):
        self.assertIn(
            RUNTIME_VARS.TMP_STATE_TREE,
            self.run_function("pillar.data")["ext_pillar_opts"]["file_roots"]["base"],
        )

    def test_pillar_items(self):
        """
        Test to ensure we get expected output
        from pillar.items
        """
        get_items = self.run_function("pillar.items")
        self.assertDictContainsSubset({"monty": "python"}, get_items)
        self.assertDictContainsSubset(
            {"knights": ["Lancelot", "Galahad", "Bedevere", "Robin"]}, get_items
        )

    def test_pillar_command_line(self):
        """
        Test to ensure when using pillar override
        on command line works
        """
        # test when pillar is overwriting previous pillar
        overwrite = self.run_function("pillar.items", pillar={"monty": "overwrite"})
        self.assertDictContainsSubset({"monty": "overwrite"}, overwrite)

        # test when using additional pillar
        additional = self.run_function("pillar.items", pillar={"new": "additional"})

        self.assertDictContainsSubset({"new": "additional"}, additional)
