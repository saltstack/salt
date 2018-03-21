# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''
from __future__ import absolute_import, print_function, unicode_literals

from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

import salt.exceptions
from salt.utils import thin
import salt.utils.stringutils

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class SSHThinTestCase(TestCase):
    '''
    TestCase for SaltSSH-related parts.
    '''

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_missing_dependencies(self):
        '''
        Test thin.get_ext_tops contains all required dependencies.

        :return:
        '''
        cfg = {'namespace': {'py-version': [0, 0], 'path': '/foo', 'dependencies': []}}

        with pytest.raises(Exception) as err:
            thin.get_ext_tops(cfg)
        assert 'Missing dependencies' in str(err)
        assert thin.log.error.called
        assert 'Missing dependencies' in thin.log.error.call_args[0][0]
        assert 'jinja2, yaml, tornado, msgpack' in thin.log.error.call_args[0][0]

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_missing_interpreter(self):
        '''
        Test thin.get_ext_tops contains interpreter configuration.

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'dependencies': []}}
        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        assert 'missing specific locked Python version' in str(err)

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_wrong_interpreter(self):
        '''
        Test thin.get_ext_tops contains correct interpreter configuration.

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': 2,
                             'dependencies': []}}

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        assert 'specific locked Python version should be a list of major/minor version' in str(err)

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_interpreter(self):
        '''
        Test thin.get_ext_tops interpreter configuration.

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': [2, 6],
                             'dependencies': {'jinja2': '',
                                              'yaml': '',
                                              'tornado': '',
                                              'msgpack': ''}}}

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        assert len(thin.log.warning.mock_calls) == 4
        assert sorted([x[1][1] for x in thin.log.warning.mock_calls]) == ['jinja2', 'msgpack', 'tornado', 'yaml']
        assert 'Module test has missing configuration' == thin.log.warning.mock_calls[0][1][0] % 'test'

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_dependency_config_check(self):
        '''
        Test thin.get_ext_tops dependencies are importable

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': [2, 6],
                             'dependencies': {'jinja2': '/jinja/foo.py',
                                              'yaml': '/yaml/',
                                              'tornado': '/tornado/wrong.rb',
                                              'msgpack': 'msgpack.sh'}}}

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        assert 'Missing dependencies for the alternative version in the external configuration' in str(err)

        messages = {}
        for cl in thin.log.warning.mock_calls:
            messages[cl[1][1]] = cl[1][0] % (cl[1][1], cl[1][2])
        for mod in ['tornado', 'yaml', 'msgpack']:
            assert 'not a Python importable module' in messages[mod]
        assert 'configured with not a file or does not exist' in messages['jinja2']

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=True))
    def test_get_ext_tops_config_pass(self):
        '''
        Test thin.get_ext_tops configuration

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': [2, 6],
                             'dependencies': {'jinja2': '/jinja/foo.py',
                                              'yaml': '/yaml/',
                                              'tornado': '/tornado/tornado.py',
                                              'msgpack': 'msgpack.py'}}}
        assert cfg == thin.get_ext_tops(cfg)
