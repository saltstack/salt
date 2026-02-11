import salt.utils.tornado as tornado_utils


def test_re_unescape_basic():
    assert tornado_utils.re_unescape(r"\.") == "."
    assert tornado_utils.re_unescape(r"\d") == "d"


def test_re_unescape_docstring_includes_backslash():
    assert "``\\d``" in tornado_utils.RE_UNESCAPE_DOC

