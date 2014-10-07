# -*- coding: utf-8 -*-
'''
The daemons package is used to store implimentations of the Salt Master and
Minion enabling different transports.
'''

# Import Python Libs
from collections import namedtuple

# Import Salt Libs
from salt.utils.odict import OrderedDict

# Python equivalent of an enum
APPL_KINDS = OrderedDict([('master', 0), ('minion', 1), ('syndic', 2), ('call', 3)])
APPL_KIND_NAMES = OrderedDict((v, k) for k, v in APPL_KINDS.iteritems())  # inverse map
ApplKind = namedtuple('ApplKind', APPL_KINDS.keys())
applKinds = ApplKind(**APPL_KINDS)
