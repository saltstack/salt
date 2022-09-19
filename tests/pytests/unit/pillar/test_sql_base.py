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
