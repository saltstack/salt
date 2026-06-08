"""
Unit tests for the _dict_to_ps_hashtable and _ps_quote helpers in
win_dsc_resource.

These tests have no platform or Windows dependencies and require no mocking.
"""

import salt.modules.win_dsc_resource as win_dsc_resource


class TestPsQuote:
    """Tests for _ps_quote single-quote escaping."""

    def test_plain_string(self):
        assert win_dsc_resource._ps_quote("hello") == "hello"

    def test_single_quote_doubled(self):
        assert win_dsc_resource._ps_quote("it's") == "it''s"

    def test_multiple_single_quotes(self):
        assert win_dsc_resource._ps_quote("don't won't") == "don''t won''t"

    def test_empty_string(self):
        assert win_dsc_resource._ps_quote("") == ""

    def test_non_string_coerced(self):
        assert win_dsc_resource._ps_quote(42) == "42"


class TestDictToPsHashtable:
    """Tests for _dict_to_ps_hashtable type conversion."""

    def test_empty_dict(self):
        assert win_dsc_resource._dict_to_ps_hashtable({}) == "@{}"

    def test_string_value(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Key": "Value"})
        assert result == "@{Key = 'Value'}"

    def test_string_escapes_single_quotes(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Key": "It's here"})
        assert result == "@{Key = 'It''s here'}"

    def test_string_escapes_multiple_single_quotes(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Key": "don't won't"})
        assert result == "@{Key = 'don''t won''t'}"

    def test_bool_true(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Enabled": True})
        assert result == "@{Enabled = $true}"

    def test_bool_false(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Enabled": False})
        assert result == "@{Enabled = $false}"

    def test_bool_is_not_confused_with_int(self):
        # bool is a subclass of int in Python; ensure bools are handled first
        result_true = win_dsc_resource._dict_to_ps_hashtable({"Val": True})
        result_one = win_dsc_resource._dict_to_ps_hashtable({"Val": 1})
        assert result_true == "@{Val = $true}"
        assert result_one == "@{Val = 1}"

    def test_integer_value(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Count": 42})
        assert result == "@{Count = 42}"

    def test_zero(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Count": 0})
        assert result == "@{Count = 0}"

    def test_float_value(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Ratio": 1.5})
        assert result == "@{Ratio = 1.5}"

    def test_none_value(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Value": None})
        assert result == "@{Value = $null}"

    def test_list_of_strings(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Items": ["a", "b", "c"]})
        assert result == "@{Items = @('a', 'b', 'c')}"

    def test_list_escapes_single_quotes(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Items": ["it's"]})
        assert result == "@{Items = @('it''s')}"

    def test_empty_list(self):
        result = win_dsc_resource._dict_to_ps_hashtable({"Items": []})
        assert result == "@{Items = @()}"

    def test_multiple_keys(self):
        result = win_dsc_resource._dict_to_ps_hashtable(
            {"Name": "Web-Server", "Ensure": "Present"}
        )
        assert result == "@{Name = 'Web-Server'; Ensure = 'Present'}"

    def test_mixed_types(self):
        result = win_dsc_resource._dict_to_ps_hashtable(
            {"Name": "test", "Count": 3, "Enabled": True, "Tag": None}
        )
        assert result == "@{Name = 'test'; Count = 3; Enabled = $true; Tag = $null}"
