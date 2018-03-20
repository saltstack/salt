# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''
from __future__ import absolute_import, print_function, unicode_literals
import datetime

from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salt.ext.six.moves import zip
from salt.ext import six

from salt.utils import thin
import salt.utils.stringutils

try:
    import pytest
except ImportError:
    pytest = None


class SaltSyetemExitException(Exception):
    '''
    System
    '''
    def __init__(self):
        Exception.__init__(self, 'The Dilithium Crystals need to be rotated.')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class SSHThinTestCase(TestCase):
    '''
    TestCase for SaltSSH-related parts.
    '''
    @patch('salt.exceptions.SaltSystemExit', MagicMock(side_effect=SaltSyetemExitException))
    @patch('salt.utils.thin.log', MagicMock())
    def test_get_ext_tops_cfg_missing_dependencies(self):
        '''
        Test thin.get_tops

        :return:
        '''
        cfg = [
            {'namespace': {'path': '/foo', 'dependencies': []}},
        ]
        with pytest.raises(Exception) as err:
            thin.get_ext_tops(cfg)
        assert 'Dilithium Crystals' in str(err)
        assert thin.log.error.called
        assert 'Missing dependencies' in thin.log.error.call_args[0][0]
        assert 'jinja2, yaml, tornado, msgpack' in thin.log.error.call_args[0][0]
