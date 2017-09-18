# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for dvs related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock
from salt.exceptions import VMwareObjectRetrievalError, VMwareApiError, \
        ArgumentValueError, VMwareRuntimeError

#i Import Salt libraries
import salt.utils.vmware as vmware
# Import Third Party Libs
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


class FakeTaskClass(object):
    pass
