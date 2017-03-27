# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import

# Python

# Salt
from salt._compat import ipaddress
from salt.utils.odict import OrderedDict
from salt.utils.dns import _to_port, _tree, _weighted_order, _data2rec, _data2rec_group

# Testing
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call


# Debug
import pprint
ppr = pprint.PrettyPrinter(indent=2).pprint


class DNShelpersCase(TestCase):

    def test_port(self):
        for right in (1, 42, '123', 65535):
            self.assertEqual(_to_port(right), int(right))

        for wrong in (0, 65536, 100000, 'not-a-port'):
            self.assertRaises(ValueError, _to_port, wrong)

    def test_tree(self):
        test_map = (
            'ex1.nl',
            'o.1.example.eu',
            'a1a.b2b.c3c.example.com'
        )

        res_map = (
            ['ex1.nl'],
            ['o.1.example.eu', '1.example.eu', 'example.eu'],
            ['a1a.b2b.c3c.example.com', 'b2b.c3c.example.com', 'c3c.example.com', 'example.com']
        )

        for domain, result in zip(test_map, res_map):
            self.assertEqual(_tree(domain), result)

    def test_weight(self):
        recs = [
            [],
            [{'weight': 100, 'name': 'nescio'}],
            [
                {'weight': 100, 'name': 'nescio1'},
                {'weight': 100, 'name': 'nescio2'},
                {'weight': 100, 'name': 'nescio3'},
                {'weight': 100, 'name': 'nescio4'},
                {'weight': 100, 'name': 'nescio5'},
                {'weight': 100, 'name': 'nescio6'},
                {'weight': 100, 'name': 'nescio7'},
                {'weight': 100, 'name': 'nescio8'}
            ]
        ]

        # What are the odds of this tripping over a build
        self.assertNotEqual(
            _weighted_order(list(recs[-1])),
            _weighted_order(list(recs[-1]))
        )

        for recset in recs:
            rs_res = _weighted_order(list(recset))
            self.assertTrue(all(rec['name'] in rs_res for rec in recset))

    def test_data2rec(self):
        right = [
            '10.0.0.1',
            '10 mbox.example.com',
            '10 20 30 example.com',
        ]
        schemas = [
            OrderedDict((
                ('address', ipaddress.IPv4Address),
            )),
            OrderedDict((
                ('preference', int),
                ('name', str),
            )),
            OrderedDict((
                ('prio', int),
                ('weight', int),
                ('port', _to_port),
                ('name', str),
            ))
        ]

        results = [
            {'address': ipaddress.IPv4Address(right[0])},
            {'preference': 10, 'name': 'mbox.example.com'},
            {'prio': 10, 'weight': 20, 'port': 30, 'name': 'example.com'}
        ]

        for rdata, rschema, res in zip(right, schemas, results):
            self.assertEqual(_data2rec(rschema, rdata), res)

        wrong = [
            'not-an-ip',
            '10 20 30 toomany.example.com',
            '10 toolittle.example.com',
        ]

        for rdata, rschema in zip(wrong, schemas):
            self.assertRaises(ValueError, _data2rec, rschema, rdata)

    def test_data2group(self):
        right = [
            ['10 mbox.example.com'],
            [
                '10 mbox1.example.com',
                '20 mbox2.example.com',
                '20 mbox3.example.com',
                '30 mbox4.example.com',
                '30 mbox5.example.com',
                '30 mbox6.example.com',
            ],
        ]
        rschema = OrderedDict((
                ('prio', int),
                ('srvr', str),
            ))

        results = [
            OrderedDict([(10, [{'srvr': 'mbox.example.com'}])]),
            OrderedDict([
                (10, [{'srvr': 'mbox1.example.com'}]),
                (20, [{'srvr': 'mbox2.example.com'}, {'srvr': 'mbox3.example.com'}]),
                (30, [{'srvr': 'mbox4.example.com'}, {'srvr': 'mbox5.example.com'}, {'srvr': 'mbox6.example.com'}])]
            ),
        ]

        for rdata, res in zip(right, results):
            group = _data2rec_group(rschema, rdata, 'prio')
            self.assertEqual(group, res)

