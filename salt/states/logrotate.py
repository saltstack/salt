# -*- coding: utf-8 -*-
'''
Logrotate state module
======================

Manage logrotate configuration on POSIX-based systems
'''

import logging

# Import salt libs
import salt.utils

# Enable proper logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work if logrotate is available
    '''
    if __salt__['cmd.has_exec']('logrotate'):
        return 'logrotate'
    return False

def show_conf(name='/etc/logrotate.conf', *args, **kwargs):
    '''
    Show parsed logrotate configuration

    name
        Path to logrotate configuration file, Default is ``/etc/logrotate.conf``

    Usage:

    .. code-block:: yaml

        /etc/logrotate.conf:
            logrotate.show_conf

    '''
    ret = {'name': name,
           'result': None,
           'comment': '',
           'changes': {}}

    if __opts__['test']:
        ret['comment'] = 'Logrotate configuration from {0} will be shown'.format(name)
        return ret

    returned = __salt__['logrotate.show_conf'](name)
    log.debug("logrotate.show_conf('{0}') returned the following dict: \n{1}".format(name, returned))

    if returned:
        ret['changes'] = returned
        ret['result'] = True
        ret['comment'] = 'Displaying logrotate configuration after parsing {0}'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to parse logrotate configuration file: {0}'.format(name)
    return ret
