# -*- coding: utf-8 -*-
from __future__ import absolute_import

import tests.integration as integration


class LibcloudDNSTest(integration.ModuleCase):
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
