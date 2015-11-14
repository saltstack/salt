# -*- coding: utf-8 -*-
'''
Module for running fmadm and fmdump on Solaris
.. versionadded:: Boron
'''
from __future__ import absolute_import

# Import Python libs
import logging

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
    return (
        False,
        '{0} module can only be loaded on Solaris with the fault management installed'.format(
            __virtualname__
        )
    )


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


def _parse_fmdump_verbose(output):
    '''
    Parses fmdump verbose output
    '''
    result = []
    output = output.split("\n")

    fault = []
    verbose_fault = {}
    for line in output:
        if line.startswith('TIME'):
            fault.append(line)
            if len(verbose_fault) > 0:
                result.append(verbose_fault)
                verbose_fault = {}
        elif len(fault) == 1:
            fault.append(line)
            verbose_fault = _parse_fmdump("\n".join(fault))[0]
            fault = []
        elif len(verbose_fault) > 0:
            if 'details' not in verbose_fault:
                verbose_fault['details'] = ""
            if line.strip() == '':
                continue
            verbose_fault['details'] = '{0}{1}\n'.format(
                verbose_fault['details'],
                line
            )
    if len(verbose_fault) > 0:
        result.append(verbose_fault)

    return result


def _parse_fmadm_config(output):
    '''
    Parsbb fmdump/fmadm output
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


def _fmadm_action_fmri(action, fmri):
    '''
    Internal function for fmadm.repqired, fmadm.replaced, fmadm.flush
    '''
    ret = {}
    fmadm = _check_fmadm()
    cmd = '{cmd} {action} {fmri}'.format(
        cmd=fmadm,
        action=action,
        fmri=fmri
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        result['Error'] = res['stderr']
    else:
        result = True

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


def show(uuid):
    '''
    Display log details

    uuid: string
        uuid of fault

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.show 11b4070f-4358-62fa-9e1e-998f485977e1
    '''
    ret = {}
    fmdump = _check_fmdump()
    cmd = '{cmd} -u {uuid} -V'.format(
        cmd=fmdump,
        uuid=uuid
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        result['Error'] = 'error executing fmdump'
    else:
        result = _parse_fmdump_verbose(res['stdout'])

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
        result['Error'] = 'error executing fmadm config'
    else:
        result = _parse_fmadm_config(res['stdout'])

    return result


def load(path):
    '''
    Load specified fault manager module

    path: string
        path of fault manager module

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.load /module/path
    '''
    ret = {}
    fmadm = _check_fmadm()
    cmd = '{cmd} load {path}'.format(
        cmd=fmadm,
        path=path
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        result['Error'] = res['stderr']
    else:
        result = True

    return result


def unload(module):
    '''
    Unload specified fault manager module

    module: string
        module to unload

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.unload software-response
    '''
    ret = {}
    fmadm = _check_fmadm()
    cmd = '{cmd} unload {module}'.format(
        cmd=fmadm,
        module=module
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        result['Error'] = res['stderr']
    else:
        result = True

    return result


def reset(module, serd=None):
    '''
    Reset module or sub-component

    module: string
        module to unload
    serd : string
        serd sub module

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.reset software-response
    '''
    ret = {}
    fmadm = _check_fmadm()
    cmd = '{cmd} reset {serd}{module}'.format(
        cmd=fmadm,
        serd='-s {0} '.format(serd) if serd else '',
        module=module
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        result['Error'] = res['stderr']
    else:
        result = True

    return result


def flush(fmri):
    '''
    Flush cached state for resource

    fmri: string
        fmri

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.flush fmri
    '''
    return _fmadm_action_fmri('flush', fmri)


def repaired(fmri):
    '''
    Notify fault manager that resource has been repaired

    fmri: string
        fmri

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.repaired fmri
    '''
    return _fmadm_action_fmri('repaired', fmri)


def replaced(fmri):
    '''
    Notify fault manager that resource has been replaced

    fmri: string
        fmri

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.repaired fmri
    '''
    return _fmadm_action_fmri('replaced', fmri)


def acquit(fmri):
    '''
    Acquit resource or acquit case

    fmri: string
        fmri or uuid

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.acquit fmri | uuid
    '''
    return _fmadm_action_fmri('acquit', fmri)


def faulty():
    '''
    Display list of faulty resources

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.faulty
    '''
    ret = {}
    fmadm = _check_fmadm()
    cmd = '{cmd} faulty'.format(
        cmd=fmadm,
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = {}
    if retcode != 0:
        #NOTE: manpage vague, non 0 output = we have faults
        #FIXME: capture correct output and try to parse
        result = True
    else:
        result = False

    return result

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
