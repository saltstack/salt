# -*- coding: utf-8 -*-
'''
Module for running fmadm and fmdump on Solaris
TODO:
 - show (fmdump -u xxx -v)
 - list (-t and -T)
'''
from __future__ import absolute_import

# Import Python libs
import logging
import json

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {
    'list_records': 'list',
}

# Define the module's virtual name
__virtualname__ = 'fmadm'


@decorators.memoize
def _check_fmadm():
    '''
    Looks to see if fmadm is present on the system
    '''
    return salt.utils.which('fmadm')


def _check_fmdump():
    '''
    Looks to see if fmdump is present on the system
    '''
    return salt.utils.which('fmdump')


def __virtual__():
    '''
    Provides fmadm only on Solaris
    '''
    if salt.utils.is_sunos() and \
        _check_fmadm() and _check_fmdump():
        return __virtualname__
    return False


def _parse_fmdump(output):
    '''
    Parses fmdump output
    '''
    result = []
    output = output.split("\n")

    # extract header
    header = [field for field in output[0].lower().split(" ") if field]
    del output[0]

    # parse entries
    for entry in output:
        entry = [item for item in entry.split(" ") if item]
        entry = ['{0} {1} {2}'.format(entry[0], entry[1], entry[2])] + entry[3:]

        # prepare faults
        fault = OrderedDict()
        for field in header:
            fault[field] = entry[header.index(field)] 

        log.error(fault)
        result.append(fault)

    return result


def list_records(after=None, before=None):
    '''
    Return a list of records (fmdump)

    after : string
        filter events after time, see man fmdump for format

    before : string
        filter events before time, see man fmdump for format

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.list [verbose=True]
    '''
    ret = {}
    fmdump = _check_fmdump()
    cmd = '{cmd}{after}{before}'.format(
        cmd=fmdump,
        after=' -t {0}'.format(after) if after else '',
        before=' -T {0}'.format(before) if before else ''
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        result['Error'] = 'error executing fmdump'
    else:
        result = _parse_fmdump(res['stdout'])

    return result

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
