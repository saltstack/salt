import pytest

import salt.pillar.sql_base as sql_base
from tests.support.mock import MagicMock


class FakeExtPillar(sql_base.SqlBaseExtPillar):
    """
    Mock SqlBaseExtPillar implementation for testing purpose
    """

    @classmethod
    def _db_name(cls):
        return "fake"

    def _get_cursor(self):
        return MagicMock()


@pytest.mark.parametrize("as_list", [True, False])
def test_process_results_as_json(as_list):
    """
    Validates merging of dict values returned from JSON datatype.
    """
    return_data = FakeExtPillar()
    return_data.as_list = as_list
    return_data.as_json = True
    return_data.with_lists = None
    return_data.enter_root(None)
    return_data.process_fields(["json_data"], 0)
    test_dicts = [
        ({"a": [1]},),
        ({"b": [2, 3]},),
        ({"a": [4]},),
        ({"c": {"d": [4, 5], "e": 6}},),
        ({"f": [{"g": 7, "h": "test"}], "c": {"g": 8}},),
    ]
    return_data.process_results(test_dicts)
    assert return_data.result == {
        "a": [1, 4] if as_list else [4],
        "b": [2, 3],
        "c": {"d": [4, 5], "e": 6, "g": 8},
        "f": [{"g": 7, "h": "test"}],
    }


@pytest.mark.parametrize("as_list", [True, False])
def test_process_results_as_json_string_rows(as_list):
    """
    Regression test for #63684: MySQLdb (and some PyMySQL configurations)
    return JSON columns as ``str`` rather than as pre-decoded dicts.
    ``process_results`` must decode string rows before merging so it does
    not raise ``TypeError`` from ``dictupdate.update``.
    """
    return_data = FakeExtPillar()
    return_data.as_list = as_list
    return_data.as_json = True
    return_data.with_lists = None
    return_data.enter_root(None)
    return_data.process_fields(["json_data"], 0)
    test_rows = [
        ('{"a": [1]}',),
        ('{"b": [2, 3]}',),
        ('{"a": [4]}',),
        ('{"c": {"d": [4, 5], "e": 6}}',),
        ('{"f": [{"g": 7, "h": "test"}], "c": {"g": 8}}',),
    ]
    return_data.process_results(test_rows)
    assert return_data.result == {
        "a": [1, 4] if as_list else [4],
        "b": [2, 3],
        "c": {"d": [4, 5], "e": 6, "g": 8},
        "f": [{"g": 7, "h": "test"}],
    }


@pytest.mark.parametrize("as_list", [True, False])
def test_process_results_as_json_bytes_rows(as_list):
    """
    Regression test for #63684: some driver/charset combinations return JSON
    columns as ``bytes``. ``process_results`` must decode bytes rows before
    merging so it does not raise ``TypeError`` from ``dictupdate.update``.
    """
    return_data = FakeExtPillar()
    return_data.as_list = as_list
    return_data.as_json = True
    return_data.with_lists = None
    return_data.enter_root(None)
    return_data.process_fields(["json_data"], 0)
    test_rows = [
        (b'{"a": [1]}',),
        (b'{"b": [2, 3]}',),
        (b'{"a": [4]}',),
        (b'{"c": {"d": [4, 5], "e": 6}}',),
        (b'{"f": [{"g": 7, "h": "test"}], "c": {"g": 8}}',),
    ]
    return_data.process_results(test_rows)
    assert return_data.result == {
        "a": [1, 4] if as_list else [4],
        "b": [2, 3],
        "c": {"d": [4, 5], "e": 6, "g": 8},
        "f": [{"g": 7, "h": "test"}],
    }


def test_process_results_as_json_non_dict_string_row_raises():
    """
    Regression test for #63684: if a JSON row decodes to a non-dict value
    (e.g. a scalar), raise a clear ``TypeError`` instead of blowing up
    deep inside ``dictupdate.update``.
    """
    return_data = FakeExtPillar()
    return_data.as_list = False
    return_data.as_json = True
    return_data.with_lists = None
    return_data.enter_root(None)
    return_data.process_fields(["json_data"], 0)
    with pytest.raises(TypeError):
        return_data.process_results([("42",)])
