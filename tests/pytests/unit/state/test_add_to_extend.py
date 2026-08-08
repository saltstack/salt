from copy import deepcopy

import pytest

import salt.state
from salt.utils.odict import HashableOrderedDict
from tests.support.mock import patch

pytestmark = [
    pytest.mark.core_test,
]


def _hod(items):
    """
    ``HashableOrderedDict`` no longer accepts an items iterable in
    ``__init__`` (deprecation tightening landed on 3006.x after this PR was
    opened). Build one explicitly so existing test cases keep working.
    """
    d = HashableOrderedDict()
    for k, v in items:
        d[k] = v
    return d


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
            },
            "baz": {
                "file": [{"require": [{"file": "foo"}]}],
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
            },
            "baz": {
                "file": [{"require": [{"file": "foo"}]}],
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
            "bar": _hod(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                ]
            ),
            "baz": _hod(
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
            "bar": _hod(
                [
                    ("file", [{"require": [{"file": "foo"}]}]),
                ]
            ),
            "baz": _hod(
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
                "file": [
                    {
                        "require": [
                            {"file": "foo"},
                        ]
                    },
                ],
            },
            "baz": {
                "file": [
                    {
                        "require": [
                            {"file": "foo"},
                        ]
                    },
                    {
                        "prereq": [
                            {"file": "bar"},
                        ]
                    },
                ],
            },
        },
    ),
]


def _flatten_extend(a):
    return {
        (k1, k2, k4, k6, v6)
        for k1, v1 in a.items()
        for k2, v2 in v1.items()
        for v3 in v2
        for k4, v4 in v3.items()
        for v5 in v4
        for k6, v6 in v5.items()
    }


def test_flatten():
    a = {
        "bar": {"file": [{"require": [{"file": "foo"}]}]},
        "baz": {
            "file": [
                {"require": [{"file": "foo"}]},
                {"prereq": [{"file": "bar"}]},
            ]
        },
    }
    b = {
        "baz": {
            "file": [
                {"prereq": [{"file": "bar"}]},
                {"require": [{"file": "foo"}]},
            ]
        },
        "bar": {"file": [{"require": [{"file": "foo"}]}]},
    }
    assert _flatten_extend(a) == _flatten_extend(b)


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
    assert _flatten_extend(_extend) == _flatten_extend(expected)


# --- Call-site coverage for ``State.requisite_in`` ---
#
# These tests drive ``State.requisite_in`` end-to-end with HighData inputs
# that previously produced duplicate ``{req_state_mod_name: req_id}`` entries
# under the same requisite list (issue #68408). They cover both call sites
# of ``_add_to_extend``:
#
# - ``salt/state.py`` line 2007: the dict-form ``*_in`` branch
#   (``isinstance(items, dict)``).
# - ``salt/state.py`` line 2148: the list-form ``*_in`` branch
#   (``isinstance(items, list)``), used both by ``*_in`` from many
#   originators and by the SLS-hinge expansion.
#
# The shape of the bug is: a single target state has several other states
# declaring a ``*_in`` toward it; before the fix, each declaration appended
# a fresh ``{state: id_}`` mapping to the target's requisite list even
# when that exact pair was already present. The fix deduplicates.


def _count_req_entries(high, target_id, state_mod, req_type, req_state, req_id):
    """
    Walk the high data returned by ``requisite_in`` (after
    ``reconcile_extend`` has merged ``__extend__`` into the target) and
    count how many times ``{req_state: req_id}`` appears under
    ``high[target_id][state_mod][*][req_type]``.
    """
    count = 0
    state_args = high.get(target_id, {}).get(state_mod, [])
    for arg in state_args:
        if not isinstance(arg, dict):
            continue
        for k, v in arg.items():
            if k != req_type:
                continue
            for item in v:
                if isinstance(item, dict) and item.get(req_state) == req_id:
                    count += 1
    return count


def _build_high_dict_form(req_in_key):
    """
    HighData triggering the dict-form ``*_in`` branch (line 2007).

    Two source states (``A`` and ``B``) each declare ``{req_in_key:
    {file: target}}`` — the dict form, single mapping. Both target ``T``.
    Pre-fix: T ends up with [{require: [{file: A}, {file: A}]}] after
    a second run-through of the same source — represented here by
    declaring the same ``*_in`` twice on the same source state.
    """
    return {
        "A": _hod(
            [
                (
                    "file",
                    [
                        # dict-form *_in declared twice on the same source
                        {req_in_key: {"file": "T"}},
                        {req_in_key: {"file": "T"}},
                        "managed",
                        {"order": 10000},
                    ],
                ),
                ("__sls__", "test_sls"),
                ("__env__", "base"),
            ]
        ),
        "T": _hod(
            [
                (
                    "file",
                    [
                        "managed",
                        {"order": 10001},
                    ],
                ),
                ("__sls__", "test_sls"),
                ("__env__", "base"),
            ]
        ),
    }


def _build_high_list_form(req_in_key):
    """
    HighData triggering the list-form ``*_in`` branch (line 2148).

    Source state ``A`` declares ``{req_in_key: [{file: T}, {file: T}]}``
    — the list form with the same target listed twice. This is the bug
    shape reported in #68408 (``hinges`` ends up with duplicate
    ``(name, pstate)`` entries, each triggering an append).
    """
    return {
        "A": _hod(
            [
                (
                    "file",
                    [
                        {req_in_key: [{"file": "T"}, {"file": "T"}]},
                        "managed",
                        {"order": 10000},
                    ],
                ),
                ("__sls__", "test_sls"),
                ("__env__", "base"),
            ]
        ),
        "T": _hod(
            [
                (
                    "file",
                    [
                        "managed",
                        {"order": 10001},
                    ],
                ),
                ("__sls__", "test_sls"),
                ("__env__", "base"),
            ]
        ),
    }


# Map ``*_in`` keys to the requisite key actually written into ``__extend__``.
# ``requisite_in`` strips the ``_in`` suffix via ``rkey = key.split("_")[0]``.
# ``listen_in`` is handled separately by the state runtime (not by
# ``requisite_in``), so it is not in this set.
REQ_IN_KEYS = [
    ("require_in", "require"),
    ("watch_in", "watch"),
    ("onfail_in", "onfail"),
    ("onchanges_in", "onchanges"),
]


@pytest.mark.parametrize("req_in_key,req_key", REQ_IN_KEYS)
def test_requisite_in_dict_form_deduplicates(minion_opts, req_in_key, req_key):
    """
    Call-site coverage for ``salt/state.py`` line 2007 (dict-form ``*_in``).

    Two identical dict-form ``*_in`` declarations on the same source should
    produce a single ``{file: A}`` entry under ``T``'s requisite list, not
    two.
    """
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        high = _build_high_dict_form(req_in_key)
        result_high, errors = state_obj.requisite_in(high)
        assert errors == [], errors
        n = _count_req_entries(result_high, "T", "file", req_key, "file", "A")
        assert n == 1, (
            f"dict-form {req_in_key}: expected one {{file: A}} entry under "
            f"T's {req_key} list, got {n}. high={result_high}"
        )


@pytest.mark.parametrize("req_in_key,req_key", REQ_IN_KEYS)
def test_requisite_in_list_form_deduplicates(minion_opts, req_in_key, req_key):
    """
    Call-site coverage for ``salt/state.py`` line 2148 (list-form ``*_in``).

    A list-form ``*_in`` with the same ``{file: T}`` entry twice should
    produce a single ``{file: A}`` entry under ``T``'s requisite list,
    not two.
    """
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        high = _build_high_list_form(req_in_key)
        result_high, errors = state_obj.requisite_in(high)
        assert errors == [], errors
        n = _count_req_entries(result_high, "T", "file", req_key, "file", "A")
        assert n == 1, (
            f"list-form {req_in_key}: expected one {{file: A}} entry under "
            f"T's {req_key} list, got {n}. high={result_high}"
        )


def test_requisite_in_preserves_env_and_sls_metadata(minion_opts):
    """
    Regression guard: the ``_add_to_extend`` refactor moved the ``__env__``
    / ``__sls__`` writes to after the helper call. Verify ``requisite_in``
    still completes without errors and the require entry lands on T.

    (``reconcile_extend`` consumes ``__env__`` / ``__sls__`` keys off the
    extend block — they do not survive into the merged high data; we
    assert the end-to-end merge succeeded instead.)
    """
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        high = _build_high_dict_form("require_in")
        result_high, errors = state_obj.requisite_in(high)
        assert errors == [], errors
        n = _count_req_entries(result_high, "T", "file", "require", "file", "A")
        assert n == 1, f"merge into T failed: {result_high}"


def test_requisite_in_distinct_sources_not_deduplicated(minion_opts):
    """
    Negative control: dedup must not collapse *distinct* sources. Two
    different IDs (``A`` and ``B``) both declaring ``require_in: file: T``
    must both appear under T's require list.
    """
    high = {
        "A": _hod(
            [
                (
                    "file",
                    [
                        {"require_in": [{"file": "T"}]},
                        "managed",
                        {"order": 10000},
                    ],
                ),
                ("__sls__", "test_sls"),
                ("__env__", "base"),
            ]
        ),
        "B": _hod(
            [
                (
                    "file",
                    [
                        {"require_in": [{"file": "T"}]},
                        "managed",
                        {"order": 10001},
                    ],
                ),
                ("__sls__", "test_sls"),
                ("__env__", "base"),
            ]
        ),
        "T": _hod(
            [
                (
                    "file",
                    [
                        "managed",
                        {"order": 10002},
                    ],
                ),
                ("__sls__", "test_sls"),
                ("__env__", "base"),
            ]
        ),
    }
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        result_high, errors = state_obj.requisite_in(high)
        assert errors == [], errors
        n_a = _count_req_entries(result_high, "T", "file", "require", "file", "A")
        n_b = _count_req_entries(result_high, "T", "file", "require", "file", "B")
        assert n_a == 1, f"expected one {{file: A}} entry, got {n_a}"
        assert n_b == 1, f"expected one {{file: B}} entry, got {n_b}"
