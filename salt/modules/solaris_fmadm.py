# -*- coding: utf-8 -*-
'''
Module for running fmadm and fmdump on Solaris
TODO:
 - show (fmdump -u xxx -v)
 - fmadm faulty [-afgiprsv] [-u <uuid>] [-n <max_fault>] - display list of faulty resources
 - fmadm flush <fmri> ...         - flush cached state for resource
 - fmadm load <path>              - load specified fault manager module
 - fmadm repaired <fmri>|label>   - notify fault manager that resource has been repaired
 - fmadm acquit <fmri> [<uuid>] | label [<uuid>] | <uuid> - acquit resource or acquit case
 - fmadm replaced <fmri>|label    - notify fault manager that resource has been replaced
 - fmadm reset [-s serd] <module> - reset module or sub-component
 - fmadm rotate <logname>         - rotate log file
 - fmadm unload <module>          - unload specified fault manager module
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

        result.append(fault)

    return result

def _parse_fmadm_config(output):
    '''
    Parses fmdump/fmadm output
    '''
    result = []
    output = output.split("\n")

    # extract header
    header = [field for field in output[0].lower().split(" ") if field]
    del output[0]

    # parse entries
    for entry in output:
        entry = [item for item in entry.split(" ") if item]
        entry = entry[0:3] + [" ".join(entry[3:])]

        # prepare component
        component = OrderedDict()
        for field in header:
            component[field] = entry[header.index(field)] 
        
        result.append(component)

    # keying
    keyed_result = OrderedDict()
    for component in result:
        keyed_result[component['module']] = component
        del keyed_result[component['module']]['module']

    result = keyed_result

    return result


def list_records(after=None, before=None):
    '''
    Display fault management logs

    after : string
        filter events after time, see man fmdump for format

    before : string
        filter events before time, see man fmdump for format

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.list
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

def config():
    '''
    Display fault manager configuration

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.config
    '''
    ret = {}
    fmadm = _check_fmadm()
    cmd = '{cmd} config'.format(
        cmd=fmadm
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        result['Error'] = 'error executing fmdump'
    else:
        result = _parse_fmadm_config(res['stdout'])

    return result

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
