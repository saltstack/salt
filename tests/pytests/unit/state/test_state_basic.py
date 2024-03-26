"""
Test functions in state.py that are not a part of a class
"""

import pytest

import salt.state
from salt.utils.odict import OrderedDict

pytestmark = [
    pytest.mark.core_test,
]


def test_state_args():
    """
    Testing state.state_args when this state is being used:

    /etc/foo.conf:
      file.managed:
        - contents: "blah"
        - mkdirs: True
        - user: ch3ll
        - group: ch3ll
        - mode: 755

    /etc/bar.conf:
      file.managed:
        - use:
          - file: /etc/foo.conf
    """
    id_ = "/etc/bar.conf"
    state = "file"
    high = OrderedDict(
        [
            (
                "/etc/foo.conf",
                OrderedDict(
                    [
                        (
                            "file",
                            [
                                OrderedDict([("contents", "blah")]),
                                OrderedDict([("mkdirs", True)]),
                                OrderedDict([("user", "ch3ll")]),
                                OrderedDict([("group", "ch3ll")]),
                                OrderedDict([("mode", 755)]),
                                "managed",
                                {"order": 10000},
                            ],
                        ),
                        ("__sls__", "test"),
                        ("__env__", "base"),
                    ]
                ),
            ),
            (
                "/etc/bar.conf",
                OrderedDict(
                    [
                        (
                            "file",
                            [
                                OrderedDict(
                                    [
                                        (
                                            "use",
                                            [OrderedDict([("file", "/etc/foo.conf")])],
                                        )
                                    ]
                                ),
                                "managed",
                                {"order": 10001},
                            ],
                        ),
                        ("__sls__", "test"),
                        ("__env__", "base"),
                    ]
                ),
            ),
        ]
    )
    ret = salt.state.state_args(id_, state, high)
    assert ret == {"order", "use"}


def test_state_args_id_not_high():
    """
    Testing state.state_args when id_ is not in high
    """
    id_ = "/etc/bar.conf2"
    state = "file"
    high = OrderedDict(
        [
            (
                "/etc/foo.conf",
                OrderedDict(
                    [
                        (
                            "file",
                            [
                                OrderedDict([("contents", "blah")]),
                                OrderedDict([("mkdirs", True)]),
                                OrderedDict([("user", "ch3ll")]),
                                OrderedDict([("group", "ch3ll")]),
                                OrderedDict([("mode", 755)]),
                                "managed",
                                {"order": 10000},
                            ],
                        ),
                        ("__sls__", "test"),
                        ("__env__", "base"),
                    ]
                ),
            ),
            (
                "/etc/bar.conf",
                OrderedDict(
                    [
                        (
                            "file",
                            [
                                OrderedDict(
                                    [
                                        (
                                            "use",
                                            [OrderedDict([("file", "/etc/foo.conf")])],
                                        )
                                    ]
                                ),
                                "managed",
                                {"order": 10001},
                            ],
                        ),
                        ("__sls__", "test"),
                        ("__env__", "base"),
                    ]
                ),
            ),
        ]
    )
    ret = salt.state.state_args(id_, state, high)
    assert ret == set()


def test_state_args_state_not_high():
    """
    Testing state.state_args when state is not in high date
    """
    id_ = "/etc/bar.conf"
    state = "file2"
    high = OrderedDict(
        [
            (
                "/etc/foo.conf",
                OrderedDict(
                    [
                        (
                            "file",
                            [
                                OrderedDict([("contents", "blah")]),
                                OrderedDict([("mkdirs", True)]),
                                OrderedDict([("user", "ch3ll")]),
                                OrderedDict([("group", "ch3ll")]),
                                OrderedDict([("mode", 755)]),
                                "managed",
                                {"order": 10000},
                            ],
                        ),
                        ("__sls__", "test"),
                        ("__env__", "base"),
                    ]
                ),
            ),
            (
                "/etc/bar.conf",
                OrderedDict(
                    [
                        (
                            "file",
                            [
                                OrderedDict(
                                    [
                                        (
                                            "use",
                                            [OrderedDict([("file", "/etc/foo.conf")])],
                                        )
                                    ]
                                ),
                                "managed",
                                {"order": 10001},
                            ],
                        ),
                        ("__sls__", "test"),
                        ("__env__", "base"),
                    ]
                ),
            ),
        ]
    )
    ret = salt.state.state_args(id_, state, high)
    assert ret == set()
