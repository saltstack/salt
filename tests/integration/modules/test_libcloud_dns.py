# -*- coding: utf-8 -*-
from __future__ import absolute_import

# import salt libs
from salt.utils.versions import LooseVersion as _LooseVersion

# Import test Helpers
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

REQUIRED_LIBCLOUD_VERSION = '0.21.0'
try:
    import libcloud
    #pylint: enable=unused-import
    if _LooseVersion(getattr(libcloud, '__version__', '0.0.0')) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


@skipIf(not HAS_LIBCLOUD, 'Requires libcloud >= {0}'.format(REQUIRED_LIBCLOUD_VERSION))
class LibcloudDNSTest(ModuleCase):
    '''
    Validate the libcloud_dns module
    '''
    def test_list_record_types(self):
        '''
        libcloud_dns.list_record_types
        '''
        # Simple profile (no special kwargs)
        self.assertTrue('SPF' in self.run_function('libcloud_dns.list_record_types', ['profile_test1']))

        # Complex profile (special kwargs)
        accepted_record_types = self.run_function('libcloud_dns.list_record_types', ['profile_test2'])

        self.assertTrue(isinstance(accepted_record_types, list) and 'SRV' in accepted_record_types)
