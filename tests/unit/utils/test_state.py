"""
Unit Tests for functions located in salt.utils.state.py.
"""


import copy
import textwrap

import salt.utils.odict
import salt.utils.state
from tests.support.unit import TestCase


class StateUtilTestCase(TestCase):
    """
    Test case for state util.
    """

    def test_check_result(self):
        self.assertFalse(
            salt.utils.state.check_result(None),
            "Failed to handle None as an invalid data type.",
        )
        self.assertFalse(
            salt.utils.state.check_result([]), "Failed to handle an invalid data type."
        )
        self.assertFalse(
            salt.utils.state.check_result({}), "Failed to handle an empty dictionary."
        )
        self.assertFalse(
            salt.utils.state.check_result({"host1": []}),
            "Failed to handle an invalid host data structure.",
        )
        test_valid_state = {"host1": {"test_state": {"result": "We have liftoff!"}}}
        self.assertTrue(salt.utils.state.check_result(test_valid_state))
        test_valid_false_states = {
            "test1": salt.utils.odict.OrderedDict(
                [
                    (
                        "host1",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": True}),
                                ("test_state", {"result": False}),
                            ]
                        ),
                    ),
                ]
            ),
            "test2": salt.utils.odict.OrderedDict(
                [
                    (
                        "host1",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": True}),
                                ("test_state", {"result": True}),
                            ]
                        ),
                    ),
                    (
                        "host2",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": True}),
                                ("test_state", {"result": False}),
                            ]
                        ),
                    ),
                ]
            ),
            "test3": ["a"],
            "test4": salt.utils.odict.OrderedDict(
                [
                    (
                        "asup",
                        salt.utils.odict.OrderedDict(
                            [
                                (
                                    "host1",
                                    salt.utils.odict.OrderedDict(
                                        [
                                            ("test_state0", {"result": True}),
                                            ("test_state", {"result": True}),
                                        ]
                                    ),
                                ),
                                (
                                    "host2",
                                    salt.utils.odict.OrderedDict(
                                        [
                                            ("test_state0", {"result": True}),
                                            ("test_state", {"result": False}),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    )
                ]
            ),
            "test5": salt.utils.odict.OrderedDict(
                [
                    (
                        "asup",
                        salt.utils.odict.OrderedDict(
                            [
                                (
                                    "host1",
                                    salt.utils.odict.OrderedDict(
                                        [
                                            ("test_state0", {"result": True}),
                                            ("test_state", {"result": True}),
                                        ]
                                    ),
                                ),
                                ("host2", salt.utils.odict.OrderedDict([])),
                            ]
                        ),
                    )
                ]
            ),
        }
        for test, data in test_valid_false_states.items():
            self.assertFalse(
                salt.utils.state.check_result(data), msg="{} failed".format(test)
            )
        test_valid_true_states = {
            "test1": salt.utils.odict.OrderedDict(
                [
                    (
                        "host1",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": True}),
                                ("test_state", {"result": True}),
                            ]
                        ),
                    ),
                ]
            ),
            "test3": salt.utils.odict.OrderedDict(
                [
                    (
                        "host1",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": True}),
                                ("test_state", {"result": True}),
                            ]
                        ),
                    ),
                    (
                        "host2",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": True}),
                                ("test_state", {"result": True}),
                            ]
                        ),
                    ),
                ]
            ),
            "test4": salt.utils.odict.OrderedDict(
                [
                    (
                        "asup",
                        salt.utils.odict.OrderedDict(
                            [
                                (
                                    "host1",
                                    salt.utils.odict.OrderedDict(
                                        [
                                            ("test_state0", {"result": True}),
                                            ("test_state", {"result": True}),
                                        ]
                                    ),
                                ),
                                (
                                    "host2",
                                    salt.utils.odict.OrderedDict(
                                        [
                                            ("test_state0", {"result": True}),
                                            ("test_state", {"result": True}),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    )
                ]
            ),
            "test2": salt.utils.odict.OrderedDict(
                [
                    (
                        "host1",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": None}),
                                ("test_state", {"result": True}),
                            ]
                        ),
                    ),
                    (
                        "host2",
                        salt.utils.odict.OrderedDict(
                            [
                                ("test_state0", {"result": True}),
                                ("test_state", {"result": "abc"}),
                            ]
                        ),
                    ),
                ]
            ),
        }
        for test, data in test_valid_true_states.items():
            self.assertTrue(
                salt.utils.state.check_result(data), msg="{} failed".format(test)
            )
        test_invalid_true_ht_states = {
            "test_onfail_simple2": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    ("test_vstate0", {"result": False}),
                                    ("test_vstate1", {"result": True}),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_vstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_vstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", True),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_vstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),
            "test_onfail_integ2": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    (
                                        "t_|-test_ivstate0_|-echo_|-run",
                                        {"result": False},
                                    ),
                                    (
                                        "cmd_|-test_ivstate0_|-echo_|-run",
                                        {"result": False},
                                    ),
                                    (
                                        "cmd_|-test_ivstate1_|-echo_|-run",
                                        {"result": False},
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_ivstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                        "t": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_ivstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", False),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_ivstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),
            "test_onfail_integ3": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    (
                                        "t_|-test_ivstate0_|-echo_|-run",
                                        {"result": True},
                                    ),
                                    (
                                        "cmd_|-test_ivstate0_|-echo_|-run",
                                        {"result": False},
                                    ),
                                    (
                                        "cmd_|-test_ivstate1_|-echo_|-run",
                                        {"result": False},
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_ivstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                        "t": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_ivstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", False),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_ivstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),
            "test_onfail_integ4": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    (
                                        "t_|-test_ivstate0_|-echo_|-run",
                                        {"result": False},
                                    ),
                                    (
                                        "cmd_|-test_ivstate0_|-echo_|-run",
                                        {"result": False},
                                    ),
                                    (
                                        "cmd_|-test_ivstate1_|-echo_|-run",
                                        {"result": True},
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_ivstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                        "t": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_ivstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", False),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_ivstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                    "test_ivstate2": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", True),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_ivstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),
            "test_onfail": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    ("test_state0", {"result": False}),
                                    ("test_state", {"result": True}),
                                ]
                            ),
                        ),
                    ]
                ),
                None,
            ),
            "test_onfail_d": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    ("test_state0", {"result": False}),
                                    ("test_state", {"result": True}),
                                ]
                            ),
                        ),
                    ]
                ),
                {},
            ),
        }
        for test, testdata in test_invalid_true_ht_states.items():
            data, ht = testdata
            for t_ in [a for a in data["host1"]]:
                tdata = data["host1"][t_]
                if "_|-" in t_:
                    t_ = t_.split("_|-")[1]
                tdata["__id__"] = t_
            self.assertFalse(
                salt.utils.state.check_result(data, highstate=ht),
                msg="{} failed".format(test),
            )

        test_valid_true_ht_states = {
            "test_onfail_integ": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    (
                                        "cmd_|-test_ivstate0_|-echo_|-run",
                                        {"result": False},
                                    ),
                                    (
                                        "cmd_|-test_ivstate1_|-echo_|-run",
                                        {"result": True},
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_ivstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_ivstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", False),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_ivstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),
            "test_onfail_intega3": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    (
                                        "t_|-test_ivstate0_|-echo_|-run",
                                        {"result": True},
                                    ),
                                    (
                                        "cmd_|-test_ivstate0_|-echo_|-run",
                                        {"result": False},
                                    ),
                                    (
                                        "cmd_|-test_ivstate1_|-echo_|-run",
                                        {"result": True},
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_ivstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                        "t": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_ivstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", False),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_ivstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),
            "test_onfail_simple": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    ("test_vstate0", {"result": False}),
                                    ("test_vstate1", {"result": True}),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_vstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_vstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    ("onfail_stop", False),
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_vstate0")]
                                            )
                                        ],
                                    ),
                                ]
                            ),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),  # order is different
            "test_onfail_simple_rev": (
                salt.utils.odict.OrderedDict(
                    [
                        (
                            "host1",
                            salt.utils.odict.OrderedDict(
                                [
                                    ("test_vstate0", {"result": False}),
                                    ("test_vstate1", {"result": True}),
                                ]
                            ),
                        ),
                    ]
                ),
                {
                    "test_vstate0": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            "run",
                            {"order": 10002},
                        ],
                    },
                    "test_vstate1": {
                        "__env__": "base",
                        "__sls__": "a",
                        "cmd": [
                            salt.utils.odict.OrderedDict([("name", "/bin/true")]),
                            salt.utils.odict.OrderedDict(
                                [
                                    (
                                        "onfail",
                                        [
                                            salt.utils.odict.OrderedDict(
                                                [("cmd", "test_vstate0")]
                                            )
                                        ],
                                    )
                                ]
                            ),
                            salt.utils.odict.OrderedDict([("onfail_stop", False)]),
                            "run",
                            {"order": 10004},
                        ],
                    },
                },
            ),
        }
        for test, testdata in test_valid_true_ht_states.items():
            data, ht = testdata
            for t_ in [a for a in data["host1"]]:
                tdata = data["host1"][t_]
                if "_|-" in t_:
                    t_ = t_.split("_|-")[1]
                tdata["__id__"] = t_
            self.assertTrue(
                salt.utils.state.check_result(data, highstate=ht),
                msg="{} failed".format(test),
            )
        test_valid_false_state = {"host1": {"test_state": {"result": False}}}
        self.assertFalse(salt.utils.state.check_result(test_valid_false_state))


class UtilStateMergeSubreturnTestcase(TestCase):
    """
    Test cases for salt.utils.state.merge_subreturn function.
    """

    main_ret = {
        "name": "primary",
        # result may be missing, as primarysalt.utils.state is still in progress
        "comment": "",
        "changes": {},
    }
    sub_ret = {
        "name": "secondary",
        "result": True,
        "comment": "",
        "changes": {},
    }

    def test_merge_result(self):
        # result not created if not needed
        for no_effect_result in [True, None]:
            m = copy.deepcopy(self.main_ret)
            s = copy.deepcopy(self.sub_ret)
            s["result"] = no_effect_result
            res = salt.utils.state.merge_subreturn(m, s)
            self.assertNotIn("result", res)

        # False subresult is propagated to existing result
        for original_result in [True, None, False]:
            m = copy.deepcopy(self.main_ret)
            m["result"] = original_result
            s = copy.deepcopy(self.sub_ret)
            s["result"] = False
            res = salt.utils.state.merge_subreturn(m, s)
            self.assertFalse(res["result"])

        # False result cannot be overridden
        for any_result in [True, None, False]:
            m = copy.deepcopy(self.main_ret)
            m["result"] = False
            s = copy.deepcopy(self.sub_ret)
            s["result"] = any_result
            res = salt.utils.state.merge_subreturn(m, s)
            self.assertFalse(res["result"])

    def test_merge_changes(self):
        # The main changes dict should always already exist,
        # and there should always be a changes dict in the secondary.
        primary_changes = {"old": None, "new": "my_resource"}
        secondary_changes = {"old": None, "new": ["alarm-1", "alarm-2"]}

        # No changes case
        m = copy.deepcopy(self.main_ret)
        s = copy.deepcopy(self.sub_ret)
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertDictEqual(res["changes"], {})

        # New changes don't get rid of existing changes
        m = copy.deepcopy(self.main_ret)
        m["changes"] = copy.deepcopy(primary_changes)
        s = copy.deepcopy(self.sub_ret)
        s["changes"] = copy.deepcopy(secondary_changes)
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertDictEqual(
            res["changes"],
            {"old": None, "new": "my_resource", "secondary": secondary_changes},
        )

        # The subkey parameter is respected
        m = copy.deepcopy(self.main_ret)
        m["changes"] = copy.deepcopy(primary_changes)
        s = copy.deepcopy(self.sub_ret)
        s["changes"] = copy.deepcopy(secondary_changes)
        res = salt.utils.state.merge_subreturn(m, s, subkey="alarms")
        self.assertDictEqual(
            res["changes"],
            {"old": None, "new": "my_resource", "alarms": secondary_changes},
        )

    def test_merge_comments(self):
        main_comment_1 = "First primary comment."
        main_comment_2 = "Second primary comment."
        sub_comment_1 = "First secondary comment,\nwhich spans two lines."
        sub_comment_2 = "Second secondary comment: {}".format(
            "some error\n  And a traceback",
        )
        final_comment = textwrap.dedent(
            """\
            First primary comment.
            Second primary comment.
            First secondary comment,
            which spans two lines.
            Second secondary comment: some error
              And a traceback
        """.rstrip()
        )

        # Joining two strings
        m = copy.deepcopy(self.main_ret)
        m["comment"] = main_comment_1 + "\n" + main_comment_2
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = sub_comment_1 + "\n" + sub_comment_2
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertMultiLineEqual(res["comment"], final_comment)

        # Joining string and a list
        m = copy.deepcopy(self.main_ret)
        m["comment"] = main_comment_1 + "\n" + main_comment_2
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = [sub_comment_1, sub_comment_2]
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertMultiLineEqual(res["comment"], final_comment)

        # For tests where output is a list,
        # also test that final joined output will match
        # Joining list and a string
        m = copy.deepcopy(self.main_ret)
        m["comment"] = [main_comment_1, main_comment_2]
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = sub_comment_1 + "\n" + sub_comment_2
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertEqual(
            res["comment"],
            [main_comment_1, main_comment_2, sub_comment_1 + "\n" + sub_comment_2],
        )
        self.assertMultiLineEqual("\n".join(res["comment"]), final_comment)

        # Joining two lists
        m = copy.deepcopy(self.main_ret)
        m["comment"] = [main_comment_1, main_comment_2]
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = [sub_comment_1, sub_comment_2]
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertEqual(
            res["comment"],
            [main_comment_1, main_comment_2, sub_comment_1, sub_comment_2],
        )
        self.assertMultiLineEqual("\n".join(res["comment"]), final_comment)

    def test_merge_empty_comments(self):
        # Since the primarysalt.utils.state is in progress,
        # the main comment may be empty, either '' or [].
        # Note that [''] is a degenerate case and should never happen,
        # hence the behavior is left unspecified in that case.
        # The secondary comment should never be empty,
        # because thatsalt.utils.state has already returned,
        # so we leave the behavior unspecified in that case.
        sub_comment_1 = "Secondary comment about changes:"
        sub_comment_2 = "A diff that goes with the previous comment"
        # No contributions from primary
        final_comment = sub_comment_1 + "\n" + sub_comment_2

        # Joining empty string and a string
        m = copy.deepcopy(self.main_ret)
        m["comment"] = ""
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = sub_comment_1 + "\n" + sub_comment_2
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertEqual(res["comment"], final_comment)

        # Joining empty string and a list
        m = copy.deepcopy(self.main_ret)
        m["comment"] = ""
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = [sub_comment_1, sub_comment_2]
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertEqual(res["comment"], final_comment)

        # For tests where output is a list,
        # also test that final joined output will match
        # Joining empty list and a string
        m = copy.deepcopy(self.main_ret)
        m["comment"] = []
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = sub_comment_1 + "\n" + sub_comment_2
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertEqual(res["comment"], [final_comment])
        self.assertEqual("\n".join(res["comment"]), final_comment)

        # Joining empty list and a list
        m = copy.deepcopy(self.main_ret)
        m["comment"] = []
        s = copy.deepcopy(self.sub_ret)
        s["comment"] = [sub_comment_1, sub_comment_2]
        res = salt.utils.state.merge_subreturn(m, s)
        self.assertEqual(res["comment"], [sub_comment_1, sub_comment_2])
        self.assertEqual("\n".join(res["comment"]), final_comment)
