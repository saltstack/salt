# -*- coding: utf-8 -*-
'''
{{module_name}} execution module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

{{short_description}}

.. versionadded:: {{version}}

:configuration:

    .. code-block:: yaml
        <your example config>

'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

# Import salt libs
import salt.utils.compat

log = logging.getLogger(__name__)

# Import third party libs
HAS_LIBS = False
try:
    #  Import libs...
    {% if depending_libraries %}
    import {{depending_libraries}}
    {% endif %}
    HAS_LIBS = True
except ImportError as ie:
    missing_package = ie.message

log = logging.getLogger(__name__)

__virtualname__ = '{{virtual_name}}'


def __virtual__():
    '''
    Only load this module if dependencies is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False, 'The {{module_name}} execution module failed to load:'
            'import error - {0}.'.format(missing_package))


def __init__(opts):
    #  Put logic here to instantiate underlying jobs/connections
    salt.utils.compat.pack_dunder(__name__)


def my_action(params):
    # Replace this with your actions
    pass
