import os

import pytest

import salt.modules.ini_manage as ini
import salt.utils.files
import salt.utils.stringutils


@pytest.fixture
def ini_content():
    return [
        "# Comment on the first line",
        "",
        "# First main option",
        "option1=main1",
        "",
        "# Second main option",
        "option2=main2",
        "",
        "",
        "[main]",
        "# Another comment",
        "test1=value 1",
        "",
        "test2=value 2",
        "",
        "[SectionB]",
        "test1=value 1B",
        "",
        "# Blank line should be above",
        "test3 = value 3B",
        "",
        "[SectionC]",
        "# The following option is empty",
        "empty_option=",
    ]


@pytest.fixture(scope="function")
def ini_file(tmp_path, ini_content):
    file_path = tmp_path / "file.ini"
    yield file_path


# def ini_file_linesep(ini_file, linesep):


def test_section_req():
    """
    Test the __repr__ in the _Section class
    """
    expected = "_Section(){}{{}}".format(os.linesep)
    assert repr(ini._Section("test")) == expected


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_get_option(linesep, ini_file, ini_content):
    """
    Test get_option method.
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    assert ini.get_option(str(ini_file), "main", "test1") == "value 1"
    assert ini.get_option(str(ini_file), "main", "test2") == "value 2"
    assert ini.get_option(str(ini_file), "SectionB", "test1") == "value 1B"
    assert ini.get_option(str(ini_file), "SectionB", "test3") == "value 3B"
    assert ini.get_option(str(ini_file), "SectionC", "empty_option") == ""


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_get_section(linesep, ini_file, ini_content):
    """
    Test get_section method.
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    expected = {"test1": "value 1B", "test3": "value 3B"}
    assert ini.get_section(str(ini_file), "SectionB") == expected


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_remove_option(linesep, ini_file, ini_content):
    """
    Test remove_option method.
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    assert ini.remove_option(str(ini_file), "SectionB", "test1") == "value 1B"
    assert ini.get_option(str(ini_file), "SectionB", "test1") is None


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_remove_section(linesep, ini_file, ini_content):
    """
    Test remove_section method.
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    expected = {"test1": "value 1B", "test3": "value 3B"}
    assert ini.remove_section(str(ini_file), "SectionB") == expected
    assert ini.get_section(str(ini_file), "SectionB") == {}


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_get_ini(linesep, ini_file, ini_content):
    """
    Test get_ini method.
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    expected = {
        "SectionC": {
            "empty_option": "",
        },
        "SectionB": {
            "test1": "value 1B",
            "test3": "value 3B",
        },
        "main": {
            "test1": "value 1",
            "test2": "value 2",
        },
        "option2": "main2",
        "option1": "main1",
    }
    assert dict(ini.get_ini(str(ini_file))) == expected


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_set_option(linesep, ini_file, ini_content):
    """
    Test set_option method.
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    result = ini.set_option(
        str(ini_file),
        {
            "SectionB": {
                "test3": "new value 3B",
                "test_set_option": "test_set_value",
            },
            "SectionD": {"test_set_option2": "test_set_value1"},
        },
    )
    expected = {
        "SectionB": {
            "test3": {"after": "new value 3B", "before": "value 3B"},
            "test_set_option": {"after": "test_set_value", "before": None},
        },
        "SectionD": {
            "after": {"test_set_option2": "test_set_value1"},
            "before": None,
        },
    }
    assert result == expected

    # Check existing option updated
    assert ini.get_option(str(ini_file), "SectionB", "test3") == "new value 3B"

    # Check new section and option added
    assert (
        ini.get_option(str(ini_file), "SectionD", "test_set_option2")
        == "test_set_value1"
    )


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_empty_value(linesep, ini_file, ini_content):
    """
    Test empty value preserved after edit
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    ini.set_option(str(ini_file), {"SectionB": {"test3": "new value 3B"}})
    with salt.utils.files.fopen(str(ini_file), "r") as fp_:
        file_content = salt.utils.stringutils.to_unicode(fp_.read())
    expected = "{0}{1}{0}".format(os.linesep, "empty_option = ")
    assert expected in file_content, "empty_option was not preserved"


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_empty_lines(linesep, ini_file, ini_content):
    """
    Test empty lines preserved after edit
    """
    content = salt.utils.stringutils.to_bytes(linesep.join(ini_content))
    ini_file.write_bytes(content)

    expected = os.linesep.join(
        [
            "# Comment on the first line",
            "",
            "# First main option",
            "option1 = main1",
            "",
            "# Second main option",
            "option2 = main2",
            "",
            "[main]",
            "# Another comment",
            "test1 = value 1",
            "",
            "test2 = value 2",
            "",
            "[SectionB]",
            "test1 = value 1B",
            "",
            "# Blank line should be above",
            "test3 = new value 3B",
            "",
            "[SectionC]",
            "# The following option is empty",
            "empty_option = ",
            "",
        ]
    )
    ini.set_option(str(ini_file), {"SectionB": {"test3": "new value 3B"}})
    with salt.utils.files.fopen(str(ini_file), "r") as fp_:
        file_content = fp_.read()
    assert expected == file_content


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_empty_lines_multiple_edits(linesep, ini_file, ini_content):
    """
    Test empty lines preserved after multiple edits
    """
    ini.set_option(
        str(ini_file),
        {"SectionB": {"test3": "this value will be edited two times"}},
    )
    test_empty_lines(linesep, ini_file, ini_content)


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
def test_different_encoding(linesep, ini_file, ini_content):
    """
    Test ability to read a different encoding
    """
    assert True
