# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`{{full_name}} <{{email}}>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf
from tests.unit import ModuleTestCase, hasDependency
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath
from salt.states import {{module_name}}

ensure_in_syspath('../../')

SERVICE_NAME = '{{module_name}}'
{{module_name}}.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class {{module_name|capitalize}}TestCase(ModuleTestCase):
    def setUp(self):
        # Optionally, tell the tests that you have a module installed into sys.modules
        #  hasDependency('library_name')

        def get_config(service):
            #  generator for the configuration of the tests
            return {}

        self.setup_loader()
        self.loader.set_result({{module_name}}, 'config.option', get_config)

    def test_behaviour(self):
        #  Test inherent behaviours
        pass

if __name__ == '__main__':
    from unit import run_tests
    run_tests({{module_name|capitalize}}TestCase)

