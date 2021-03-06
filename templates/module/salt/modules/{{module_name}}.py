'''
{{module_name}} execution module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

{{short_description}}

.. versionadded:: {{version}}

:configuration:

    .. code-block:: yaml
        <your example config>

'''
import logging

import salt.utils.compat

try:
    #  Import libs...
    {% if depending_libraries %}
    import {{depending_libraries}}
    {% endif %}
    HAS_LIBS = True
    MISSING_PACKAGE_REASON = None
except ImportError as ie:
    HAS_LIBS = False
    MISSING_PACKAGE_REASON = ie.message

log = logging.getLogger(__name__)

__virtualname__ = '{{virtual_name}}'


def __virtual__():
    '''
    Only load this module if dependencies is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False,
            'The {{module_name}} execution module failed to load:'
            'import error - {0}.'.format(MISSING_PACKAGE_REASON))


def __init__(opts):
    #  Put logic here to instantiate underlying jobs/connections
    pass


def my_action(params):
    # Replace this with your actions
    pass
