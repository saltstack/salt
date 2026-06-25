"""
Tests for the documented slots examples in ``doc/topics/slots/index.rst``.

These tests render the documented SLS samples through ``state.apply`` and
assert the slot-resolved values land in the state arguments.
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.core_test,
]


@pytest.fixture(scope="module")
def state(modules):
    return modules.state


def test_documented_slot_in_arg(state, state_tree, tmp_path):
    """
    The slot returns a string and that string is used as the state arg.

    Documented example: ``name: __slot__:salt:test.echo(<value>)``.
    """
    marker = tmp_path / "slots_marker_arg"
    sls = f"""
    write-arg-marker:
      file.managed:
        - name: __slot__:salt:test.echo({marker})
        - contents: arg-resolved
        - makedirs: True
    """
    with pytest.helpers.temp_file("slots_arg.sls", sls, state_tree):
        ret = state.sls("slots_arg")
    assert ret.failed is False, ret.raw
    assert marker.exists(), f"expected {marker} to be created via slot-resolved name"
    assert marker.read_text().rstrip() == "arg-resolved"


def test_documented_slot_append(state, state_tree, tmp_path):
    """
    The slot returns a string and ``~`` appends a literal suffix.

    Documented example: ``__slot__:salt:test.echo(<base>) ~ "/suffix"``.
    """
    base = tmp_path / "slots_base"
    base.mkdir()
    expected = base / "appended"
    sls = f"""
    write-appended-marker:
      file.managed:
        - name: __slot__:salt:test.echo({base}) ~ "/appended"
        - contents: append-resolved
        - makedirs: True
    """
    with pytest.helpers.temp_file("slots_append.sls", sls, state_tree):
        ret = state.sls("slots_append")
    assert ret.failed is False, ret.raw
    assert expected.exists(), f"expected {expected} to be created via appended slot"
    assert expected.read_text().rstrip() == "append-resolved"
