# -*- coding: utf-8 -*-
'''
Tests for loop state(s)
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.states.loop as loop


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LoopTestCase(TestCase, LoaderModuleMockMixin):

    mock = MagicMock(return_value=True)
    func = 'foo.bar'
    m_args = ['foo', 'bar', 'baz']
    m_kwargs = {'hello': 'world'}
    condition = 'm_ret is True'
    period = 1
    timeout = 3

    def setup_loader_modules(self):
        return {
            loop: {
                '__opts__': {'test': False},
                '__salt__': {self.func: self.mock},
            }
        }

    def setUp(self):
        self.mock.reset_mock()

    def test_until(self):
        ret = loop.until(
            name=self.func,
            m_args=self.m_args,
            m_kwargs=self.m_kwargs,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout)
        assert ret['result'] is True
        self.mock.assert_called_once_with(*self.m_args, **self.m_kwargs)

    def test_until_without_args(self):
        ret = loop.until(
            name=self.func,
            m_kwargs=self.m_kwargs,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout)
        assert ret['result'] is True
        self.mock.assert_called_once_with(**self.m_kwargs)

    def test_until_without_kwargs(self):
        ret = loop.until(
            name=self.func,
            m_args=self.m_args,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout)
        assert ret['result'] is True
        self.mock.assert_called_once_with(*self.m_args)

    def test_until_without_args_or_kwargs(self):
        ret = loop.until(
            name=self.func,
            condition=self.condition,
            period=self.period,
            timeout=self.timeout)
        assert ret['result'] is True
        self.mock.assert_called_once_with()
