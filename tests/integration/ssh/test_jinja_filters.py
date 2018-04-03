# Import Salt Testing Libs
from tests.support.case import SSHCase

from tests.support.jinja_filters import JinjaFiltersTest


class SSHJinjaFiltersTest(SSHCase, JinjaFiltersTest):
    pass
