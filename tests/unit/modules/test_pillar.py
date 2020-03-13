# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt libs
from salt.ext import six
from salt.utils.odict import OrderedDict
import salt.modules.pillar as pillarmod
import pytest


pillar_value_1 = dict(a=1, b='very secret')


class PillarModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {pillarmod: {}}

    def test_obfuscate_inner_recursion(self):
        assert pillarmod._obfuscate_inner(dict(a=[1, 2],
                                                b=dict(pwd='secret', deeper=('a', 1)))) == \
                dict(a=['<int>', '<int>'],
                     b=dict(pwd='<str>', deeper=('<str>', '<int>')))

    def test_obfuscate_inner_more_types(self):
        assert pillarmod._obfuscate_inner(OrderedDict([('key', 'value')])) == \
                         OrderedDict([('key', '<str>')])

        assert pillarmod._obfuscate_inner(set((1, 2))) == \
                         set(['<int>'])

        assert pillarmod._obfuscate_inner((1, 2)) == \
                         ('<int>', '<int>')

    def test_obfuscate(self):
        with patch('salt.modules.pillar.items', MagicMock(return_value=pillar_value_1)):
            assert pillarmod.obfuscate() == \
                             dict(a='<int>', b='<str>')

    def test_ls(self):
        with patch('salt.modules.pillar.items', MagicMock(return_value=pillar_value_1)):
            ls = sorted(pillarmod.ls())
            if six.PY3:
                self.assertCountEqual(ls, ['a', 'b'])
            else:
                assert ls == ['a', 'b']

    def test_pillar_get_default_merge(self):
        defaults = {'int': 1,
                    'string': 'foo',
                    'list': ['foo'],
                    'dict': {'foo': 'bar', 'subkey': {'foo': 'bar'}}}

        pillar_mock = {'int': 2,
                       'string': 'bar',
                       'list': ['bar', 'baz'],
                       'dict': {'baz': 'qux', 'subkey': {'baz': 'qux'}}}

        # Test that we raise a KeyError when pillar_raise_on_missing is True
        with patch.dict(pillarmod.__opts__, {'pillar_raise_on_missing': True}):
            with pytest.raises(KeyError):
                pillarmod.get('missing')
        # Test that we return an empty string when it is not
        with patch.dict(pillarmod.__opts__, {}):
            assert pillarmod.get('missing') == ''

        with patch.dict(pillarmod.__pillar__, pillar_mock):
            # Test with no default passed (it should be KeyError) and merge=True.
            # The merge should be skipped and the value returned from __pillar__
            # should be returned.
            for item in pillarmod.__pillar__:
                assert pillarmod.get(item, merge=True) == \
                    pillarmod.__pillar__[item]

            # Test merging when the type of the default value is not the same as
            # what was returned. Merging should be skipped and the value returned
            # from __pillar__ should be returned.
            for default_type in defaults:
                for data_type in ('dict', 'list'):
                    if default_type == data_type:
                        continue
                    assert pillarmod.get(data_type, default=defaults[default_type], merge=True) == \
                        pillarmod.__pillar__[data_type]

            # Test recursive dict merging
            assert pillarmod.get('dict', default=defaults['dict'], merge=True) == \
                {'foo': 'bar', 'baz': 'qux', 'subkey': {'foo': 'bar', 'baz': 'qux'}}

            # Test list merging
            assert pillarmod.get('list', default=defaults['list'], merge=True) == \
                ['foo', 'bar', 'baz']

    def test_pillar_get_default_merge_regression_38558(self):
        """Test for pillar.get(key=..., default=..., merge=True)

        Do not update the ``default`` value when using ``merge=True``.

        See: https://github.com/saltstack/salt/issues/38558
        """
        with patch.dict(pillarmod.__pillar__, {'l1': {'l2': {'l3': 42}}}):

            res = pillarmod.get(key='l1')
            assert {'l2': {'l3': 42}} == res

            default = {'l2': {'l3': 43}}

            res = pillarmod.get(key='l1', default=default)
            assert {'l2': {'l3': 42}} == res
            assert {'l2': {'l3': 43}} == default

            res = pillarmod.get(key='l1', default=default, merge=True)
            assert {'l2': {'l3': 42}} == res
            assert {'l2': {'l3': 43}} == default

    def test_pillar_get_default_merge_regression_39062(self):
        '''
        Confirm that we do not raise an exception if default is None and
        merge=True.

        See https://github.com/saltstack/salt/issues/39062 for more info.
        '''
        with patch.dict(pillarmod.__pillar__, {'foo': 'bar'}):

            assert pillarmod.get(key='foo', default=None, merge=True) == \
                'bar'
