import logging
from copy import deepcopy

import pytest

import salt.config
import salt.state
from salt.utils.odict import HashableOrderedDict

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def minion_config(minion_opts):
    minion_opts["file_client"] = "local"
    minion_opts["id"] = "foo01"
    return minion_opts


single_extend_test_cases = [
    (
        {},  # extend
        "bar",  # id_to_extend
        "file",  # state_mod_name
        "require",  # req_type
        "foo",  # req_id
        "file",  # req_state_mod_name
        {
            "bar": HashableOrderedDict({"file": [{"require": [{"file": "foo"}]}]})
        },  # expected
    )
]

simple_extend_test_cases = [
    (
        {},  # extend
        "bar",  # id_to_extend
        "file",  # state_mod_name
        "require",  # req_type
        "foo",  # req_id
        "file",  # req_state_mod_name
        {"bar": {"file": [{"require": [{"file": "foo"}]}]}},  # expected
    ),
    (
        {  # extend
            "bar": {
                "file": [{"require": [{"file": "foo"}]}],
                "__env__": "base",
                "__sls__": "test.foo",
            },
            "baz": {
                "file": [{"require": [{"file": "foo"}]}],
                "__env__": "base",
                "__sls__": "test.foo",
            },
        },
        "baz",  # id_to_extend
        "file",  # state_mod_name
        "require",  # req_type
        "foo",  # req_id
        "file",  # req_state_mod_name
        {  # expected
            "bar": {
                "file": [{"require": [{"file": "foo"}]}],
                "__env__": "base",
                "__sls__": "test.foo",
            },
            "baz": {
                "file": [{"require": [{"file": "foo"}]}],
                "__env__": "base",
                "__sls__": "test.foo",
            },
        },
    ),
    (
        {  # extend
            "/tmp/bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "foo": HashableOrderedDict(
                [("file", [{"prerequired": [{"pkg": "quux-pkg"}]}])]
            ),
            "quux-pkg": HashableOrderedDict(
                [
                    ("file", [{"prereq": [{"pkg": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
        },
        "/tmp/baz",  # id_to_extend
        "file",  # state_mod_name
        "require",  # req_type
        "bar",  # req_id
        "file",  # req_state_mod_name
        {  # expected
            "/tmp/bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "foo": HashableOrderedDict(
                [("file", [{"prerequired": [{"pkg": "quux-pkg"}]}])]
            ),
            "quux-pkg": HashableOrderedDict(
                [
                    ("file", [{"prereq": [{"pkg": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "/tmp/baz": HashableOrderedDict(
                [("file", [{"require": [{"file": "bar"}]}])]
            ),
        },
    ),
    (
        {
            "bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "foo": HashableOrderedDict(
                [("file", [{"prerequired": [{"pkg": "quux"}]}])]
            ),
            "quux": HashableOrderedDict(
                [
                    ("file", [{"prereq": [{"pkg": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
        },
        "baz",
        "file",
        "require",
        "bar",
        "file",
        {
            "bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}, {"file": "bar"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "foo": HashableOrderedDict(
                [("file", [{"prerequired": [{"pkg": "quux"}]}])]
            ),
            "quux": HashableOrderedDict(
                [
                    ("file", [{"prereq": [{"pkg": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
        },
    ),
    (
        {
            "bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
        },
        "baz",
        "file",
        "require",
        "bar",
        "file",
        {
            "bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}, {"file": "bar"}]}]),
                    ("__env__", "base"),
                    ("__sls__", "test.foo"),
                ]
            ),
        },
    ),
]


@pytest.mark.parametrize(
    "extend,id_to_extend,state_mod_name,req_type,req_id,req_state_mod_name,expected",
    simple_extend_test_cases,
)
def test_simple_extend(
    extend, id_to_extend, state_mod_name, req_type, req_id, req_state_mod_name, expected
):
    #  local copy of extend, as it is modified by _add_to_extend
    _extend = deepcopy(extend)

    salt.state.State._add_to_extend(
        _extend, id_to_extend, state_mod_name, req_type, req_id, req_state_mod_name
    )
    assert _extend == expected
