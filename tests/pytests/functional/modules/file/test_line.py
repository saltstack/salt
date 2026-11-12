"""
Functional tests for ``file.line`` on non-ASCII text files.
"""

import codecs

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


@pytest.mark.parametrize("prefix", [b"", codecs.BOM_UTF8], ids=["utf-8", "utf-8-bom"])
def test_line_keeps_utf8(file, tmp_path, prefix):
    """
    The file is written back as UTF-8, not in the system locale's encoding
    (issue #54377).
    """
    path = tmp_path / "web.config"
    text = "<configuration>\r\n  <!-- \u4e2d\u6587 \u201cquoted\u201d -->\r\n</configuration>\r\n"
    path.write_bytes(prefix + text.encode("utf-8"))
    content = '  <add key="a" value="\u503c" />'
    kwargs = {"content": content, "mode": "ensure", "before": "</configuration>"}
    expected = prefix + text.replace(
        "\r\n</configuration>", f"\r\n{content}\r\n</configuration>"
    ).encode("utf-8")

    assert file.line(str(path), **kwargs)
    assert path.read_bytes() == expected

    assert not file.line(str(path), **kwargs)
    assert path.read_bytes() == expected
