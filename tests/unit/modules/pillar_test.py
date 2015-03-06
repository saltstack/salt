# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt libs
from salt.utils.odict import OrderedDict
from salt.modules import pillar as pillarmod


pillar_value_1 = dict(a=1, b='very secret')


class PillarModuleTestCase(TestCase):

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
        self.assertEqual(pillarmod.ls(), ['a', 'b'])


# gracinet: not sure this is really useful, but other test modules have this as well
if __name__ == '__main__':
    from integration import run_tests
    run_tests(PillarModuleTestCase, needs_daemon=False)
