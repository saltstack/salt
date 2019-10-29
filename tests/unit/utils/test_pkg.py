# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
# Import Salt Libs
import salt.utils.pkg
import salt.utils.pkg.rpm
# Import Salt Testing Libs
from tests.support.unit import TestCase


class PkgUtilsTestCase(TestCase):
    '''
    TestCase for salt.utils.pkg module
    '''
    test_parameters = [
        ("16.0.0.49153-0+f1", "", "16.0.0.49153-0+f1"),
        ("> 15.0.0", ">", "15.0.0"),
        ("< 15.0.0", "<", "15.0.0"),
        ("<< 15.0.0", "<<", "15.0.0"),
        (">> 15.0.0", ">>", "15.0.0"),
        (">= 15.0.0", ">=", "15.0.0"),
        ("<= 15.0.0", "<=", "15.0.0"),
        ("!= 15.0.0", "!=", "15.0.0"),
        ("<=> 15.0.0", "<=>", "15.0.0"),
        ("<> 15.0.0", "<>", "15.0.0"),
        ("= 15.0.0", "=", "15.0.0"),
        (">15.0.0", ">", "15.0.0"),
        ("<15.0.0", "<", "15.0.0"),
        ("<<15.0.0", "<<", "15.0.0"),
        (">>15.0.0", ">>", "15.0.0"),
        (">=15.0.0", ">=", "15.0.0"),
        ("<=15.0.0", "<=", "15.0.0"),
        ("!=15.0.0", "!=", "15.0.0"),
        ("<=>15.0.0", "<=>", "15.0.0"),
        ("<>15.0.0", "<>", "15.0.0"),
        ("=15.0.0", "=", "15.0.0"),
        ("", "", "")
    ]

    def test_split_comparison(self):
        '''
        Tests salt.utils.pkg.split_comparison
        '''
        for test_parameter in self.test_parameters:
            oper, verstr = salt.utils.pkg.split_comparison(test_parameter[0])
            self.assertEqual(test_parameter[1], oper)
            self.assertEqual(test_parameter[2], verstr)

    def test_rpm_arches(self):
        '''
        Test salt.utils.pkg.rpm supported arch
        '''
        self.assertSequenceEqual(['x86_64', 'athlon', 'amd64', 'ia32e', 'ia64', 'geode'], salt.utils.pkg.rpm.ARCHES_64)
        self.assertSequenceEqual(['i386', 'i486', 'i586', 'i686'], salt.utils.pkg.rpm.ARCHES_32)
        self.assertSequenceEqual(['ppc', 'ppc64', 'ppc64le', 'ppc64iseries', 'ppc64pseries'], salt.utils.pkg.rpm.ARCHES_PPC)
        self.assertSequenceEqual(['s390', 's390x'], salt.utils.pkg.rpm.ARCHES_S390)
        self.assertSequenceEqual(['sparc', 'sparcv8', 'sparcv9', 'sparcv9v', 'sparc64', 'sparc64v'], salt.utils.pkg.rpm.ARCHES_SPARC)
        self.assertSequenceEqual(['alpha', 'alphaev4', 'alphaev45', 'alphaev5', 'alphaev56', 'alphapca56', 'alphaev6', 'alphaev67', 'alphaev68', 'alphaev7'], salt.utils.pkg.rpm.ARCHES_ALPHA)
        self.assertSequenceEqual(['armv5tel', 'armv5tejl', 'armv6l', 'armv7l'], salt.utils.pkg.rpm.ARCHES_ARM)
        self.assertSequenceEqual(['sh3', 'sh4', 'sh4a'], salt.utils.pkg.rpm.ARCHES_SH)
