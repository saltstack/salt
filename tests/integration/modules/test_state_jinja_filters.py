# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase

# Import Salt libs
from tests.support.jinja_filters import JinjaFiltersTest

import logging
log = logging.getLogger(__name__)


class StateModuleJinjaFiltersTest(ModuleCase, JinjaFiltersTest):
    '''
    Validate jinja filters via state module
    '''
    pass
