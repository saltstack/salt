"""
    :codeauthor: :email:`saltybob <bbaker@saltstack.com`
"""

from salt.client.ssh.wrapper import state


def test_parse_mods():
    """
    Test _parse_mods
    """
    expected = ["a", "b", "c", "d", "e", "f"]
    mods = "a,b, c,  d,e ,f  "

    actual = state._parse_mods(mods)
    assert expected == actual
