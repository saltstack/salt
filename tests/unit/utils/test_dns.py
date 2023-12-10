import logging
import socket
import textwrap

import pytest

import salt.modules.cmdmod
import salt.utils.dns
from salt._compat import ipaddress
from salt.utils.dns import (
    _data2rec,
    _data2rec_group,
    _lookup_dig,
    _lookup_drill,
    _lookup_gai,
    _lookup_host,
    _lookup_nslookup,
    _to_port,
    _tree,
    _weighted_order,
    lookup,
)
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class DNShelpersCase(TestCase):
    """
    Tests for the parser helpers
    """

    def test_port(self):
        for right in (1, 42, "123", 65535):
            self.assertEqual(_to_port(right), int(right))

        for wrong in (0, 65536, 100000, "not-a-port"):
            self.assertRaises(ValueError, _to_port, wrong)

    def test_tree(self):
        test_map = (
            "ex1.nl",
            "o.1.example.eu",
            "a1a.b2b.c3c.example.com",
            "c3c.example.co.uk",
            "c3c.example.mil.ng",
        )

        res_map = (
            ["ex1.nl"],
            ["o.1.example.eu", "1.example.eu", "example.eu"],
            [
                "a1a.b2b.c3c.example.com",
                "b2b.c3c.example.com",
                "c3c.example.com",
                "example.com",
            ],
            ["c3c.example.co.uk", "example.co.uk"],
            ["c3c.example.mil.ng", "example.mil.ng"],
        )

        for domain, result in zip(test_map, res_map):
            self.assertEqual(_tree(domain), result)

    def test_weight(self):
        recs = [
            [],
            [{"weight": 100, "name": "nescio"}],
            [
                {"weight": 100, "name": "nescio1"},
                {"weight": 100, "name": "nescio2"},
                {"weight": 100, "name": "nescio3"},
                {"weight": 100, "name": "nescio4"},
                {"weight": 100, "name": "nescio5"},
                {"weight": 100, "name": "nescio6"},
                {"weight": 100, "name": "nescio7"},
                {"weight": 100, "name": "nescio8"},
            ],
        ]

        # What are the odds of this tripping over a build
        # 1/(8!^4) builds?
        self.assertNotEqual(
            _weighted_order(list(recs[-1])),
            _weighted_order(list(recs[-1])),
            _weighted_order(list(recs[-1])),
        )

        for recset in recs:
            rs_res = _weighted_order(list(recset))
            self.assertTrue(all(rec["name"] in rs_res for rec in recset))

    def test_data2rec(self):
        right = [
            "10.0.0.1",
            "10 mbox.example.com",
            "10 20 30 example.com",
        ]
        schemas = [
            OrderedDict((("address", ipaddress.IPv4Address),)),
            OrderedDict(
                (
                    ("preference", int),
                    ("name", str),
                )
            ),
            OrderedDict(
                (
                    ("prio", int),
                    ("weight", int),
                    ("port", _to_port),
                    ("name", str),
                )
            ),
        ]

        results = [
            ipaddress.IPv4Address(right[0]),
            {"preference": 10, "name": "mbox.example.com"},
            {"prio": 10, "weight": 20, "port": 30, "name": "example.com"},
        ]

        for rdata, rschema, res in zip(right, schemas, results):
            self.assertEqual(_data2rec(rschema, rdata), res)

        wrong = [
            "not-an-ip",
            "hundred 20 30 interror.example.com",
            "10 toolittle.example.com",
        ]

        for rdata, rschema in zip(wrong, schemas):
            self.assertRaises(ValueError, _data2rec, rschema, rdata)

    def test_data2group(self):
        right = [
            ["10 mbox.example.com"],
            [
                "10 mbox1.example.com",
                "20 mbox2.example.com",
                "20 mbox3.example.com",
                "30 mbox4.example.com",
                "30 mbox5.example.com",
                "30 mbox6.example.com",
            ],
        ]
        rschema = OrderedDict(
            (
                ("prio", int),
                ("srvr", str),
            )
        )

        results = [
            OrderedDict([(10, ["mbox.example.com"])]),
            OrderedDict(
                [
                    (10, ["mbox1.example.com"]),
                    (20, ["mbox2.example.com", "mbox3.example.com"]),
                    (
                        30,
                        ["mbox4.example.com", "mbox5.example.com", "mbox6.example.com"],
                    ),
                ]
            ),
        ]

        for rdata, res in zip(right, results):
            group = _data2rec_group(rschema, rdata, "prio")
            self.assertEqual(group, res)


class DNSlookupsCase(TestCase):
    """
    Test the lookup result parsers

    Note that by far and large the parsers actually
    completely ignore the input name or output content
    only nslookup is bad enough to be an exception to that

    a lookup function
    - raises ValueError when an incorrect DNS type is given
    - returns False upon error
    - returns [*record-data] upon succes/no records

    """

    CMD_RET = {"pid": 12345, "retcode": 0, "stderr": "", "stdout": ""}

    RESULTS = {
        "A": [
            ["10.1.1.1"],  # one-match
            ["10.1.1.1", "10.2.2.2", "10.3.3.3"],  # multi-match
        ],
        "AAAA": [
            ["2a00:a00:b01:c02:d03:e04:f05:111"],  # one-match
            [
                "2a00:a00:b01:c02:d03:e04:f05:111",
                "2a00:a00:b01:c02:d03:e04:f05:222",
                "2a00:a00:b01:c02:d03:e04:f05:333",
            ],  # multi-match
        ],
        "CAA": [['0 issue "exampleca.com"', '0 iodef "mailto:sslabuse@example.com"']],
        "CNAME": [["web.example.com."]],
        "MX": [
            ["10 mx1.example.com."],
            ["10 mx1.example.com.", "20 mx2.example.eu.", "30 mx3.example.nl."],
        ],
        "SSHFP": [
            [
                "1 1 0aabda8af5418108e8a5d3f90f207226b2c89fbe",
                "1 2 500ca871d8e255e01f1261a2370c4e5406b8712f19916d3ab9f86344a67e5597",
                "3 1 a3b605ce6f044617c6077c46a7cd5d17a767f0d5",
                "4 2 0360d0a5a2fa550f972259e7374533add7ac8e5f303322a5b8e208bbc859ab1b",
            ]
        ],
        "TXT": [
            [
                "v=spf1 a include:_spf4.example.com include:mail.example.eu"
                " ip4:10.0.0.0/8 ip6:2a00:a00:b01::/48 ~all"
            ]
        ],
    }

    def _mock_cmd_ret(self, delta_res):
        """
        Take CMD_RET and update it w/(a list of ) delta_res
        Mock cmd.run_all w/it
        :param delta_res: list or dict
        :return: patched cmd.run_all
        """
        if isinstance(delta_res, (list, tuple)):
            test_res = []
            for dres in delta_res:
                tres = self.CMD_RET.copy()
                tres.update(dres)
                test_res.append(tres)

            cmd_mock = MagicMock(side_effect=test_res)
        else:
            test_res = self.CMD_RET.copy()
            test_res.update(delta_res)
            cmd_mock = MagicMock(return_value=test_res)
        return patch.dict(
            salt.utils.dns.__salt__, {"cmd.run_all": cmd_mock}, clear=True
        )

    def _test_cmd_lookup(
        self, lookup_cb, wrong_type, wrong, right, empty=None, secure=None
    ):
        """
        Perform a given battery of tests against a given lookup utilizing cmd.run_all
        :param wrong_type: delta cmd.run_all output for an incorrect DNS type
        :param wrong: delta cmd.run_all output for any error
        :param right: delta cmd.run_all output for outputs in RESULTS
        :param empty: delta cmd.run_all output for anything that won't return matches
        :param secure: delta cmd.run_all output for secured RESULTS
        """
        # wrong
        for wrong in wrong:
            with self._mock_cmd_ret(wrong):
                self.assertEqual(lookup_cb("mockq", "A"), False)

        # empty response
        if empty is None:
            empty = {}
        with self._mock_cmd_ret(empty):
            self.assertEqual(lookup_cb("mockq", "AAAA"), [])

        # wrong types
        with self._mock_cmd_ret(wrong_type):
            self.assertRaises(ValueError, lookup_cb, "mockq", "WRONG")

        # Regular outputs
        for rec_t, tests in right.items():
            with self._mock_cmd_ret([dict([("stdout", dres)]) for dres in tests]):
                for test_res in self.RESULTS[rec_t]:
                    if rec_t in ("A", "AAAA", "CNAME", "SSHFP"):
                        rec = "mocksrvr.example.com"
                    else:
                        rec = "example.com"

                    lookup_res = lookup_cb(rec, rec_t)
                    if rec_t == "SSHFP":
                        # Some resolvers 'split' the output and/or capitalize differently.
                        # So we need to workaround that here as well
                        lookup_res = [
                            res[:4] + res[4:].replace(" ", "").lower()
                            for res in lookup_res
                        ]

                    self.assertEqual(
                        lookup_res,
                        test_res,
                        # msg='Error parsing {0} returns'.format(rec_t)
                    )

        if not secure:
            return

        # Regular outputs are insecure outputs (e.g. False)
        for rec_t, tests in right.items():
            with self._mock_cmd_ret([dict([("stdout", dres)]) for dres in tests]):
                for _ in self.RESULTS[rec_t]:
                    self.assertEqual(
                        lookup_cb("mocksrvr.example.com", rec_t, secure=True),
                        False,
                        msg="Insecure {} returns should not be returned".format(rec_t),
                    )

        for rec_t, tests in secure.items():
            with self._mock_cmd_ret([dict([("stdout", dres)]) for dres in tests]):
                for test_res in self.RESULTS[rec_t]:
                    self.assertEqual(
                        lookup_cb("mocksrvr.example.com", rec_t, secure=True),
                        test_res,
                        msg="Error parsing DNSSEC'd {} returns".format(rec_t),
                    )

    @pytest.mark.skipif(
        not salt.utils.dns.HAS_NSLOOKUP, reason="nslookup is not available"
    )
    @pytest.mark.requires_network
    def test_lookup_with_servers(self):
        rights = {
            "A": [
                "Name:\tmocksrvr.example.com\nAddress: 10.1.1.1",
                "Name:\tmocksrvr.example.com\nAddress: 10.1.1.1\n"
                "Name:\tweb.example.com\nAddress: 10.2.2.2\n"
                "Name:\tweb.example.com\nAddress: 10.3.3.3",
            ],
            "AAAA": [
                "mocksrvr.example.com\thas AAAA address"
                " 2a00:a00:b01:c02:d03:e04:f05:111",
                "mocksrvr.example.com\tcanonical name = web.example.com.\n"
                "web.example.com\thas AAAA address 2a00:a00:b01:c02:d03:e04:f05:111\n"
                "web.example.com\thas AAAA address 2a00:a00:b01:c02:d03:e04:f05:222\n"
                "web.example.com\thas AAAA address 2a00:a00:b01:c02:d03:e04:f05:333",
            ],
            "CNAME": ["mocksrvr.example.com\tcanonical name = web.example.com."],
            "MX": [
                "example.com\tmail exchanger = 10 mx1.example.com.",
                "example.com\tmail exchanger = 10 mx1.example.com.\n"
                "example.com\tmail exchanger = 20 mx2.example.eu.\n"
                "example.com\tmail exchanger = 30 mx3.example.nl.",
            ],
            "TXT": [
                'example.com\ttext = "v=spf1 a include:_spf4.example.com'
                ' include:mail.example.eu ip4:10.0.0.0/8 ip6:2a00:a00:b01::/48 ~all"'
            ],
        }

        for rec_t, tests in rights.items():
            with self._mock_cmd_ret([dict([("stdout", dres)]) for dres in tests]):
                for test_res in self.RESULTS[rec_t]:
                    if rec_t in ("A", "AAAA", "CNAME"):
                        rec = "mocksrvr.example.com"
                    else:
                        rec = "example.com"
                    self.assertEqual(
                        lookup(rec, rec_t, method="nslookup", servers="8.8.8.8"),
                        test_res,
                    )

    @pytest.mark.skipif(not salt.utils.dns.HAS_DIG, reason="dig is not available")
    def test_dig_options(self):
        cmd = "dig {} -v".format(salt.utils.dns.DIG_OPTIONS)
        cmd = salt.modules.cmdmod.retcode(
            cmd, python_shell=False, output_loglevel="quiet"
        )
        self.assertEqual(cmd, 0)

    def test_dig(self):
        wrong_type = {"retcode": 0, "stderr": ";; Warning, ignoring invalid type ABC"}

        wrongs = [
            {
                "retcode": 9,
                "stderr": ";; connection timed out; no servers could be reached",
            },
        ]

        # example returns for dig +search +fail +noall +answer +noclass +nosplit +nottl -t {rtype} {name}
        rights = {
            "A": [
                "mocksrvr.example.com.\tA\t10.1.1.1",
                "web.example.com.\t\tA\t10.1.1.1\n"
                "web.example.com.\t\tA\t10.2.2.2\n"
                "web.example.com.\t\tA\t10.3.3.3",
            ],
            "AAAA": [
                "mocksrvr.example.com.\tA\t2a00:a00:b01:c02:d03:e04:f05:111",
                "mocksrvr.example.com.\tCNAME\tweb.example.com.\n"
                "web.example.com.\t\tAAAA\t2a00:a00:b01:c02:d03:e04:f05:111\n"
                "web.example.com.\t\tAAAA\t2a00:a00:b01:c02:d03:e04:f05:222\n"
                "web.example.com.\t\tAAAA\t2a00:a00:b01:c02:d03:e04:f05:333",
            ],
            "CAA": [
                'example.com.\t\tCAA\t0 issue "exampleca.com"\n'
                'example.com.\t\tCAA\t0 iodef "mailto:sslabuse@example.com"'
            ],
            "CNAME": ["mocksrvr.example.com.\tCNAME\tweb.example.com."],
            "MX": [
                "example.com.\t\tMX\t10 mx1.example.com.",
                "example.com.\t\tMX\t10 mx1.example.com.\nexample.com.\t\tMX\t20"
                " mx2.example.eu.\nexample.com.\t\tMX\t30 mx3.example.nl.",
            ],
            "SSHFP": [
                "mocksrvr.example.com.\tSSHFP\t1 1"
                " 0AABDA8AF5418108E8A5D3F90F207226B2C89FBE\nmocksrvr.example.com.\tSSHFP\t1"
                " 2 500CA871D8E255E01F1261A2370C4E5406B8712F19916D3AB9F86344A67E5597\nmocksrvr.example.com.\tSSHFP\t3"
                " 1 A3B605CE6F044617C6077C46A7CD5D17A767F0D5\nmocksrvr.example.com.\tSSHFP\t4"
                " 2 0360D0A5A2FA550F972259E7374533ADD7AC8E5F303322A5B8E208BBC859AB1B"
            ],
            "TXT": [
                'example.com.\tTXT\t"v=spf1 a include:_spf4.example.com'
                ' include:mail.example.eu ip4:10.0.0.0/8 ip6:2a00:a00:b01::/48 ~all"'
            ],
        }

        secure = {
            "A": [
                "mocksrvr.example.com.\tA\t10.1.1.1\nmocksrvr.example.com.\tRRSIG\tA 8"
                " 3 7200 20170420000000 20170330000000 1629 example.com."
                " Hv4p37EF55LKBxUNYpnhWiEYqfmMct0z0WgDJyG5reqYfl+z4HX/kaoi"
                " Wr2iCYuYeB4Le7BgnMSb77UGHPWE7lCQ8z5gkgJ9rCDrooJzSTVdnHfw"
                " 1JQ7txRSp8Rj2GLf/L3Ytuo6nNZTV7bWUkfhOs61DAcOPHYZiX8rVhIh UAE=",
                "web.example.com.\t\tA\t10.1.1.1\nweb.example.com.\t\tA\t10.2.2.2\nweb.example.com.\t\tA\t10.3.3.3\nweb.example.com.\tRRSIG\tA"
                " 8 3 7200 20170420000000 20170330000000 1629 example.com."
                " Hv4p37EF55LKBxUNYpnhWiEYqfmMct0z0WgDJyG5reqYfl+z4HX/kaoi"
                " Wr2iCYuYeB4Le7BgnMSb77UGHPWE7lCQ8z5gkgJ9rCDrooJzSTVdnHfw"
                " 1JQ7txRSp8Rj2GLf/L3Ytuo6nNZTV7bWUkfhOs61DAcOPHYZiX8rVhIh UAE=",
            ]
        }

        self._test_cmd_lookup(
            _lookup_dig,
            wrong=wrongs,
            right=rights,
            wrong_type=wrong_type,
            secure=secure,
        )

    def test_drill(self):
        # all Drill returns look like this
        RES_TMPL = textwrap.dedent(
            """\
            ;; ->>HEADER<<- opcode: QUERY, rcode: NOERROR, id: 58233
            ;; flags: qr rd ra ; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0
            ;; QUESTION SECTION:
            ;; mocksrvr.example.com.\tIN\tA

            ;; ANSWER SECTION:
            {}

            ;; AUTHORITY SECTION:

            ;; ADDITIONAL SECTION:

            ;; Query time: 37 msec
            ;; SERVER: 10.100.150.129
            ;; WHEN: Tue Apr  4 19:03:51 2017
            ;; MSG SIZE  rcvd: 50
        """
        )

        # Not even a different retcode!?
        wrong_type = {
            "stdout": RES_TMPL.format("mocksrvr.example.com.\t4404\tIN\tA\t10.1.1.1\n")
        }

        wrongs = [
            {
                "retcode": 1,
                "stderr": (
                    "Error: error sending query: No (valid) nameservers defined in the"
                    " resolver"
                ),
            }
        ]

        # example returns for drill {rtype} {name}
        rights = {
            "A": [
                "mocksrvr.example.com.\t4404\tIN\tA\t10.1.1.1\n",
                "web.example.com.\t4404\tIN\tA\t10.1.1.1\n"
                "web.example.com.\t4404\tIN\tA\t10.2.2.2\n"
                "web.example.com.\t4404\tIN\tA\t10.3.3.3",
            ],
            "AAAA": [
                "mocksrvr.example.com.\t4404\tIN\tAAAA\t2a00:a00:b01:c02:d03:e04:f05:111",
                "mocksrvr.example.com.\t4404\tIN\tCNAME\tweb.example.com.\n"
                "web.example.com.\t4404\tIN\tAAAA\t2a00:a00:b01:c02:d03:e04:f05:111\n"
                "web.example.com.\t4404\tIN\tAAAA\t2a00:a00:b01:c02:d03:e04:f05:222\n"
                "web.example.com.\t4404\tIN\tAAAA\t2a00:a00:b01:c02:d03:e04:f05:333",
            ],
            "CAA": [
                'example.com.\t1144\tIN\tCAA\t0 issue "exampleca.com"\n'
                'example.com.\t1144\tIN\tCAA\t0 iodef "mailto:sslabuse@example.com"'
            ],
            "CNAME": ["mocksrvr.example.com.\t4404\tIN\tCNAME\tweb.example.com."],
            "MX": [
                "example.com.\t4404\tIN\tMX\t10 mx1.example.com.",
                "example.com.\t4404\tIN\tMX\t10 mx1.example.com.\n"
                "example.com.\t4404\tIN\tMX\t20 mx2.example.eu.\n"
                "example.com.\t4404\tIN\tMX\t30 mx3.example.nl.",
            ],
            "SSHFP": [
                "mocksrvr.example.com.\t3339\tIN\tSSHFP\t1 1"
                " 0aabda8af5418108e8a5d3f90f207226b2c89fbe\nmocksrvr.example.com.\t3339\tIN\tSSHFP\t1"
                " 2 500ca871d8e255e01f1261a2370c4e5406b8712f19916d3ab9f86344a67e5597\nmocksrvr.example.com.\t3339\tIN\tSSHFP\t3"
                " 1 a3b605ce6f044617c6077c46a7cd5d17a767f0d5\nmocksrvr.example.com.\t3339\tIN\tSSHFP\t4"
                " 2 0360d0a5a2fa550f972259e7374533add7ac8e5f303322a5b8e208bbc859ab1b"
            ],
            "TXT": [
                'example.com.\t4404\tIN\tTXT\t"v=spf1 a include:_spf4.example.com'
                ' include:mail.example.eu ip4:10.0.0.0/8 ip6:2a00:a00:b01::/48 ~all"'
            ],
        }

        secure = {
            "A": [
                "mocksrvr.example.com.\t4404\tIN\tA\t10.1.1.1\nmocksrvr.example.com.\t4404\tIN\tRRSIG\tA"
                " 8 3 7200 20170420000000 20170330000000 1629 example.com."
                " Hv4p37EF55LKBxUNYpnhWiEYqfmMct0z0WgDJyG5reqYfl+z4HX/kaoi"
                " Wr2iCYuYeB4Le7BgnMSb77UGHPWE7lCQ8z5gkgJ9rCDrooJzSTVdnHfw"
                " 1JQ7txRSp8Rj2GLf/L3Ytuo6nNZTV7bWUkfhOs61DAcOPHYZiX8rVhIh UAE=",
                "web.example.com.\t4404\tIN\tA\t10.1.1.1\nweb.example.com.\t4404\tIN\tA\t10.2.2.2\nweb.example.com.\t4404\tIN\tA\t10.3.3.3\nweb.example.com.\t4404\tIN\tRRSIG\tA"
                " 8 3 7200 20170420000000 20170330000000 1629 example.com."
                " Hv4p37EF55LKBxUNYpnhWiEYqfmMct0z0WgDJyG5reqYfl+z4HX/kaoi"
                " Wr2iCYuYeB4Le7BgnMSb77UGHPWE7lCQ8z5gkgJ9rCDrooJzSTVdnHfw"
                " 1JQ7txRSp8Rj2GLf/L3Ytuo6nNZTV7bWUkfhOs61DAcOPHYZiX8rVhIh UAE=",
            ]
        }

        for rec_d in rights, secure:
            for rec_t, tests in rec_d.items():
                for idx, test in enumerate(tests):
                    rec_d[rec_t][idx] = RES_TMPL.format(test)

        self._test_cmd_lookup(
            _lookup_drill,
            wrong_type=wrong_type,
            wrong=wrongs,
            right=rights,
            secure=secure,
        )

    def test_gai(self):
        # wrong type
        self.assertRaises(ValueError, _lookup_gai, "mockq", "WRONG")

        # wrong
        with patch.object(
            socket, "getaddrinfo", MagicMock(side_effect=socket.gaierror)
        ):
            for rec_t in ("A", "AAAA"):
                self.assertEqual(False, _lookup_gai("mockq", rec_t))

        # example returns from getaddrinfo
        right = {
            "A": [
                [(2, 3, 3, "", ("10.1.1.1", 0))],
                [
                    (2, 3, 3, "", ("10.1.1.1", 0)),
                    (2, 3, 3, "", ("10.2.2.2", 0)),
                    (2, 3, 3, "", ("10.3.3.3", 0)),
                ],
            ],
            "AAAA": [
                [(10, 3, 3, "", ("2a00:a00:b01:c02:d03:e04:f05:111", 0, 0, 0))],
                [
                    (10, 3, 3, "", ("2a00:a00:b01:c02:d03:e04:f05:111", 0, 0, 0)),
                    (10, 3, 3, "", ("2a00:a00:b01:c02:d03:e04:f05:222", 0, 0, 0)),
                    (10, 3, 3, "", ("2a00:a00:b01:c02:d03:e04:f05:333", 0, 0, 0)),
                ],
            ],
        }

        for rec_t, tests in right.items():
            with patch.object(socket, "getaddrinfo", MagicMock(side_effect=tests)):
                for test_res in self.RESULTS[rec_t]:
                    self.assertEqual(
                        _lookup_gai("mockq", rec_t),
                        test_res,
                        msg="Error parsing {} returns".format(rec_t),
                    )

    def test_host(self):
        wrong_type = {"retcode": 9, "stderr": "host: invalid type: WRONG"}

        wrongs = [
            {
                "retcode": 9,
                "stderr": ";; connection timed out; no servers could be reached",
            }
        ]

        empty = {"stdout": "www.example.com has no MX record"}

        # example returns for host -t {rdtype} {name}
        rights = {
            "A": [
                "mocksrvr.example.com has address 10.1.1.1",
                "web.example.com has address 10.1.1.1\n"
                "web.example.com has address 10.2.2.2\n"
                "web.example.com has address 10.3.3.3",
            ],
            "AAAA": [
                "mocksrvr.example.com has IPv6 address"
                " 2a00:a00:b01:c02:d03:e04:f05:111",
                "mocksrvr.example.com is an alias for web.example.com.\n"
                "web.example.com has IPv6 address 2a00:a00:b01:c02:d03:e04:f05:111\n"
                "web.example.com has IPv6 address 2a00:a00:b01:c02:d03:e04:f05:222\n"
                "web.example.com has IPv6 address 2a00:a00:b01:c02:d03:e04:f05:333",
            ],
            "CAA": [
                'example.com has CAA record 0 issue "exampleca.com"\n'
                'example.com has CAA record 0 iodef "mailto:sslabuse@example.com"'
            ],
            "CNAME": ["mocksrvr.example.com is an alias for web.example.com."],
            "MX": [
                "example.com mail is handled by 10 mx1.example.com.",
                "example.com mail is handled by 10 mx1.example.com.\n"
                "example.com mail is handled by 20 mx2.example.eu.\n"
                "example.com mail is handled by 30 mx3.example.nl.",
            ],
            "SSHFP": [
                "mocksrvr.example.com has SSHFP record 1 1"
                " 0AABDA8AF5418108E8A5D3F90F207226B2C89FBE\nmocksrvr.example.com has"
                " SSHFP record 1 2"
                " 500CA871D8E255E01F1261A2370C4E5406B8712F19916D3AB9F86344"
                " A67E5597\nmocksrvr.example.com has SSHFP record 3 1"
                " A3B605CE6F044617C6077C46A7CD5D17A767F0D5\nmocksrvr.example.com has"
                " SSHFP record 4 2"
                " 0360D0A5A2FA550F972259E7374533ADD7AC8E5F303322A5B8E208BB C859AB1B"
            ],
            "TXT": [
                'example.com descriptive text "v=spf1 a include:_spf4.example.com'
                ' include:mail.example.eu ip4:10.0.0.0/8 ip6:2a00:a00:b01::/48 ~all"'
            ],
        }

        self._test_cmd_lookup(
            _lookup_host, wrong_type=wrong_type, wrong=wrongs, right=rights, empty=empty
        )

    def test_nslookup(self):
        # all nslookup returns look like this
        RES_TMPL = textwrap.dedent(
            """\
            Server:\t\t10.11.12.13
            Address:\t10.11.12.13#53

            Non-authoritative answer:
            {}

            Authoritative answers can be found from:
        """
        )

        wrong_type = {
            "stdout": "unknown query type: WRONG"
            + RES_TMPL.format("Name:\tmocksrvr.example.com\nAddress: 10.1.1.1")
        }

        wrongs = [
            {
                "retcode": 1,
                "stdout": ";; connection timed out; no servers could be reached",
            }
        ]

        empty = {"stdout": RES_TMPL.format("*** Can't find www.google.com: No answer")}

        # Example returns of nslookup -query={rdype} {name}
        rights = {
            "A": [
                "Name:\tmocksrvr.example.com\nAddress: 10.1.1.1",
                "Name:\tmocksrvr.example.com\nAddress: 10.1.1.1\n"
                "Name:\tweb.example.com\nAddress: 10.2.2.2\n"
                "Name:\tweb.example.com\nAddress: 10.3.3.3",
            ],
            "AAAA": [
                "mocksrvr.example.com\thas AAAA address"
                " 2a00:a00:b01:c02:d03:e04:f05:111",
                "mocksrvr.example.com\tcanonical name = web.example.com.\n"
                "web.example.com\thas AAAA address 2a00:a00:b01:c02:d03:e04:f05:111\n"
                "web.example.com\thas AAAA address 2a00:a00:b01:c02:d03:e04:f05:222\n"
                "web.example.com\thas AAAA address 2a00:a00:b01:c02:d03:e04:f05:333",
            ],
            "CAA": [
                'example.com\trdata_257 = 0 issue "exampleca.com"\n'
                'example.com\trdata_257 = 0 iodef "mailto:sslabuse@example.com"'
            ],
            "CNAME": ["mocksrvr.example.com\tcanonical name = web.example.com."],
            "MX": [
                "example.com\tmail exchanger = 10 mx1.example.com.",
                "example.com\tmail exchanger = 10 mx1.example.com.\n"
                "example.com\tmail exchanger = 20 mx2.example.eu.\n"
                "example.com\tmail exchanger = 30 mx3.example.nl.",
            ],
            "SSHFP": [
                "mocksrvr.example.com\trdata_44 = 1 1"
                " 0AABDA8AF5418108E8A5D3F90F207226B2C89FBE\nmocksrvr.example.com\trdata_44"
                " = 1 2 500CA871D8E255E01F1261A2370C4E5406B8712F19916D3AB9F86344"
                " A67E5597\nmocksrvr.example.com\trdata_44 = 3 1"
                " A3B605CE6F044617C6077C46A7CD5D17A767F0D5\nmocksrvr.example.com\trdata_44"
                " = 4 2 0360D0A5A2FA550F972259E7374533ADD7AC8E5F303322A5B8E208BB"
                " C859AB1B"
            ],
            "TXT": [
                'example.com\ttext = "v=spf1 a include:_spf4.example.com'
                ' include:mail.example.eu ip4:10.0.0.0/8 ip6:2a00:a00:b01::/48 ~all"'
            ],
        }

        for rec_t, tests in rights.items():
            for idx, test in enumerate(tests):
                rights[rec_t][idx] = RES_TMPL.format(test)

        self._test_cmd_lookup(
            _lookup_nslookup,
            wrong_type=wrong_type,
            wrong=wrongs,
            right=rights,
            empty=empty,
        )
