# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.tops.saltclass as saltclass

base_path = os.path.dirname(os.path.realpath(__file__))
fake_minion = 'fake_id2'

fake_pillar = {}
fake_path = os.path.abspath(os.path.join(
            base_path, '..', '..', 'integration', 'files', 'saltclass', 'examples-new'))
fake_opts = {}
fake_salt = {}
fake_grains = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltclassTestCase(TestCase, LoaderModuleMockMixin):
    '''
    New tests for salt.pillar.saltclass
    '''

    def setup_loader_modules(self):
        return {
            saltclass: {
                    '__opts__': {
                        'master_tops': {
                            'saltclass': {
                                'path': fake_path
                            }
                        }
                    }
            }
        }

    def test_saltclass_tops(self):
        expected_result = ['state_B', 'state_C.1', 'state_C.9999']
        result = saltclass.top(opts={'id': fake_minion}, grains={})
        filtered_result = result['test']
        self.assertEqual(filtered_result, expected_result)
