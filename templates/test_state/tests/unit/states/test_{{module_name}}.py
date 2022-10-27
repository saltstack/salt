'''
    :codeauthor: {{full_name}} <{{email}}>
'''


from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import patch
import salt.states.{{module_name}} as {{module_name}}


class {{module_name|capitalize}}TestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {% raw -%} {
            {% endraw -%} {{module_name}} {%- raw -%}: {
                '__env__': 'base'
            }
        } {%- endraw %}

    def test_behaviour(self):
        #  Test inherent behaviours
        pass
