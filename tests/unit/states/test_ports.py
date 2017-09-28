# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salt.exceptions import SaltInvocationError

# Import Salt Libs
import salt.states.ports as ports


class MockModule(object):
    """
    Mock of __module__
    """
    __module__ = 'A'


class MockContext(object):
    """
    Mock of __context__
    """
    __context__ = {'ports.install_error': 'salt'}


class MockSys(object):
    """
    Mock of sys
    """
    def __init__(self):
        self.modules = {'A': MockContext()}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PortsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.ports
    '''
    def setup_loader_modules(self):
        return {ports: {'sys': MockSys()}}

    # 'installed' function tests: 1

    def test_installed(self):
        '''
        Test to verify that the desired port is installed,
        and that it was compiled with the desired options.
        '''
        name = 'security/nmap'
        options = [{'IPV6': 'on'}]

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=SaltInvocationError)
        with patch.dict(ports.__salt__, {'ports.showconfig': mock}):
            comt = ('Unable to get configuration for {0}. Port name may '
                    'be invalid, or ports tree may need to be updated. '
                    'Error message: '.format(name))
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(ports.installed(name), ret)

        mock = MagicMock(return_value={})
        mock_lst = MagicMock(return_value={'origin': {'origin': name}})
        with patch.dict(ports.__salt__, {'ports.showconfig': mock,
                                         'pkg.list_pkgs': mock_lst}):
            comt = ('security/nmap is already installed')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(ports.installed(name), ret)

            comt = ('security/nmap does not have any build options,'
                    ' yet options were specified')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(ports.installed(name, options), ret)

            mock_dict = MagicMock(return_value={'origin': {'origin': 'salt'}})
            with patch.dict(ports.__salt__, {'pkg.list_pkgs': mock_dict}):
                with patch.dict(ports.__opts__, {'test': True}):
                    comt = ('{0} will be installed'.format(name))
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(ports.installed(name), ret)

        mock = MagicMock(return_value={'salt': {'salt': 'salt'}})
        mock_dict = MagicMock(return_value={'origin': {'origin': 'salt'}})
        mock_f = MagicMock(return_value=False)
        mock_t = MagicMock(return_value=True)
        with patch.dict(ports.__salt__, {'ports.showconfig': mock,
                                         'pkg.list_pkgs': mock_dict,
                                         'ports.config': mock_f,
                                         'ports.rmconfig': mock_t}):
            with patch.dict(ports.__opts__, {'test': True}):
                comt = ('The following options are not available'
                        ' for security/nmap: IPV6')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(ports.installed(name, options), ret)

                comt = ('security/nmap will be installed with the '
                        'default build options')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(ports.installed(name), ret)

            with patch.dict(ports.__opts__, {'test': False}):
                comt = ('Unable to set options for security/nmap')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(ports.installed(name, [{'salt': 'salt'}]),
                                     ret)

                with patch.object(os.path, 'isfile', mock_t):
                    with patch.object(os.path, 'isdir', mock_t):
                        comt = ('Unable to clear options for security/nmap')
                        ret.update({'comment': comt, 'result': False})
                        self.assertDictEqual(ports.installed(name), ret)

                with patch.dict(ports.__salt__, {'ports.config': mock_t,
                                                 'ports.install': mock_t,
                                                 'test.ping': MockModule()}):
                    comt = ('Failed to install security/nmap.'
                            ' Error message:\nsalt')
                    ret.update({'comment': comt, 'result': False,
                                'changes': True})
                    self.assertDictEqual(ports.installed(name,
                                                         [{'salt': 'salt'}]),
                                         ret)
