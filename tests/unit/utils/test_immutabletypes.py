# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.utils.immutabletypes
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt.utils.immutabletypes
"""

# Import Python libs
from __future__ import absolute_import, unicode_literals

# Import salt libs
import salt.utils.immutabletypes as immutabletypes

# Import Salt Testing libs
from tests.support.unit import TestCase


class ImmutableTypesTestCase(TestCase):
    def test_immutablelist_sum(self):
        lst = [4, 5, 6]
        imt = immutabletypes.ImmutableList([1, 2, 3])
        __add__ = imt + lst
        self.assertEqual(__add__, [1, 2, 3, 4, 5, 6])
        __radd__ = lst + imt
        self.assertEqual(__radd__, [4, 5, 6, 1, 2, 3])

    def test_freeze_list_sum(self):
        lst = [4, 5, 6]
        imt = immutabletypes.freeze([1, 2, 3])
        __add__ = imt + lst
        self.assertEqual(__add__, [1, 2, 3, 4, 5, 6])
        __radd__ = lst + imt
        self.assertEqual(__radd__, [4, 5, 6, 1, 2, 3])

    def test_immutablelist_imutability(self):
        frozen = immutabletypes.freeze([1, 2, 3])
        with self.assertRaises(TypeError):
            frozen[1] = 2

        with self.assertRaises(TypeError):
            frozen[1:-1] = 5

    def test_immutabledict_imutability(self):
        data = {
            1: 1,
            2: 2,
            3: {
                3.1: 3.1,
                3.2: 3.2,
                3.3: {3.31: 3.33, 3.32: 3.34, 3.33: [3.331, 3.332, 3.333]},
            },
            4: [4.1, 4.2, 4.3],
        }
        frozen = immutabletypes.freeze(data)
        with self.assertRaises(TypeError):
            frozen[1] = 2

        with self.assertRaises(TypeError):
            fdict = frozen[3]
            fdict[3.1] = 5

        with self.assertRaises(TypeError):
            fdict = frozen[3]
            fdict[3.4] = 3.4

        with self.assertRaises(TypeError):
            frozen[3][3.3][3.32] = 3.99

        with self.assertRaises(TypeError):
            frozen[3][3.3][3.33][0] = 5

        with self.assertRaises(TypeError):
            flist = frozen[4]
            flist[0] = 5
