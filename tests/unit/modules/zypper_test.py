# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
import os

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


def get_test_data(filename):
    '''
    Return static test data
    '''
    return open(os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zypp'), filename)).read()


# Import Salt Libs
from salt.modules import zypper

# Globals
zypper.__salt__ = {}

@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZypperTestCase(TestCase):
    '''
    Test cases for salt.modules.zypper
    '''

    def test_list_products(self):
        '''
        List products test.
        '''
        ref_out = get_test_data('zypper-products.xml')
        with patch.dict(zypper.__salt__, {'cmd.run': MagicMock(return_value=ref_out)}):
            products = zypper.list_products()
            assert(len(products) == 5)
            assert([u'SLES', u'SLES', u'SUSE-Manager-Proxy',
                    u'SUSE-Manager-Server',
                    u'sle-manager-tools-beta'] == sorted([prod['name'] for prod in products]))
            assert('SUSE LLC <https://www.suse.com/>' in [product['vendor'] for product in products])
            assert([False, False, False, False, True] ==
                   sorted([product['isbase'] for product in products]))
            assert([False, False, False, False, True] ==
                   sorted([product['installed'] for product in products]))
            assert([u'0', u'0', u'0', u'0', u'0'] ==
                   sorted([product['release'] for product in products]))
            assert([False, False, False, False, u'sles'] ==
                   sorted([product['productline'] for product in products]))
            assert([1509408000, 1522454400, 1522454400, 1730332800, 1730332800] ==
                   sorted([product['eol_t'] for product in products]))



    def test_refresh_db(self):
        '''
        Test if refresh DB handled correctly
        '''
        ref_out = [
            "Repository 'openSUSE-Leap-42.1-LATEST' is up to date.",
            "Repository 'openSUSE-Leap-42.1-Update' is up to date.",
            "Retrieving repository 'openSUSE-Leap-42.1-Update-Non-Oss' metadata",
            "Forcing building of repository cache",
            "Building repository 'openSUSE-Leap-42.1-Update-Non-Oss' cache ..........[done]",
            "Building repository 'salt-dev' cache",
            "All repositories have been refreshed."
        ]

        run_out = {
            'stderr': '', 'stdout': '\n'.join(ref_out), 'retcode': 0
        }

        with patch.dict(zypper.__salt__, {'cmd.run_all': MagicMock(return_value=run_out)}):
            result = zypper.refresh_db()
            self.assertEqual(result.get("openSUSE-Leap-42.1-LATEST"), False)
            self.assertEqual(result.get("openSUSE-Leap-42.1-Update"), False)
            self.assertEqual(result.get("openSUSE-Leap-42.1-Update-Non-Oss"), True)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ZypperTestCase, needs_daemon=False)
