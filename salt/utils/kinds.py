# -*- coding: utf-8 -*-
'''
Application Kinds of Salt apps.
These are used to indicate what kind of Application is using RAET
'''
from __future__ import absolute_import
from collections import namedtuple
from salt.utils.odict import OrderedDict

# Python equivalent of an enum
APPL_KINDS = OrderedDict([('master', 0),
                          ('minion', 1),
                          ('syndic', 2),
                          ('caller', 3)])
APPL_KIND_NAMES = OrderedDict((v, k) for k, v in list(APPL_KINDS.items()))  # inverse map
ApplKind = namedtuple('ApplKind', list(APPL_KINDS.keys()))
applKinds = ApplKind(**APPL_KINDS)
