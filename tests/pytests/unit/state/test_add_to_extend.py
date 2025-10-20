from copy import deepcopy

import pytest

import salt.state
from salt.utils.odict import HashableOrderedDict

pytestmark = [
    pytest.mark.core_test,
]


simple_extend_test_cases = [
    (
        # Simple addition
        #
        # add_to_extend:
        # foo:
        #   file.managed:
        #     - required_in:
        #       - file: bar
        {},  # extend
        "bar",  # id_to_extend
        "file",  # state_mod_name
        "require",  # req_type
        "foo",  # req_id
        "file",  # req_state_mod_name
        {"bar": {"file": [{"require": [{"file": "foo"}]}]}},  # expected
    ),
    (
        # Requisite already exists
        #
        # bar:
        #   file.managed:
        #     require:
        #       - file: foo
        # baz:
        #   file.managed:
        #     - require:
        #       - file: foo
        #
        # add_to_extend:
        # foo:
        #   file.managed:
        #     - required_in:
        #       - file: baz
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
        # Append requisite
        #
        # bar:
        #   file.managed:
        #     require:
        #       - file: foo
        # baz:
        #   file.managed:
        #     - require:
        #       - file: foo
        #
        # add_to_extend:
        # bar:
        #  file.managed:
        #    - require_in:
        #       - file: baz
        {  # extend
            "bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                ]
            ),
        },
        "baz",  # id_to_extend
        "file",  # state_mod_name
        "require",  # req_type
        "bar",  # req_id
        "file",  # req_state_mod_name
        {  # expected
            "bar": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                ]
            ),
            "baz": HashableOrderedDict(
                [
                    ("file", [{"require": [{"file": "foo"}, {"file": "bar"}]}]),
                ]
            ),
        },
    ),
    (
        # Append with different requisite type
        #
        # bar:
        #   file.managed:
        #     require:
        #       - file: foo
        # baz:
        #   file.managed:
        #     - require:
        #       - file: foo
        #
        # add_to_extend:
        # bar:
        #   file.managed:
        #     - prereq_in:
        #       - file: baz
        {  # extend
            "bar": {
                "file": [{"require": [{"file": "foo"}]}],
            },
            "baz": {
                "file": [{"require": [{"file": "foo"}]}],
            },
        },
        "baz",  # id_to_extend
        "file",  # state_mod_name
        "prereq",  # req_type
        "bar",  # req_id
        "file",  # req_state_mod_name
        {  # expected
            "bar": {
                "file": [{"require": [{"file": "foo"}]}],
            },
            "baz": {
                "file": [{"require": [{"file": "foo"}], "prereq": [{"file": "bar"}]}],
            },
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
