# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.ext.six as six
from salt.utils.odict import OrderedDict
import salt.modules.pillar as pillarmod


pillar_value_1 = dict(a=1, b='very secret')


class PillarModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {pillarmod: {}}

    def test_obfuscate_inner_recursion(self):
        self.assertEqual(
                pillarmod._obfuscate_inner(dict(a=[1, 2],
                                                b=dict(pwd='secret', deeper=('a', 1)))),
                dict(a=['<int>', '<int>'],
                     b=dict(pwd='<str>', deeper=('<str>', '<int>')))
        )

    def test_obfuscate_inner_more_types(self):
        self.assertEqual(pillarmod._obfuscate_inner(OrderedDict([('key', 'value')])),
                         OrderedDict([('key', '<str>')]))

        self.assertEqual(pillarmod._obfuscate_inner(set((1, 2))),
                         set(['<int>']))

        self.assertEqual(pillarmod._obfuscate_inner((1, 2)),
                         ('<int>', '<int>'))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @patch('salt.modules.pillar.items', MagicMock(return_value=pillar_value_1))
    def test_obfuscate(self):
        self.assertEqual(pillarmod.obfuscate(),
                         dict(a='<int>', b='<str>'))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @patch('salt.modules.pillar.items', MagicMock(return_value=pillar_value_1))
    def test_ls(self):
        if six.PY3:
            self.assertCountEqual(pillarmod.ls(), ['a', 'b'])
        else:
            self.assertEqual(pillarmod.ls(), ['a', 'b'])

    def test_pillar_get_default_merge(self):
        with patch.dict(pillarmod.__pillar__, {'key': 'value'}):
            default = {'default': 'plop'}

            res = pillarmod.get(key='key', default=default)
            self.assertEqual("value", res)

            res = pillarmod.get(key='missing pillar', default=default)
            self.assertEqual({'default': 'plop'}, res)

    def test_pillar_get_default_merge_regression_38558(self):
        """Test for pillar.get(key=..., default=..., merge=True)

        Do not update the ``default`` value when using ``merge=True``.

        See: https://github.com/saltstack/salt/issues/38558
        """
        with patch.dict(pillarmod.__pillar__, {'l1': {'l2': {'l3': 42}}}):

            res = pillarmod.get(key='l1')
            self.assertEqual({'l2': {'l3': 42}}, res)

            default = {'l2': {'l3': 43}}

            res = pillarmod.get(key='l1', default=default)
            self.assertEqual({'l2': {'l3': 42}}, res)
            self.assertEqual({'l2': {'l3': 43}}, default)

            res = pillarmod.get(key='l1', default=default, merge=True)
            self.assertEqual({'l2': {'l3': 42}}, res)
            self.assertEqual({'l2': {'l3': 43}}, default)

    def test_pillar_get_default_merge_regression_39062(self):
        '''
        Confirm that we do not raise an exception if default is None and
        merge=True.

        See https://github.com/saltstack/salt/issues/39062 for more info.
        '''
        with patch.dict(pillarmod.__pillar__, {'foo': 'bar'}):

            self.assertEqual(
                pillarmod.get(key='foo', default=None, merge=True),
                'bar',
            )
