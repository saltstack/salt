import io

# import pytest
import salt.returners.highstate_return as highstate_return


def test_generate_table_should_correctly_escape_html_characters_when_data_contains_both_list_and_dict():
    unescaped_fnord = "&fnord&"
    unescaped_dronf = "<dronf>"
    expected_escaped_fnord = "&amp;fnord&amp;"
    expected_escaped_dronf = "&lt;dronf&gt;"
    data = [["something", "or", "another", unescaped_fnord, {"cool": unescaped_dronf}]]

    out = io.StringIO()
    highstate_return._generate_html_table(data=data, out=out)
    out.seek(0)
    actual_table = out.read()

    assert expected_escaped_fnord in actual_table
    assert expected_escaped_dronf in actual_table
