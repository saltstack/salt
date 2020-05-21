# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.jinja_filters import JinjaFiltersTest


class StateModuleJinjaFiltersTest(ModuleCase, JinjaFiltersTest):
    """
    testing Jinja filters are available via state system
    """
