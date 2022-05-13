from tests.support.case import ModuleCase
from tests.support.jinja_filters import JinjaFiltersTest


class StateModuleJinjaFiltersTest(ModuleCase, JinjaFiltersTest):
    """
    testing Jinja filters are available via state system
    """
