import os
import sys

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


@pytest.fixture
def unicode_content():
    return [
        "# An ini file with some unicode characters",
        "",
        "[Ascii]",
        "de = Deutsch",
        "en_GB = English (UK)",
        "en_US = English (US)",
        "fi = Suomi",
        "hu = Magyar",
        "it = Italiano",
        "nl = Dutch",
        "pt = Portuguese",
        "sv = Svenska",
        "",
        "[Юникод]",
        "# This means unicode in Russian",
        "es = Español",
        "es_ES = Español (ES)",
        "fr = Français",
        "hi = हिंदी",
        "ja = 日本語",
        "ko = :한국어",
        "zh = 简体中文",
        "繁體中文 = zh_TW",
    ]


def test_section_req():
    """
    Test the __repr__ in the _Section class
    """
    expected = f"_Section(){os.linesep}{{}}"
    assert repr(ini._Section("test")) == expected


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_get_option(encoding, linesep, ini_file, ini_content):
    """
    Test get_option method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    option = ini.get_option(str(ini_file), "main", "test1", encoding=encoding)
    assert option == "value 1"

    option = ini.get_option(str(ini_file), "main", "test2", encoding=encoding)
    assert option == "value 2"

    option = ini.get_option(str(ini_file), "SectionB", "test1", encoding=encoding)
    assert option == "value 1B"

    option = ini.get_option(str(ini_file), "SectionB", "test3", encoding=encoding)
    assert option == "value 3B"

    option = ini.get_option(
        str(ini_file), "SectionC", "empty_option", encoding=encoding
    )
    assert option == ""


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_get_section(encoding, linesep, ini_file, ini_content):
    """
    Test get_section method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    expected = {"test1": "value 1B", "test3": "value 3B"}
    assert ini.get_section(str(ini_file), "SectionB", encoding=encoding) == expected


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_remove_option(encoding, linesep, ini_file, ini_content):
    """
    Test remove_option method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    assert (
        ini.remove_option(str(ini_file), "SectionB", "test1", encoding=encoding)
        == "value 1B"
    )
    assert ini.get_option(str(ini_file), "SectionB", "test1", encoding=encoding) is None


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_remove_section(encoding, linesep, ini_file, ini_content):
    """
    Test remove_section method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    expected = {"test1": "value 1B", "test3": "value 3B"}
    assert ini.remove_section(str(ini_file), "SectionB", encoding=encoding) == expected
    assert ini.get_section(str(ini_file), "SectionB", encoding=encoding) == {}


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_get_ini(encoding, linesep, ini_file, ini_content):
    """
    Test get_ini method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
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
    assert dict(ini.get_ini(str(ini_file), encoding=encoding)) == expected


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_set_option(encoding, linesep, ini_file, ini_content):
    """
    Test set_option method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
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
        encoding=encoding,
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
    assert (
        ini.get_option(str(ini_file), "SectionB", "test3", encoding=encoding)
        == "new value 3B"
    )

    # Check new section and option added
    assert (
        ini.get_option(str(ini_file), "SectionD", "test_set_option2", encoding=encoding)
        == "test_set_value1"
    )


@pytest.mark.parametrize("no_spaces", [True, False])
@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_empty_value(encoding, linesep, no_spaces, ini_file, ini_content):
    """
    Test empty value preserved after edit
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    ini.set_option(
        str(ini_file),
        {"SectionB": {"test3": "new value 3B"}},
        encoding=encoding,
        no_spaces=no_spaces,
    )
    with salt.utils.files.fopen(str(ini_file), "r") as fp_:
        file_content = salt.utils.stringutils.to_unicode(fp_.read(), encoding=encoding)
    expected = f"{os.linesep}empty_option{'=' if no_spaces else ' = '}{os.linesep}"
    assert expected in file_content, "empty_option was not preserved"


@pytest.mark.parametrize("no_spaces", [True, False])
@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_empty_lines(encoding, linesep, no_spaces, ini_file, ini_content):
    """
    Test empty lines preserved after edit
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    expected = os.linesep.join(
        [
            "# Comment on the first line",
            "",
            "# First main option",
            f"option1{'=' if no_spaces else ' = '}main1",
            "",
            "# Second main option",
            f"option2{'=' if no_spaces else ' = '}main2",
            "",
            "[main]",
            "# Another comment",
            f"test1{'=' if no_spaces else ' = '}value 1",
            "",
            f"test2{'=' if no_spaces else ' = '}value 2",
            "",
            "[SectionB]",
            f"test1{'=' if no_spaces else ' = '}value 1B",
            "",
            "# Blank line should be above",
            f"test3{'=' if no_spaces else ' = '}new value 3B",
            "",
            "[SectionC]",
            "# The following option is empty",
            f"empty_option{'=' if no_spaces else ' = '}",
            "",
        ]
    )
    ini.set_option(
        str(ini_file),
        {"SectionB": {"test3": "new value 3B"}},
        encoding=encoding,
        no_spaces=no_spaces,
    )
    with salt.utils.files.fopen(str(ini_file), "r") as fp_:
        file_content = fp_.read()
    assert expected == file_content


@pytest.mark.parametrize("no_spaces", [True, False])
@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize(
    "encoding", [None, "cp1252" if sys.platform == "win32" else "ISO-2022-JP"]
)
def test_empty_lines_multiple_edits(
    encoding, linesep, no_spaces, ini_file, ini_content
):
    """
    Test empty lines preserved after multiple edits
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(ini_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    ini.set_option(
        str(ini_file),
        {"SectionB": {"test3": "this value will be edited two times"}},
        encoding=encoding,
        no_spaces=no_spaces,
    )

    expected = os.linesep.join(
        [
            "# Comment on the first line",
            "",
            "# First main option",
            f"option1{'=' if no_spaces else ' = '}main1",
            "",
            "# Second main option",
            f"option2{'=' if no_spaces else ' = '}main2",
            "",
            "[main]",
            "# Another comment",
            f"test1{'=' if no_spaces else ' = '}value 1",
            "",
            f"test2{'=' if no_spaces else ' = '}value 2",
            "",
            "[SectionB]",
            f"test1{'=' if no_spaces else ' = '}value 1B",
            "",
            "# Blank line should be above",
            f"test3{'=' if no_spaces else ' = '}new value 3B",
            "",
            "[SectionC]",
            "# The following option is empty",
            f"empty_option{'=' if no_spaces else ' = '}",
            "",
        ]
    )
    ini.set_option(
        str(ini_file),
        {"SectionB": {"test3": "new value 3B"}},
        encoding=encoding,
        no_spaces=no_spaces,
    )
    with salt.utils.files.fopen(str(ini_file), "r") as fp_:
        file_content = fp_.read()
    assert expected == file_content


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize("encoding", [None, "utf-16", "utf-32-le"])
def test_unicode_get_option(encoding, linesep, ini_file, unicode_content):
    """
    Test ability to get an option from a file that contains unicode characters
    We can't encode the file with something that doesn't support unicode
    Ie: cp1252
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(unicode_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    # Get a non-unicode value
    assert ini.get_option(str(ini_file), "Ascii", "de", encoding=encoding) == "Deutsch"

    # Get a unicode value
    assert ini.get_option(str(ini_file), "Юникод", "hi", encoding=encoding) == "हिंदी"


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize("encoding", [None, "utf-16", "utf-16-le", "utf-32-le"])
def test_unicode_set_option(encoding, linesep, ini_file, unicode_content):
    """
    Test ability to set an option in a file that contains unicode characters.
    The option itself may be unicode
    We can't encode the file with something that doesn't support unicode
    Ie: cp1252
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(unicode_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    result = ini.set_option(
        str(ini_file),
        {
            "Ascii": {"ay": "Aymar"},
            "Юникод": {"dv": "ދިވެހިބަސް"},
        },
        encoding=encoding,
    )
    expected = {
        "Ascii": {
            "ay": {
                "before": None,
                "after": "Aymar",
            },
        },
        "Юникод": {
            "dv": {
                "before": None,
                "after": "ދިވެހިބަސް",
            },
        },
    }
    assert result == expected

    # Check existing option updated
    assert ini.get_option(str(ini_file), "Ascii", "ay", encoding=encoding) == "Aymar"

    # Check new section and option added
    assert ini.get_option(str(ini_file), "Юникод", "dv", encoding=encoding) == "ދިވެހިބަސް"


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize("encoding", [None, "utf-16", "utf-16-le", "utf-32-le"])
def test_unicode_get_section(encoding, linesep, ini_file, unicode_content):
    """
    Test get_section method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(unicode_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    expected = {
        "es": "Español",
        "es_ES": "Español (ES)",
        "fr": "Français",
        "hi": "हिंदी",
        "ja": "日本語",
        "ko": ":한국어",
        "zh": "简体中文",
        "繁體中文": "zh_TW",
    }
    assert ini.get_section(str(ini_file), "Юникод", encoding=encoding) == expected


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize("encoding", [None, "utf-16", "utf-16-le", "utf-32-le"])
def test_unicode_remove_option(encoding, linesep, ini_file, unicode_content):
    """
    Test remove_option method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(unicode_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    assert (
        ini.remove_option(str(ini_file), "Юникод", "繁體中文", encoding=encoding)
        == "zh_TW"
    )
    assert (
        ini.get_option(str(ini_file), "Юникод", "繁體中文", encoding=encoding) is None
    )


@pytest.mark.parametrize("linesep", ["\r", "\n", "\r\n"])
@pytest.mark.parametrize("encoding", [None, "utf-16", "utf-16-le", "utf-32-le"])
def test_unicode_remove_section(encoding, linesep, ini_file, unicode_content):
    """
    Test remove_section method.
    """
    content = salt.utils.stringutils.to_bytes(
        linesep.join(unicode_content), encoding=encoding
    )
    ini_file.write_bytes(content)

    expected = {
        "es": "Español",
        "es_ES": "Español (ES)",
        "fr": "Français",
        "hi": "हिंदी",
        "ja": "日本語",
        "ko": ":한국어",
        "zh": "简体中文",
        "繁體中文": "zh_TW",
    }
    assert ini.remove_section(str(ini_file), "Юникод", encoding=encoding) == expected
    assert ini.get_section(str(ini_file), "Юникод", encoding=encoding) == {}


def test_set_option_preserves_indented_options(ini_file):
    """
    Test that setting an option does not delete indented options in other
    sections (e.g. a git-style config where options are indented).

    Regression test for #36354.
    """
    ini_content = os.linesep.join(
        [
            "[core]",
            "",
            '[remote "origin"]',
            "        url = git@version-control:test.git",
            "        fetch = +refs/heads/*:refs/remotes/origin/*",
        ]
    )
    ini_file.write_text(ini_content)

    ini.set_option(str(ini_file), {"core": {"sharedRepository": "group"}})

    # The indented options in the untouched section must survive
    assert (
        ini.get_option(str(ini_file), 'remote "origin"', "url")
        == "git@version-control:test.git"
    )
    assert (
        ini.get_option(str(ini_file), 'remote "origin"', "fetch")
        == "+refs/heads/*:refs/remotes/origin/*"
    )
    # The new option was still written
    assert ini.get_option(str(ini_file), "core", "sharedRepository") == "group"


def test_section_refresh_parses_leading_indented_options_36354():
    """
    Call the fixed _Section.refresh directly with a section body whose
    options are all indented (git-style config), the case that used to be
    silently dropped.

    Regression test for #36354.
    """
    # Mirror the production call site in _Ini.refresh: the section body is
    # passed positionally as inicontents with separator="=" and refresh()
    # is then called with no arguments, so it parses self.inicontents.
    sect_ini = os.linesep.join(
        [
            "        url = git@version-control:test.git",
            "        fetch = +refs/heads/*:refs/remotes/origin/*",
        ]
    )
    sect = ini._Section('remote "origin"', sect_ini, separator="=")
    sect.refresh()

    # Before the fix, refresh() consumed indented lines even when there was
    # no previous option to append them to, so the section came back empty.
    assert sect.get("url") == "git@version-control:test.git"
    assert sect.get("fetch") == "+refs/heads/*:refs/remotes/origin/*"


def test_section_refresh_keeps_continuation_lines_36354():
    """
    Guard against overcorrection of the #36354 fix: an indented line that
    follows a normal option must still be folded into that option's value
    as a continuation line, not parsed as a separate option or dropped.
    This passes with and without the fix.
    """
    sect_ini = os.linesep.join(
        [
            "key1 = value1",
            "    continuation line",
            "key2 = value2",
        ]
    )
    sect = ini._Section("test", sect_ini, separator="=")
    sect.refresh()

    assert sect.get("key1") == os.linesep.join(["value1", "    continuation line"])
    assert sect.get("key2") == "value2"
    # The continuation line must not have become its own entry
    assert len(sect) == 2
