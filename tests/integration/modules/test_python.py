# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase


class PythonModuleTest(ModuleCase):
    def test_python_exec_source(self):
        ret = self.run_function('python.exec', source='salt://test_pythonmod.py', entry='main')
        self.assertEqual(ret, 'Success')

    def test_python_exec_contents(self):
        contents = textwrap.dedent('''
            def main():
                return 'Success'
        ''')
        ret = self.run_function('python.exec', contents=contents, entry='main')
        self.assertEqual(ret, 'Success')
