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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ImmutableTypesTestCase, needs_daemon=False)
