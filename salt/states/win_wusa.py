# -*- coding: utf-8 -*-
'''
Microsoft Updates (KB) Management

This module provides the ability to enforce KB installations
from files (.msu), without WSUS.

.. versionadded:: Neon
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import logging

# Import salt libs
import salt.utils.platform
import salt.exceptions

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = 'win_wusa'


def __virtual__():
    '''
    Load only on Windows
    '''
    if not salt.utils.platform.is_windows():
        return False, 'Only available on Windows systems'

    return __virtualname__


def installed(name, source):
    '''
    Enforce the installed state of a KB

    name
        Name of the Windows KB ("KB123456")
    source
        Source of .msu file corresponding to the KB

    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': '',
        }

    # Start with basic error-checking. Do all the passed parameters make sense
    # and agree with each-other?
    if not name or not source:
        raise salt.exceptions.SaltInvocationError(
            'Arguments "name" and "source" are mandatory.')

    # Check the current state of the system. Does anything need to change?
    current_state = __salt__['win_wusa.is_installed'](name)

    if current_state:
        ret['result'] = True
        ret['comment'] = 'KB already installed'
        return ret

    # The state of the system does need to be changed. Check if we're running
    # in ``test=true`` mode.
    if __opts__['test'] is True:
        ret['comment'] = 'The KB "{0}" will be installed.'.format(name)
        ret['changes'] = {
            'old': current_state,
            'new': True,
        }

        # Return ``None`` when running with ``test=true``.
        ret['result'] = None

        return ret

    try:
        result = __states__['file.cached'](source,
                                           skip_verify=True,
                                           saltenv=__env__)
    except Exception as exc:
        msg = 'Failed to cache {0}: {1}'.format(
                salt.utils.url.redact_http_basic_auth(source),
                exc.__str__())
        log.exception(msg)
        ret['comment'] = msg
        return ret

    if result['result']:
        # Get the path of the file in the minion cache
        cached = __salt__['cp.is_cached'](source, saltenv=__env__)
    else:
        log.debug(
            'failed to download %s',
            salt.utils.url.redact_http_basic_auth(source)
        )
        return result

    # Finally, make the actual change and return the result.
    new_state = __salt__['win_wusa.install'](cached)

    ret['comment'] = 'The KB "{0}" was installed!'.format(name)

    ret['changes'] = {
        'old': current_state,
        'new': new_state,
    }

    ret['result'] = True

    return ret
