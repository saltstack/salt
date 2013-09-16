# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.payload_test
    ~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath, MockWraps
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch
ensure_in_syspath('../')

# Import salt libs
import salt.payload
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
import msgpack


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PayloadTestCase(TestCase):

    def assertNoOrderedDict(self, data):
        if isinstance(data, OrderedDict):
            raise AssertionError(
                'Found an ordered dictionary'
            )
        if isinstance(data, dict):
            for value in data.values():
                self.assertNoOrderedDict(value)
        elif isinstance(data, (list, tuple)):
            for chunk in data:
                self.assertNoOrderedDict(chunk)

    def test_list_nested_odicts(self):
        with patch('msgpack.version', (0, 1, 13)):
            msgpack.dumps = MockWraps(
                msgpack.dumps, 1, TypeError('ODict TypeError Forced')
            )
            payload = salt.payload.Serial('msgpack')
            idata = {'pillar': [OrderedDict(environment='dev')]}
            odata = payload.loads(payload.dumps(idata.copy()))
            self.assertNoOrderedDict(odata)
            self.assertEqual(idata, odata)
