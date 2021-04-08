# -*- coding: utf-8 -*-
'''
    :codeauthor: Naveena <naveena.maplelabs@cohesity.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import sys

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
)

# Import Salt Libs
import salt.modules.cohesity as cohesity


@pytest.fixture
def configure_loader_modules():
    return {cohesity: {}}


def test_register_vcenter(self):
    '''
    Test if the parsing function works
    '''
    context_key = {"cohesity.context_key": Mock(return_value=True)}
    key = patch.dict(cohesity.__context__, context_key)
    msg = "Successfully registered source ABC"
    with key:
        result = cohesity.register_vcenter("ABC", "User", "Passowrd")
        assert result == msg

