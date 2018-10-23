# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import SSHCase
from tests.support.jinja_filters import JinjaFiltersTest


class SSHJinjaFiltersTest(SSHCase, JinjaFiltersTest):
    '''
    testing Jinja filters are available via state system & salt-ssh
    '''
    pass
