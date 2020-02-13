# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.smartos as smartos

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import patch


class SmartOsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.states.smartos
    '''

    def setup_loader_modules(self):
        return {smartos: {
                  '__opts__': {'test': False}}
        }

    def test_config_present_does_not_exist(self):
        '''
        Test salt.states.smartos.config_present
        when the config files does not exist
        '''
        name = 'test'
        value = 'test_value'
        with patch('os.path.isfile', return_value=False):
            with patch('salt.utils.atomicfile.atomic_open', side_effect=IOError):
                ret = smartos.config_present(name=name, value=value)
        assert not ret['result']
        assert ret['comment'] == 'Could not add property {0} with value "{1}" to config'.format(name, value)
