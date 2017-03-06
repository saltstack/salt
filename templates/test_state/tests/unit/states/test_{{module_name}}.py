# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`{{full_name}} <{{email}}>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.unit import ModuleTestCase, hasDependency
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salt.states import {{module_name}}

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
