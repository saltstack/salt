import salt.utils.templates
import salt.exceptions

import pytest


def test_sanboxed_jinja():
    '''
    Jinja sandbox prevents access to dangerous builtins
    '''
    with pytest.raises(salt.exceptions.SaltRenderError, match=".* access to attribute .*"):
        output = salt.utils.templates.render_jinja_tmpl('{{ [].__class__ }}', {'opts': {}, 'saltenv': ''})

