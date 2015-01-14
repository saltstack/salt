# -*- coding: utf-8 -*-
'''
Validate the boto_iam module
'''


from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

import integration


class BotoIAMTest(integration.ModuleCase):

    def test_get_account_id(self):
        ret = self.run_function('boto_iam.get_account_id')
        self.assertRegexpMatches(ret, r'^\d{12}$')