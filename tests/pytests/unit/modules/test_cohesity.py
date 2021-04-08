"""
    :codeauthor: Naveena <naveena.maplelabs@cohesity.com>
"""

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mock import MagicMock, patch
)

# Import Salt Libs
import salt.modules.cohesity as cohesity


def test_register_vcenter(self):
    """
    Test if the parsing function works
    """
    context_key = {"cohesity.context_key": MagicMock(return_value=True)}
    key = patch.dict(cohesity.__context__, context_key)
    msg = "Successfully registered source ABC"
    with key:
        result = cohesity.register_vcenter("ABC", "User", "Passowrd")
        assert result == msg
