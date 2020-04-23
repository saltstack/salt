# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Testing libs
from tests.support.case import ModuleCase, ShellCase
<<<<<<< HEAD
=======
from tests.support.unit import skipIf
>>>>>>> 8d70836c614efff36c045d0a87f7a94614409610

log = logging.getLogger(__name__)


class ExecutorTest(ModuleCase, ShellCase):
<<<<<<< HEAD

    def setup(self):
        self.run_function('saltutil.sync_all')

    def test_executor(self):
        '''
        test that dunders are set
        '''
        data = self.run_call('test.arg --module-executors=arg')
        self.assertIn('test.arg fired', "".join(data))
=======
    def setup(self):
        self.run_function("saltutil.sync_all")

    @skipIf(True, "SLOWTEST skip")
    def test_executor(self):
        """
        test that dunders are set
        """
        data = self.run_call("test.arg --module-executors=arg")
        self.assertIn("test.arg fired", "".join(data))
>>>>>>> 8d70836c614efff36c045d0a87f7a94614409610
