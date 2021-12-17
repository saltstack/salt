"""
    :codeauthor: :email:`saltybob <bbaker@saltstack.com`
"""

from salt.client.ssh.wrapper import state
from tests.support.unit import TestCase


class StateTests(TestCase):
    def test_parse_mods(self):
        """
        Test _parse_mods
        """
        expected = ["a", "b", "c", "d", "e", "f"]
        mods = "a,b, c,  d,e ,f  "

        actual = state._parse_mods(mods)
        self.assertEqual(expected, actual)
