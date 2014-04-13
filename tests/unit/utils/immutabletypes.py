# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2014 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.utils.immutabletypes
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt.utils.immutabletypes
'''

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import immutabletypes


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
                3.3: {
                    3.31: 3.33,
                    3.32: 3.34,
                    3.33: [3.331, 3.332, 3.333]
                }
            },
            4: [4.1, 4.2, 4.3]
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ImmutableTypesTestCase, needs_daemon=False)
