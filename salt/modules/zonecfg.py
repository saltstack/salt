# -*- coding: utf-8 -*-
'''
Module for Solaris 10's zonecfg

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      OmniOS,OpenIndiana,SmartOS,OpenSolaris,Solaris 10
:depend:        salt.modules.file

.. versionadded:: nitrogen

.. TODO:
    - set_property
    - add_resource
    - delete_resource

.. warning::
    Oracle Solaris 11's zonecfg is not supported by this module!
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.files
import salt.utils.decorators

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'zonecfg'

# Function aliases
__func_alias__ = {
    'import_': 'import'
}

# Global data
_zonecfg_info_resources = [
    'rctl',
    'net',
    'fs',
    'device',
    'dedicated-cpu',
    'dataset',
    'attr',
]

_zonecfg_info_resources_calculated = [
    'capped-cpu',
    'capped-memory',
]


@salt.utils.decorators.memoize
def _is_globalzone():
    '''
    Check if we are running in the globalzone
    '''
    if not __grains__['kernel'] == 'SunOS':
        return False

    zonename = __salt__['cmd.run_all']('zonename')
    if zonename['retcode']:
        return False
    if zonename['stdout'] == 'global':
        return True

    return False


def __virtual__():
    '''
    We are available if we are have zonecfg and are the global zone on
    Solaris 10, OmniOS, OpenIndiana, OpenSolaris, or Smartos.
    '''
    ## note: we depend on PR#37472 to distinguish between Solaris and Oracle Solaris
    if _is_globalzone() and salt.utils.which('zonecfg'):
        if __grains__['os'] in ['Solaris', 'OpenSolaris', 'SmartOS', 'OmniOS', 'OpenIndiana']:
            return __virtualname__

    return (
        False,
        '{0} module can only be loaded in a solaris globalzone.'.format(
            __virtualname__
        )
    )


def create(zone, brand, zonepath, force=False):
    '''
    Create an in-memory configuration for the specified zone.

    zone : string
        name of zone
    brand : string
        brand name
    zonepath : string
        path of zone
    force : boolean
        overwrite configuration

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.create deathscythe ipkg /zones/deathscythe
    '''
    ret = {'status': True}

    ## write config
    cfg_file = salt.utils.files.mkstemp()
    with salt.utils.fpopen(cfg_file, 'w+', mode=0o600) as fp_:
        fp_.write("create -b -F\n" if force else "create -b\n")
        fp_.write("set brand={0}\n".format(brand))
        fp_.write("set zonepath={0}\n".format(zonepath))

    ## create
    if not __salt__['file.directory_exists'](zonepath):
        __salt__['file.makedirs_perms'](zonepath if zonepath[-1] == '/' else '{0}/'.format(zonepath), mode='0700')
    res = __salt__['cmd.run_all']('zonecfg -z {zone} -f {cfg}'.format(
        zone=zone,
        cfg=cfg_file,
    ))
    ret['status'] = res['retcode'] == 0
    ret['message'] = res['stdout'] if ret['status'] else res['stderr']
    ret['message'] = ret['message'].replace('zonecfg: ', '')
    if ret['message'] == '':
        del ret['message']

    ## cleanup config file
    __salt__['file.remove'](cfg_file)

    return ret


def create_from_template(zone, template):
    '''
    Create an in-memory configuration from a template for the specified zone.

    zone : string
        name of zone
    template : string
        name of template

    .. warning::
        existing config will be overwritten!

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.create_from_template leo tallgeese
    '''
    ret = {'status': True}

    ## create from template
    res = __salt__['cmd.run_all']('zonecfg -z {zone} create -t {tmpl} -F'.format(
        zone=zone,
        tmpl=template,
    ))
    ret['status'] = res['retcode'] == 0
    ret['message'] = res['stdout'] if ret['status'] else res['stderr']
    ret['message'] = ret['message'].replace('zonecfg: ', '')
    if ret['message'] == '':
        del ret['message']

    return ret


def delete(zone):
    '''
    Delete the specified configuration from memory and stable storage.

    zone : string
        name of zone

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.delete epyon
    '''
    ret = {'status': True}

    ## delete zone
    res = __salt__['cmd.run_all']('zonecfg -z {zone} delete -F'.format(
        zone=zone,
    ))
    ret['status'] = res['retcode'] == 0
    ret['message'] = res['stdout'] if ret['status'] else res['stderr']
    ret['message'] = ret['message'].replace('zonecfg: ', '')
    if ret['message'] == '':
        del ret['message']

    return ret


def export(zone, path=None):
    '''
    Export the configuration from memory to stable storage.

    zone : string
        name of zone
    path : string
        path of file to export to

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.export epyon
        salt '*' zonecfg.export epyon /zones/epyon.cfg
    '''
    ret = {'status': True}

    ## export zone
    res = __salt__['cmd.run_all']('zonecfg -z {zone} export{path}'.format(
        zone=zone,
        path=' -f {0}'.format(path) if path else '',
    ))
    ret['status'] = res['retcode'] == 0
    ret['message'] = res['stdout'] if ret['status'] else res['stderr']
    ret['message'] = ret['message'].replace('zonecfg: ', '')
    if ret['message'] == '':
        del ret['message']

    return ret


def import_(zone, path):
    '''
    Import the configuration to memory from stable storage.

    zone : string
        name of zone
    path : string
        path of file to export to

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.import epyon /zones/epyon.cfg
    '''
    ret = {'status': True}

    ## create from file
    res = __salt__['cmd.run_all']('zonecfg -z {zone} -f {path}'.format(
        zone=zone,
        path=path,
    ))
    ret['status'] = res['retcode'] == 0
    ret['message'] = res['stdout'] if ret['status'] else res['stderr']
    ret['message'] = ret['message'].replace('zonecfg: ', '')
    if ret['message'] == '':
        del ret['message']

    return ret


def info(zone, show_all=False):
    '''
    Display the configuration from memory

    zone : string
        name of zone
    show_all : boolean
        also include calculated values like capped-cpu, cpu-shares, ...

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.info tallgeese
    '''
    ret = {}

    ## internal helpers
    def _parse_value(value):
        value = value.strip()
        if value.startswith('[') and value.endswith(']'):
            return value[1:-1].split(',')
        elif value.startswith('(') and value.endswith(')'):
            rval = {}
            for pair in value[1:-1].split(','):
                kv = pair.split('=')
                rval[kv[0].strip()] = kv[1].strip()
            return rval
        else:
            return value

    ## dump zone
    res = __salt__['cmd.run_all']('zonecfg -z {zone} info'.format(
        zone=zone,
    ))
    if res['retcode'] == 0:
        # parse output
        resname = None
        resdata = {}
        for line in res['stdout'].split("\n"):
            # ship calculated values (if requested)
            if line.startswith('['):
                if not show_all:
                    continue
                line = line.rstrip()[1:-1]

            # extract key
            key = line.strip().split(':')[0]
            if '[' in key:
                key = key[1:]

            # parse calculated resource (if requested)
            if key in _zonecfg_info_resources_calculated:
                if resname:
                    ret[resname].append(resdata)
                if show_all:
                    resname = key
                    resdata = {}
                    if key not in ret:
                        ret[key] = []
                else:
                    resname = None
                    resdata = {}
            # parse resources
            elif key in _zonecfg_info_resources:
                if resname:
                    ret[resname].append(resdata)
                resname = key
                resdata = {}
                if key not in ret:
                    ret[key] = []
            # store resource property
            elif line.startswith("\t"):
                # ship calculated values (if requested)
                if line.strip().startswith('['):
                    if not show_all:
                        continue
                    line = line.strip()[1:-1]
                resdata[key] = _parse_value(line.strip().split(':')[1])
            # store property
            else:
                if resname:
                    ret[resname].append(resdata)
                resname = None
                resdata = {}
                ret[key] = _parse_value(line.strip().split(':')[1])
        # store hanging resource
        if resname:
            ret[resname].append(resdata)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
