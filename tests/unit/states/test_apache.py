# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch,
    mock_open)

# Import Salt Libs
import salt.states.apache as apache
import salt.utils

apache.__opts__ = {}
apache.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ApacheTestCase(TestCase):
    '''
    Test cases for salt.states.apache
    '''
    # 'configfile' function tests: 1

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_configfile(self):
        '''
        Test to allows for inputting a yaml dictionary into a file
        for apache configuration files.
        '''
        name = '/etc/distro/specific/apache.conf'
        config = 'VirtualHost: this: "*:80"'
        new_config = 'LiteralHost: that: "*:79"'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        with patch.object(salt.utils, 'fopen', mock_open(read_data=config)):
            mock_config = MagicMock(return_value=config)
            with patch.dict(apache.__salt__, {'apache.config': mock_config}):
                ret.update({'comment': 'Configuration is up to date.'})
                self.assertDictEqual(apache.configfile(name, config), ret)

        with patch.object(salt.utils, 'fopen', mock_open(read_data=config)):
            mock_config = MagicMock(return_value=new_config)
            with patch.dict(apache.__salt__, {'apache.config': mock_config}):
                ret.update({'comment': 'Configuration will update.',
                            'changes': {'new': new_config,
                                        'old': config},
                            'result': None})
                with patch.dict(apache.__opts__, {'test': True}):
                    self.assertDictEqual(apache.configfile(name, new_config), ret)

        with patch.object(salt.utils, 'fopen', mock_open(read_data=config)):
            mock_config = MagicMock(return_value=new_config)
            with patch.dict(apache.__salt__, {'apache.config': mock_config}):
                ret.update({'comment': 'Successfully created configuration.',
                            'result': True})
                with patch.dict(apache.__opts__, {'test': False}):
                    self.assertDictEqual(apache.configfile(name, config), ret)
