# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.portage_config as portage_config


class PortageConfigTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.portage_config
    '''
    def setup_loader_modules(self):
        return {portage_config: {'__opts__': {'test': True}}}

    # 'mod_init' function tests: 1

    def test_mod_init(self):
        '''
        Test to enforce a nice structure on the configuration files.
        '''
        name = 'salt'

        mock = MagicMock(side_effect=[True, Exception])
        with patch.dict(portage_config.__salt__,
                        {'portage_config.enforce_nice_config': mock}):
            assert portage_config.mod_init(name)

            assert not portage_config.mod_init(name)

    # 'flags' function tests: 1

    def test_flags(self):
        '''
        Test to enforce the given flags on the given package or ``DEPEND`` atom.
        '''
        with patch('traceback.format_exc', MagicMock(return_value='SALTSTACK')):
            name = 'salt'

            ret = {'name': name,
                   'result': False,
                   'comment': 'SALTSTACK',
                   'changes': {}}

            mock = MagicMock(side_effect=Exception('error'))
            with patch.dict(portage_config.__salt__,
                            {'portage_config.get_missing_flags': mock}):
                assert portage_config.flags(name, use='openssl') == ret

                assert portage_config.flags(name,
                                                          accept_keywords=True) == \
                                     ret

                assert portage_config.flags(name, env=True) == ret

                assert portage_config.flags(name, license=True) == ret

                assert portage_config.flags(name, properties=True) == \
                                     ret

                assert portage_config.flags(name, mask=True) == ret

                assert portage_config.flags(name, unmask=True) == ret

                ret.update({'comment': '', 'result': True})
                assert portage_config.flags(name) == ret
