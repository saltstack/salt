import integration


class LibcloudDNSTest(integration.ModuleCase):
    '''
    Validate the test module
    '''
    def test_list_record_types(self):
        '''
        test.ping
        '''
        # Simple profile (no special kwargs)
        self.assertTrue('SPF' in self.run_function('libcloud_dns.list_record_types', ['profile_test1']))
        
        # Complex profile (special kwargs)
        accepted_record_types = self.run_function('libcloud_dns.list_record_types', ['profile_test2'])
        self.assertTrue(isinstance(accepted_record_types, list) and 'SPF' in accepted_record_types)
